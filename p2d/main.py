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
from argparse import ArgumentParser

from ._version import __version__
from .generate_testlib_for_domjudge import generate_testlib_for_domjudge

RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')
BIG_SAMPLE_SIZE = 40

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
    'time-limit-exceeded': 'time_limit_exceed',
    'time-limit-exceeded-or-accepted': 'time_limit_exceed',
    'time-limit-exceeded-or-memory-limit-exceeded': 'run_time_error',
    'memory-limit-exceeded': 'run_time_error',
    'rejected': 'run_time_error',  # = label 'Incorrect' in polygon.
    'failed': 'run_time_error',
    'do-not-run': None
}


def prepare_argument_parser():
    parser = ArgumentParser(description='Convert Polygon Problem Package to DOMjudge Problem Package.')
    parser.add_argument('--polygon', '--from', required=True, help='Path of the polygon package. Can be either a directory or a zip.')
    parser.add_argument('--domjudge', '--to', required=True, help='Name of the domjudge package that will be created. Can be either a directory or a zip.')
    parser.add_argument('--force', '-f', action='store_true', help='Whether the script can overwrite the destination given by --to.')
    parser.add_argument('--color', required=True, help='Color of the problem.')
    parser.add_argument('--contest', required=True, help='Name of the contest, used only to generate the statement.')
    parser.add_argument('--statements-template', default=os.path.join(RESOURCES_PATH, 'statements_template.tex'), help='Path of the LaTeX statements template.')
    parser.add_argument('--big-sample-size', type=int, default=BIG_SAMPLE_SIZE, help='Number of characters in the longest line of a sample which triggers the call of \'\\bigsample\' instead of \'\\sample\' in the tex source of the statement.')
    parser.add_argument('--update-testlib', action='store_true', help='Whether to update the local version of testlib (syncing it with the last version from the github repository).')
    parser.add_argument('--verbosity', choices=['debug', 'info', 'warning'],
                        default='info', help='Verbosity of the logs.')
    parser.add_argument('--keep-dirs', action='store_true', help='Whether the temporary directories created shall be kept or removed (useful for debugging).')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

    return parser


def parse_samples_explanations(notes):
    lines = notes.splitlines()
    explanations = {}
    test_id = -1
    curr = ''
    for line in lines:
        if re.fullmatch(r'%BEGIN (\d+)', line.strip()):
            assert(test_id == -1)
            test_id = int(re.fullmatch(r'%BEGIN (\d+)', line.strip()).group(1))
        elif re.fullmatch(r'%END', line.strip()):
            assert(test_id != -1)
            assert(test_id not in explanations)
            explanations[test_id] = curr
            curr = ''
            test_id = -1
        elif test_id != -1:
            curr += line + '\n'
    assert(test_id == -1)
    return explanations


def contains_long_line(args, txt):
    for line in txt.split('\n'):
        if len(line) > args.big_sample_size:
            return True
    return False


# Returns a string containing the statement tex (only what shall go inside
# \begin{document} \end{document}).
# The samples (.in/.out) are copied in pdflatex_dir.
def generate_problem_tex(args, problem, pdflatex_dir):
    samples_tex = ''

    sample_id = 1
    for sample in problem['statement']['samples']:
        sample_path = (os.path.join(pdflatex_dir, problem['letter']
                       + str(sample_id)))

        shutil.copyfile(sample['in'], sample_path + '.in')
        shutil.copyfile(sample['out'], sample_path + '.out')

        if sample['is_long']:
            samples_tex += '\\bigsample{%s}' % sample_path
        else:
            samples_tex += '\\sample{%s}' % sample_path
        samples_tex += '\n'

        if sample['explanation']:
            samples_tex += '\\sampleexplanation{%s}\n' % sample['explanation']

        sample_id += 1

    with open(os.path.join(RESOURCES_PATH, 'problem_template.tex')) as f:
        problem_template = f.read()
    replacements_problem = {
        'LETTER': problem['letter'],
        'NAME': problem['name'],
        'TIMELIMIT': problem['timelimit'],
        'MEMORYLIMIT': problem['memorylimit'],
        'LEGEND': problem['statement']['legend'],
        'INPUT': problem['statement']['input'],
        'OUTPUT': problem['statement']['output'],
        'SAMPLES': samples_tex
    }
    for placeholder in replacements_problem:
        problem_template = problem_template.replace(
            '??%s??' % placeholder, str(replacements_problem[placeholder]))

    return problem_template


# Execute pdflatex on `pdflatex_dir/tex` and copies the generated pdf document
# in the `pdf` path.
def tex2pdf(pdflatex_dir, tex, pdf):
    command_as_list = ['pdflatex', '-interaction=nonstopmode',
                       '-output-dir=' + pdflatex_dir, '-jobname=problem',
                       os.path.join(pdflatex_dir, tex)]

    logging.debug('pdflatex command = ' + ' '.join(command_as_list))
    pdflatex = subprocess.run(command_as_list, stdout=subprocess.PIPE,
                              shell=False)
    if pdflatex.returncode != 0:
        logging.error(' '.join(command_as_list) + '\n'
                      + pdflatex.stdout.decode("utf-8"))
        logging.error('The pdflatex command returned an error.')
        exit(1)

    shutil.copyfile(os.path.join(pdflatex_dir, 'problem.pdf'), pdf)


