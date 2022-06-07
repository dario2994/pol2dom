import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree
import yaml
import zipfile

from p2d._version import __version__
from p2d import tex_utilities

RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')

CHECKER_POLYGON2DOMJUDGE = {
    'fcmp': 'case_sensitive space_change_sensitive',
    'hcmp': None,
    'lcmp': None,
    'ncmp': None,
    'nyesno': None,
    'rcmp4': 'float_tolerance 1e-4',
    'rcmp6': 'float_tolerance 1e-6',
    'rcmp9': 'float_tolerance 1e-9',
    'wcmp': None,
    'yesno': None
}

RESULT_POLYGON2DOMJUDGE = {
    'main': 'accepted',
    'accepted': 'accepted',
    'wrong-answer': 'wrong_answer',
    'presentation-error': 'wrong_answer',
    'time-limit-exceeded': 'time_limit_exceeded',
    'time-limit-exceeded-or-accepted': None,
    'time-limit-exceeded-or-memory-limit-exceeded': None,
    'memory-limit-exceeded': 'run_time_error',
    'rejected': None,  # = label 'Incorrect' in polygon.
    'failed': None,
    'do-not-run': None
}

# Generate the DOMjudge package directory of problem.
#   problem = dictionary object describing a problem (as generated by
#             parse_problem_from_polygon
#   domjudge = path of the root of the polygon package directory (initially it
#              is empty)
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_domjudge_package(problem, domjudge, params):
    logging.info('Creating the DOMjudge package directory \'%s\'.' % domjudge)

    problem_yaml_data = {}

    # Metadata
    logging.debug('Writing \'domjudge-problem.ini\'.')
    ini_file = os.path.join(domjudge, 'domjudge-problem.ini')
    ini_content = [
        'short-name = %s' % problem['name'],
        'name = %s' % problem['title'].replace("'", "`"),
        'timelimit = %s' % problem['timelimit'],
        'color = %s' % problem['color']
    ]
    with open(ini_file, 'w', encoding='utf-8') as f:
        f.writelines(map(lambda s: s + '\n', ini_content))
    problem_yaml_data['limits'] = {'memory': problem['memorylimit']}

    # Statement
    tex_utilities.generate_statement_pdf(
        problem, os.path.join(domjudge, 'problem.pdf'), params)

    # Tests
    logging.info('Copying the tests in the DOMjudge package.')

    sample_dir = os.path.join(domjudge, 'data', 'sample')
    secret_dir = os.path.join(domjudge, 'data', 'secret')
    pathlib.Path(sample_dir).mkdir(parents=True)
    pathlib.Path(secret_dir).mkdir(parents=True)
    for test in problem['tests']:
        destination = sample_dir if test['is_sample'] else secret_dir
        shutil.copyfile(
            test['in'], os.path.join(destination, '%s.in' % test['num']))
        shutil.copyfile(
            test['out'], os.path.join(destination, '%s.ans' % test['num']))

    # Checker or interactor.
    if problem['interactor'] is not None:
        problem_yaml_data['validation'] = 'custom interactive'
        pathlib.Path(domjudge, 'output_validators').mkdir()
        shutil.copyfile(os.path.join(RESOURCES_PATH, 'testlib.h'),
                        os.path.join(domjudge, 'output_validators', 'testlib.h'))
        shutil.copyfile(
                problem['interactor']['source'],
                os.path.join(domjudge, 'output_validators', 'interactor.cpp'))
    elif problem['checker']['name'] is not None:
        checker_name = problem['checker']['name']
        logging.debug('Standard checker \'%s\'.' % checker_name)

        checker_name_match = re.match(r'std\:\:([a-z0-9]+)\.cpp', checker_name)
        assert(checker_name_match)
        checker_name = checker_name_match.groups()[0]
        assert(checker_name in CHECKER_POLYGON2DOMJUDGE)

        problem_yaml_data['validation'] = 'default'
        if CHECKER_POLYGON2DOMJUDGE[checker_name] is not None:
            problem_yaml_data['validator_flags'] = \
                CHECKER_POLYGON2DOMJUDGE[checker_name]
    else:
        logging.debug('Custom checker.')
        problem_yaml_data['validation'] = 'custom'
        pathlib.Path(domjudge, 'output_validators').mkdir()
        shutil.copyfile(
                os.path.join(RESOURCES_PATH, 'testlib.h'),
                os.path.join(domjudge, 'output_validators', 'testlib.h'))
        shutil.copyfile(
                problem['checker']['source'],
                os.path.join(domjudge, 'output_validators', 'checker.cpp'))

    # Solutions
    for solution in problem['solutions']:
        result = solution['result']
        assert(result in RESULT_POLYGON2DOMJUDGE)
        result = RESULT_POLYGON2DOMJUDGE[result]
        if result is not None:
            result_dir = os.path.join(domjudge, 'submissions', result)
            submission_name = os.path.basename(solution['source'])
            pathlib.Path(result_dir).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(solution['source'],
                            os.path.join(result_dir, submission_name))

    # Write problem.yaml
    yaml_path = os.path.join(domjudge, 'problem.yaml')
    logging.debug(
            'Writing into \'%s\' the dictionary %s'
            % (yaml_path, problem_yaml_data))
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(problem_yaml_data, f, default_flow_style=False)