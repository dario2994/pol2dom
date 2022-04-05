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
    'time-limit-exceeded': 'time_limit_exceeded',
    'time-limit-exceeded-or-accepted': None,
    'time-limit-exceeded-or-memory-limit-exceeded': None,
    'memory-limit-exceeded': 'run_time_error',
    'rejected': None,  # = label 'Incorrect' in polygon.
    'failed': None,
    'do-not-run': None
}


def prepare_argument_parser():
    parser = ArgumentParser(description='Convert Polygon Problem Package to DOMjudge Problem Package.')
    parser.add_argument('--polygon', '--from', required=True, help='Path of the polygon package. Can be either a directory or a zip.')
    parser.add_argument('--domjudge', '--to', required=True, help='Name of the domjudge package that will be created. Can be either a directory or a zip.')
    parser.add_argument('--force', '-f', action='store_true', help='Whether the script can overwrite the destination given by --to.')
    parser.add_argument('--color', default='black', help='Color of the problem.')
    parser.add_argument('--contest', default='', help='Name of the contest, used only to generate the statement.')
    parser.add_argument('--save-tex', default='', help='If provided, the tex of the statement (only the statement itself, not a full working tex file) is saved into this path. This can be handy to generate the pdf for the complete problem set of a contest.')
    parser.add_argument('--only-tex', action='store_true', help='Whether only the tex (as described in the help section of --save-tex) should be generated without generating a DOMjudge package. This can be passed only if --save-tex is passed.')
    parser.add_argument('--override-time-limit', type=float, help='Override the time limit set in the polygon package with the value (in seconds) given with this argument.')
    parser.add_argument('--override-memory-limit', type=int, help='Override the memory limit set in the polygon package with the value (in MiB) given with this argument.')
    parser.add_argument('--hide-tl-ml', action='store_true', help='Whether the time limit and the memory limit shall be shown in the statement.') 
    parser.add_argument('--statements-template', default=os.path.join(RESOURCES_PATH, 'statements_template.tex'), help='Path of the LaTeX statements template.')
    parser.add_argument('--big-sample-size', type=int, default=BIG_SAMPLE_SIZE, help='Number of characters in the longest line of a sample which triggers the call of \'\\bigsample\' instead of \'\\sample\' in the tex source of the statement.')
    parser.add_argument('--update-testlib', action='store_true', help='Whether to update the local version of testlib (syncing it with the last version from the github repository).')
    parser.add_argument('--verbosity', choices=['debug', 'info', 'warning'],
                        default='info', help='Verbosity of the logs.')
    parser.add_argument('--keep-dirs', action='store_true', help='Whether the temporary directories created shall be kept or removed (useful for debugging).')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

    return parser

def parse_author_and_preparation(tutorial):
    lines = tutorial.splitlines()
    if not lines:
        return ('', '')

    author = ''
    preparation = ''

    for line in lines:
        line = line.strip()
        if line.startswith('%AUTHOR '):
            if author:
                console.warning('There are multiple lines in the tutorial starting with %AUTHOR.')
            author = line[len('%AUTHOR '):]
        if line.startswith('%PREPARATION '):
            if preparation:
                console.warning('There are multiple lines in the tutorial starting with %PREPARATION.')
            preparation = line[len('%PREPARATION '):]

    if not author:
        logging.warning('The AUTHOR line is not present in the tutorial section of the statement.')
    if not preparation:
        logging.warning('The PREPARATION line is not present in the tutorial section of the statement.')

    return (author, preparation)
    
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


def contains_long_line(args, filename):
    with open(filename) as f:
        lines = f.readlines()
        for line in lines:
            if len(line) > args.big_sample_size:
                return True
        return False

# Returns a string containing the tex source of the solution (only what shall
# go inside \begin{document} \end{document}).
# The images are copied in pdflatex_dir.
def generate_solution_tex(args, problem, pdflatex_dir):
    with open(os.path.join(RESOURCES_PATH, 'solution_template.tex')) as f:
        solution_template = f.read()

    replacements_solution = {
        'LABEL': problem['label'],
        'PROBLEM': problem['color'],
        'NAME': problem['name'],
        'AUTHOR': problem['author'],
        'PREPARATION': problem['preparation'],
        'SOLUTION': problem['statement']['tutorial']
    }
    for placeholder in replacements_solution:
        solution_template = solution_template.replace(
            '??%s??' % placeholder, str(replacements_solution[placeholder]))

    for image in problem['statement']['images']:
        # Giving a name depending on the problem label to the image so that
        # if the complete problem set of a contest is compiled in the same
        # directory no errors are generated because of images in different
        # problems with the exact same name (e.g., figure.png).
        image_unique_name = problem['label'] + '_' + image[0]
        solution_template = solution_template.replace(image[0], image_unique_name)
        shutil.copyfile(image[1], os.path.join(pdflatex_dir, image_unique_name))

    return solution_template

