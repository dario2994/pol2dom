import json
import logging
import os
import pathlib
import re
import sys
from filecmp import cmp
import xml.etree.ElementTree

from p2d._version import __version__
    
def parse_samples_explanations(notes):
    lines = notes.splitlines()
    explanations = {}
    test_id = -1
    curr = ''
    for line in lines:
        if re.fullmatch(r'%BEGIN (\d+)', line.strip()):
            if test_id != -1:
                logging.error('In the samples explanations, there are two %BEGIN lines without an %END line in between: %s.' % notes)
                exit(1)
            assert(test_id == -1)
            test_id = int(re.fullmatch(r'%BEGIN (\d+)', line.strip()).group(1))
        elif re.fullmatch(r'%END', line.strip()):
            if test_id == -1:
                logging.error('In the samples explanations, there is an %END line which does not close any %BEGIN line: %s.' % notes)
                exit(1)
            assert(test_id != -1)
            assert(test_id not in explanations)
            curr = curr[0].upper() + curr[1:]  # Capitalize first letter.
            explanations[test_id] = curr
            curr = ''
            test_id = -1
        elif test_id != -1:
            curr += line + '\n'
    if test_id != -1:
        logging.error('In the samples explanations, the last %BEGIN line is not matched by an %END line: %s.' % notes)
        exit(1)
    assert(test_id == -1)
    return explanations


# Parsing a Polygon package to a Dictionary object.
#   polygon = path of the root of the polygon package directory
#
# The returned dictionary has the following structure ('[]' denotes a list):
'''
color: string (not set in this function as it is not present in polygon)
label: string (not set in this function as it is not present in polygon)
name: string
title: string
timelimit: float (seconds)
memorylimit: int (MiB)
author: string (not set in this function as it is not present in polygon)
preparation: string (not set in this function as it is not present in polygon)

statement:
    legend: string
    input: string
    output: string
    samples: []
        in: string
        out: string
        explanation: string
    tutorial: string

tests: []
    num: integer
    in: string
    out: string
    is_sample: boolean

checker:
    name: string or None
    source: string

interactor:
    source: string or None

solutions: []
    source: string
    result: string
'''
def parse_problem_from_polygon(polygon):
    def pol_path(*path):
        return os.path.join(polygon, *path)

    logging.debug('Parsing the polygon package directory \'%s\'.' % polygon)
    if not os.path.isfile(pol_path('problem.xml')):
        logging.error('The directory \'%s\' is not a polygon package (as it does not contain the file \'problem.xml\'.' % polygon)
        exit(1)

    problem = {}

    # Metadata
    logging.debug('Parsing \'%s\'' % pol_path('problem.xml'))
    problem_xml = xml.etree.ElementTree.parse(pol_path('problem.xml'))
    problem['name'] = problem_xml.getroot().attrib['short-name']
    problem['title'] = problem_xml.find('names').find('name').attrib['value']
    for testset in problem_xml.find('judging').findall('testset'):
        if testset.attrib['name'] == 'tests':
            tl_str = testset.find('time-limit').text
            ml_str = testset.find('memory-limit').text
            problem['timelimit'] = float(tl_str) / 1000.0
            # In the polygon package the memory limit is given in byte.
            # The memory limit written in polygon is interpreted as MiB, thus
            # here we recover such number dividing by 2**20.
            # DOMjudge interpret this value in MiB, so the conversion is exact
            # see icpc.io/problem-package-format/spec/problem_package_format#limits).
            problem['memorylimit'] = int(ml_str) // 2**20 # MiB
    assert('timelimit' in problem and 'memorylimit' in problem)
    
    # Statement
    problem['statement'] = {}
    statement_json_path = pol_path(
        'statements', 'english', 'problem-properties.json')
    with open(statement_json_path) as f:
        statement_json = json.load(f)
        problem['statement']['legend'] = statement_json['legend']
        problem['statement']['input'] = statement_json['input']
        problem['statement']['output'] = statement_json['output']
        problem['statement']['tutorial'] = statement_json['tutorial']
        explanations = parse_samples_explanations(statement_json['notes'])

        sample_id = 1
        samples = []
        for sample_json in statement_json['sampleTests']:
            sample = {
                'in': pol_path('statements', 'english', sample_json['inputFile']),
                'out': pol_path('statements', 'english', sample_json['outputFile']),
                'explanation': explanations.get(sample_id)
            }
            samples.append(sample)
            sample_id += 1
        problem['statement']['samples'] = samples

    # Detecting images
    problem['statement']['images'] = []
    statement_path = pol_path('statements', 'english')
    image_extensions = ['.jpg', '.gif', '.png', '.jpeg', '.pdf', '.svg']
    for f in os.listdir(statement_path):
        if any([f.lower().endswith(ext) for ext in image_extensions]):
            problem['statement']['images'].append(
                    (f, os.path.join(statement_path,f)))

    # Tests
    problem['tests'] = []
    test_id = 1
    for testset in problem_xml.find('judging').iter('testset'):
        if testset.attrib['name'] not in ['pretests', 'tests']:
            logging.warning('testset \'%s\' ignored: only the testset \'tests\' is exported in DOMjudge (apart from the samples).' % testset.attrib['name'])
        local_id = 1
        # Pretests are processed only to collect samples.

        input_format = testset.find('input-path-pattern').text
        output_format = testset.find('answer-path-pattern').text
        # Fetch samples from statements directory (for custom output)
        sample_input_format = input_format.replace('tests/', os.path.join('statements', 'english') + '/example.')
        sample_output_format = output_format.replace('tests/', os.path.join('statements', 'english') + '/example.')

        for test in testset.iter('test'):
            if 'sample' in test.attrib and not cmp(pol_path(input_format % local_id), pol_path(sample_input_format % local_id)):
                raise RuntimeError('Custom inputs are not supported.')  # Because DOMjudge evaluates the same sample inputs that are provided to contestants.
            t = {
                'num': test_id,
                'in': pol_path(input_format % local_id),
                'out': pol_path(sample_output_format % local_id) if 'sample' in test.attrib else pol_path(output_format % local_id),
                'is_sample': 'sample' in test.attrib
            }
            local_id += 1
            
            if testset.attrib['name'] == 'tests' or t['is_sample']:
                problem['tests'].append(t)
                test_id += 1
    if not problem['tests']:
        raise RuntimeError('One of the testset shall be called \'tests\'.')

    # Checker
    checker_xml = problem_xml.find('assets').find('checker')
    problem['checker'] = {
        'source': pol_path(checker_xml.find('source').attrib['path']),
        'name': checker_xml.attrib.get('name')
    }

    checker_name = problem['checker']['source']
    if not checker_name.endswith('.cpp') and not checker_name.endswith('.cc'):
        raise RuntimeError('Only C++ checkers (using testlib) are supported.')

    # Interactor
    problem['interactor'] = None
    if problem_xml.find('assets').find('interactor'):
        logging.debug('The problem is interactive.')
        problem['interactor'] = {
            'source': pol_path(problem_xml.find('assets').find('interactor')
                                          .find('source').attrib['path'])
        }

    # Solutions
    problem['solutions'] = []
    solutions_tag = problem_xml.find('assets').find('solutions')
    for solution in solutions_tag.iter('solution'):
        s = {
            'source': pol_path(solution.find('source').attrib['path']),
            'result': solution.attrib['tag']
        }
        problem['solutions'].append(s)

    return problem