# Produce the statement domjudge/problem.pdf.
def generate_problem_pdf(args, problem, domjudge):
    pdflatex_dir = tempfile.mkdtemp(
        prefix='%s-p2d-pdflatex' % problem['shortname'])
    logging.debug('Temporary directory for pdflatex: \'%s\'.' % pdflatex_dir)

    problem_tex = generate_problem_tex(args, problem, pdflatex_dir)

    replacements_statements = {
        'CONTEST': args.contest,
        'DOCUMENTCONTENT': problem_tex
    }
    with open(args.statements_template) as f:
        statements_template = f.read()
    for placeholder in replacements_statements:
        statements_template = statements_template.replace(
            '??%s??' % placeholder, str(replacements_statements[placeholder]))

    with open(os.path.join(pdflatex_dir, 'statement.tex'), 'w') as f:
        f.write(statements_template)

    # Compile the tex to pdf.
    logging.info('Compiling the statement to pdf.')
    tex2pdf(
        pdflatex_dir, 'statement.tex', os.path.join(domjudge, 'problem.pdf'))

    if not args.keep_dirs:
        shutil.rmtree(pdflatex_dir)


# Parsing a Polygon package to a Dictionary object.
#   args = arguments passed by the user
#   polygon = path of the root of the polygon package directory
#
# The returned dictionary has the following structure ('[]' denotes a list):
'''
color: string
letter: string
shortname: string
name: string
timelimit: float
memorylimit: int


statement:
    legend: string
    input: string
    output: string
    samples: []
        in: string
        out: string
        is_long: boolean
        explanation: string

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
def parse_problem_from_polygon(args, polygon):
    def abs_path(*path):
        return os.path.join(polygon, *path)

    logging.info('Parsing the polygon package directory \'%s\'.' % polygon)
    logging.debug('Parsing \'%s\'' % abs_path('problem.xml'))

    problem = {}

    # Metadata
    problem_xml = xml.etree.ElementTree.parse(abs_path('problem.xml'))
    problem['shortname'] = problem_xml.getroot().attrib['short-name']
    problem['name'] = problem_xml.find('names').find('name').attrib['value']
    problem['letter'] = os.path.splitext(os.path.basename(args.domjudge))[0]
    problem['color'] = args.color
    for testset in problem_xml.find('judging').findall('testset'):
        if testset.attrib['name'] == 'tests':
            tl_str = testset.find('time-limit').text
            ml_str = testset.find('memory-limit').text
            problem['timelimit'] = float(tl_str) / 1000.0
            problem['memorylimit'] = int(ml_str) // 2**20

    # Statement
    problem['statement'] = {}
    statement_json_path = abs_path(
        'statements', 'english', 'problem-properties.json')
    with open(statement_json_path) as f:
        statement_json = json.load(f)
        problem['statement']['legend'] = statement_json['legend']
        problem['statement']['input'] = statement_json['input']
        problem['statement']['output'] = statement_json['output']
        explanations = parse_samples_explanations(statement_json['notes'])

        sample_id = 1
        samples = []
        for sample_json in statement_json['sampleTests']:
            sample = {
                'in': abs_path('statements', 'english', sample_json['inputFile']),
                'out': abs_path('statements', 'english', sample_json['outputFile']),
                'is_long': contains_long_line(args, sample_json['inputFile'])
                           or contains_long_line(args, sample_json['outputFile']),
                'explanation': explanations[sample_id] if sample_id in explanations
                                                       else None
            }
            samples.append(sample)
            sample_id += 1
        problem['statement']['samples'] = samples

    # Tests
    problem['tests'] = []
    for testset in problem_xml.find('judging').iter('testset'):
        if testset.attrib['name'] == 'pretests':
            continue
        if testset.attrib['name'] != 'tests':
            raise RuntimeError('The tests shall may contain only the testsets \'tests\' and \'pretests\' (\'pretests\' is not necessary.')
        input_format = testset.find('input-path-pattern').text
        output_format = testset.find('answer-path-pattern').text

        test_id = 1
        for test in testset.iter('test'):
            t = {
                'num': test_id,
                'in': abs_path(input_format % test_id),
                'out': abs_path(output_format % test_id),
                'is_sample': 'sample' in test.attrib
            }
            problem['tests'].append(t)
            test_id += 1
    if not problem['tests']:
        raise RuntimeError('One of the testset shall be called \'tests\'.')

    # Checker
    checker_xml = problem_xml.find('assets').find('checker')
    problem['checker'] = {
        'source': abs_path(checker_xml.find('source').attrib['path']),
        'name': checker_xml.attrib['name'] if 'name' in checker_xml.attrib
                                           else None
    }

    if not problem['checker']['source'].endswith('.cpp'):
        raise RuntimeError('Only C++ checkers (using testlib) are supported.')

    # Interactor
    problem['interactor'] = None
    if problem_xml.find('assets').find('interactor'):
        logging.debug('The problem is interactive.')
        problem['interactor'] = {
            'source': abs_path(problem_xml.find('assets').find('interactor')
                                          .find('source').attrib['path'])
        }

    # Solutions
    problem['solutions'] = []
    solutions_tag = problem_xml.find('assets').find('solutions')
    for solution in solutions_tag.iter('solution'):
        s = {
            'source': abs_path(solution.find('source').attrib['path']),
            'result': solution.attrib['tag']
        }
        problem['solutions'].append(s)

    return problem


# Generate the DOMjudge package directory of problem.
#   problem = dictionary object describing a problem (as generated by
#             parse_problem_from_polygon
#   domjudge = path of the root of the polygon package directory (initially it
#              is empty)
def convert_to_domjudge(args, problem, domjudge):
    logging.info('Creating the DOMjudge package directory \'%s\'.' % domjudge)

    problem_yaml_data = {}

    # Metadata
    logging.debug('Writing \'domjudge-problem.ini\'.')
    ini_file = os.path.join(domjudge, 'domjudge-problem.ini')
    ini_content = [
        'short-name = %s' % problem['shortname'],
        'name = %s' % problem['name'].replace("'", "`"),
        'timelimit = %s' % problem['timelimit'],
        'color = %s' % problem['color']
    ]
    with open(ini_file, 'w', encoding='utf-8') as f:
        f.writelines(map(lambda s: s + '\n', ini_content))
    problem_yaml_data['limits'] = {'memory': problem['memorylimit']}

    # Statement
    generate_problem_pdf(args, problem, domjudge)

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
        assert(re.match(r'std\:\:([a-z]+)\.cpp', checker_name) is not None)
        checker_name = re.match(r'std\:\:([a-z]+)\.cpp', checker_name).groups()[0]
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


def main():
    args = prepare_argument_parser().parse_args()
    logging.basicConfig(
        stream=sys.stdout,
        format='%(levelname)s: %(message)s',
        level=eval('logging.' + args.verbosity.upper())
    )

    if args.domjudge.endswith('/'):
        args.domjudge = args.domjudge[:-1]

    # Unzip the polygon package if it is zipped.
    if zipfile.is_zipfile(args.polygon):
        polygon = tempfile.mkdtemp(prefix='p2d-polygon')
        logging.debug('Unzipping the polygon package in %s.' % polygon)
        with zipfile.ZipFile(args.polygon, 'r') as f:
            logging.info('Unzipping the polygon package \'%s\'.'
                         % args.polygon)
            f.extractall(polygon)
    else:
        if not os.path.isdir(args.polygon):
            raise FileNotFoundError('The polygon package %s does not exist.'
                                    % args.polygon)
        polygon = args.polygon

    # Parse the polygon package
    problem = parse_problem_from_polygon(args, polygon)

    # Create the domjudge directory.
    if args.domjudge.endswith('.zip'):
        if os.path.isfile(args.domjudge) and not args.force:
            raise FileExistsError('The zip file %s already exists. Use --force to let the script overwrite existing files.' % args.domjudge)
        domjudge = tempfile.mkdtemp(prefix='p2d-domjudge')
        logging.debug('The temporary directory for the DOMjudge package is %s.'
                      % domjudge)
    else:
        if os.path.isdir(args.domjudge) and not args.force:
            raise FileExistsError('The directory %s already exists. Use --force to let the script overwrite existing directories.' % args.domjudge)
        domjudge = args.domjudge
        # The following three lines guarantee that in the end the domjudge
        # directory is empty.
        pathlib.Path(domjudge).mkdir(exist_ok=args.force)
        shutil.rmtree(domjudge)
        pathlib.Path(domjudge).mkdir()

    logging.debug(json.dumps(problem, sort_keys=True, indent=4))

    testlib_h = os.path.join(RESOURCES_PATH, 'testlib.h')
    if args.update_testlib or not os.path.isfile(testlib_h):
        logging.info('Downloading testlib.h and patching it for DOMjudge compatibility.')
        generate_testlib_for_domjudge(testlib_h)

    # Produce the domjudge package.
    convert_to_domjudge(args, problem, domjudge)

    # Erase the unzipped polygon package if it were created.
    if zipfile.is_zipfile(args.polygon) and not args.keep_dirs:
        shutil.rmtree(polygon)

    # Create the domjudge zip if required.
    if args.domjudge.endswith('.zip'):
        logging.info('Zipping the DOMjudge package \'%s\'.' % args.domjudge)
        shutil.make_archive(args.domjudge[:-4], 'zip', domjudge)
        if not args.keep_dirs:
            shutil.rmtree(domjudge)

    logging.info('Converted \'%s\' to the DOMjudge format.'
                 % problem['shortname'])


if __name__ == "__main__":
    main()

# TODO: Create whole problem set (with custom front page).
#       Create tests for this tool.
#       Interaction section is not supported in the statement.
#       Handle images in the statement.
#       Handle additional files used in the generator/checker/anything else.