# Returns a string containing the tex of the statement (only what shall go
# inside \begin{document} \end{document}).
# The samples (.in/.out) and the images are copied in pdflatex_dir.
def generate_problem_tex(args, problem, pdflatex_dir):
    samples_tex = ''

    sample_id = 1
    for sample in problem['statement']['samples']:
        sample_path = (os.path.join(pdflatex_dir, problem['label']
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

    if sample_id == 1:
        logging.error('No samples found.')
        exit(1)

    with open(os.path.join(RESOURCES_PATH, 'problem_template.tex')) as f:
        problem_template = f.read()

    replacements_problem = {
        'LABEL': problem['label'],
        'PROBLEM': problem['color'],
        'NAME': problem['name'],
        'TIMELIMIT': problem['timelimit'],
        'MEMORYLIMIT': problem['memorylimit'],
        'SHOWTLML': '0' if args.hide_tl_ml else '1',
        'LEGEND': problem['statement']['legend'],
        'INPUT': problem['statement']['input'],
        'OUTPUT': problem['statement']['output'],
        'SAMPLES': samples_tex
    }
    for placeholder in replacements_problem:
        problem_template = problem_template.replace(
            '??%s??' % placeholder, str(replacements_problem[placeholder]))

    for image in problem['statement']['images']:
        # Giving a name depending on the problem label to the image so that
        # if the complete problem set of a contest is compiled in the same
        # directory no errors are generated because of images in different
        # problems with the exact same name (e.g., figure.png).
        image_unique_name = problem['label'] + '_' + image[0]
        problem_template = problem_template.replace(image[0], image_unique_name)
        shutil.copyfile(image[1], os.path.join(pdflatex_dir, image_unique_name))

    return problem_template


# Execute pdflatex on `from_` and copies the generated pdf document
# in the `to` path.
# from_ is a .tex file, to is a .pdf file.
def tex2pdf(from_, to):
    logging.info('Compiling \'%s\' into \'%s\' (pdflatex).' % (from_, to))
    if not from_.endswith('.tex'):
        logging.error('The argument from_=\'%s\' passed to tex2pdf is not a .tex file.')
        exit(1)
    
    from_dir = os.path.dirname(from_)
    from_name = os.path.basename(from_)[:-4]# Without extension
    command_as_list = ['pdflatex', '-interaction=nonstopmode',
                       '-output-dir=' + from_dir, '-jobname=%s' % from_name,
                       from_]
    logging.debug('pdflatex command = ' + ' '.join(command_as_list))
    pdflatex = subprocess.run(command_as_list, stdout=subprocess.PIPE,
                              shell=False)
    if pdflatex.returncode != 0:
        logging.error(' '.join(command_as_list) + '\n'
                      + pdflatex.stdout.decode("utf-8"))
        logging.error('The pdflatex command returned an error.')
        exit(1)

    shutil.copyfile(os.path.join(from_dir, from_name + '.pdf'), to)

def compile_statements_template(
        statements_template_path, contest, document_content, from_, to):
    replacements_statements = {
        'CONTEST': contest,
        'DOCUMENTCONTENT': document_content
    }
    with open(statements_template_path) as f:
        statements_template = f.read()

    for placeholder in replacements_statements:
        statements_template = statements_template.replace(
            '??%s??' % placeholder, str(replacements_statements[placeholder]))

    with open(from_, 'w') as f:
        f.write(statements_template)

    tex2pdf(from_, to)

# Produce the statement domjudge/problem.pdf.
def generate_problem_pdf(args, problem, domjudge):
    pdflatex_dir = tempfile.mkdtemp(
        prefix='%s-p2d-pdflatex' % problem['shortname'])
    logging.debug('Temporary directory for pdflatex: \'%s\'.' % pdflatex_dir)

    problem_tex = generate_problem_tex(args, problem, pdflatex_dir)

    compile_statements_template(args.statements_template, args.contest, problem_tex,
                                os.path.join(pdflatex_dir, 'statement.tex'),
                                os.path.join(domjudge, 'problem.pdf'))

    if not args.keep_dirs:
        shutil.rmtree(pdflatex_dir)


# Parsing a Polygon package to a Dictionary object.
#   args = arguments passed by the user
#   polygon = path of the root of the polygon package directory
#
# The returned dictionary has the following structure ('[]' denotes a list):
'''
color: string
label: string
shortname: string
name: string
timelimit: float (seconds)
memorylimit: int (MiB)
author: string
preparation: string

statement:
    legend: string
    input: string
    output: string
    samples: []
        in: string
        out: string
        is_long: boolean
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
def parse_problem_from_polygon(args, polygon):
    def pol_path(*path):
        return os.path.join(polygon, *path)

    logging.info('Parsing the polygon package directory \'%s\'.' % polygon)
    logging.debug('Parsing \'%s\'' % pol_path('problem.xml'))

    problem = {}

    # Metadata
    problem_xml = xml.etree.ElementTree.parse(pol_path('problem.xml'))
    problem['shortname'] = problem_xml.getroot().attrib['short-name']
    problem['name'] = problem_xml.find('names').find('name').attrib['value']
    problem['label'] = os.path.splitext(os.path.basename(args.domjudge))[0]
    problem['color'] = args.color
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
    
    if args.override_time_limit:
        problem['timelimit'] = args.override_time_limit

    if args.override_memory_limit:
        problem['memorylimit'] = args.override_memory_limit
    
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
        problem['author'], problem['preparation'] = \
                parse_author_and_preparation(statement_json['tutorial'])
        explanations = parse_samples_explanations(statement_json['notes'])

        sample_id = 1
        samples = []
        for sample_json in statement_json['sampleTests']:
            sample = {
                'in': pol_path('statements', 'english', sample_json['inputFile']),
                'out': pol_path('statements', 'english', sample_json['outputFile']),
                'explanation': explanations.get(sample_id)
            }
            sample['is_long'] = contains_long_line(args, sample['in']) \
                                or contains_long_line(args, sample['out'])
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

        for test in testset.iter('test'):
            t = {
                'num': test_id,
                'in': pol_path(input_format % local_id),
                'out': pol_path(output_format % local_id),
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

    if not problem['checker']['source'].endswith('.cpp'):
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


def p2d_problem(args):
    logging.basicConfig(
        stream=sys.stdout,
        format='%(levelname)s: %(message)s',
        level=eval('logging.' + args.verbosity.upper())
    )

    if not args.save_tex and args.only_tex:
        logging.error('The flag --only-tex can be passed only if --save-tex is specified.')
        exit(1)

    if args.domjudge.endswith('/'):
        args.domjudge = args.domjudge[:-1]

    if not re.fullmatch(r'[a-zA-Z0-9\-]+', pathlib.Path(args.domjudge).stem):
        logging.error('The name of the domjudge package '
                      + '(specified via --domjudge) '
                      + 'can contain only letters, numbers and '
                      + 'hyphens (spaces and underscores are not allowed).')
        exit(1)

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

    if args.save_tex:
        if not os.path.isdir(args.save_tex):
            logging.error('The directory \'%s\' passed through the command line argument \'--save-tex\' does not exist.' % args.save_tex)
            exit(1)
        args.save_tex = os.path.abspath(args.save_tex)
        problem_tex = generate_problem_tex(args, problem, args.save_tex)
        solution_tex = generate_solution_tex(args, problem, args.save_tex)

        with open(os.path.join(args.save_tex,
                               problem['label'] + '-statement.tex'),
                  'w') as f:
            f.write(problem_tex)
        with open(os.path.join(args.save_tex,
                               problem['label'] + '-solution.tex'),
                  'w') as f:
            f.write(solution_tex)

    # Create the domjudge directory.
    if not args.only_tex:
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

        # Create the domjudge zip if required.
        if args.domjudge.endswith('.zip'):
            logging.info('Zipping the DOMjudge package \'%s\'.' % args.domjudge)
            shutil.make_archive(args.domjudge[:-4], 'zip', domjudge)
            if not args.keep_dirs:
                shutil.rmtree(domjudge)

    logging.info('Converted \'%s\' to the DOMjudge format.'
                 % problem['shortname'])

    # Erase the unzipped polygon package if it were created.
    if zipfile.is_zipfile(args.polygon) and not args.keep_dirs:
        shutil.rmtree(polygon)

def main():
    args = prepare_argument_parser().parse_args()
    p2d_problem(args)

if __name__ == "__main__":
    main()

# TODO: 
#       Create tests for this tool.
#       Interactive problems are not supported.
