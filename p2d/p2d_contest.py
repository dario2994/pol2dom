import logging
import os
import pathlib
import platform
import random
import requests
import shutil
import string
import subprocess
import sys
import tempfile
import yaml
from argparse import ArgumentParser
from . import p2d_problem

OK_SYMBOL = u'\u2705'
NEUTRAL_SYMBOL = '  '
ERROR_SYMBOL = u'\u274C'

def generate_externalid(problem):
    random_suffix = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))
    return problem['label'] + '-' + problem['name'] + '-' + random_suffix

def package_suffix():
    os_name = 'windows' if platform.system() == 'Windows' else 'linux'
    return '$%s.zip' % os_name

def find_latest_local_version(name, polygon):
    suffix = package_suffix()
    version = -1
    for f in os.listdir(polygon):
        prefix = name + '-'
        if f.startswith(name + '-') and f.endswith(suffix):
            maybe_version = f[len(prefix):-len(suffix)]
            if maybe_version.isdigit():
                version = max(version, int(f[len(prefix):-len(suffix)]))
    return version

def run_p2d_problem(
        name, old_local_version, label, color, contest, polygon, domjudge):
    local_version = find_latest_local_version(name, polygon)
    if local_version == -1:
        print(ERROR_SYMBOL, name, ':', 'Not found.')
        return old_local_version
    assert(local_version != -1)
    if old_local_version > local_version:
        print(ERROR_SYMBOL, name, ':', 'The latest polygon package found in \'%s\' is older than the latest DOMjudge package found in \'%s\'.' % (polygon, domjudge))
        return old_local_version
    assert(old_local_version <= local_version)

    args_list = \
        ['--from', os.path.join(polygon, '%s-%s%s'
                                         % (name, local_version, package_suffix())),
        '--to', os.path.join(domjudge, '%s.zip' % label),
        '--color', color,
        '--contest', contest,
        '--save-tex', os.path.join(domjudge, 'tex'),
        '--verbosity', 'warning',
        '--force']

    if local_version == old_local_version:
        args_list.append('--only-tex')
    
    args = p2d_problem.prepare_argument_parser().parse_args(args_list)

    try:
        p2d_problem.p2d_problem(args)
    except:
        print(ERROR_SYMBOL, name, ':', 'Error during the execution of p2d-problem with arguments %s.' % args)
        return old_local_version

    if local_version == old_local_version:
        print(NEUTRAL_SYMBOL, name, ':', 'Already up to date, not modified.')
    else:
        print(OK_SYMBOL, name, ':', 'Converted into \'%s\'.'
                                    % (os.path.join(domjudge, label + '.zip')))
    return local_version

def call_domjudge_api(config, api_address, data, files):
    res = requests.post(
        config['server'] + api_address,
        auth=requests.auth.HTTPBasicAuth(config['username'], config['password']),
        data=data,
        files=files)
    return res

def update_problem_api(zip_file, problem_id, config):
    api_address = '/api/v4/contests/%s/problems' % config['contest_id']
    
    with open(zip_file, 'rb') as f:
        res = call_domjudge_api(config, api_address, {'problem': problem_id},
                                {'zip': (zip_file, f)})

    if res.status_code != 200 or not res.json()['problem_id']:
        print(ERROR_SYMBOL, 'Error sending the package to the DOMjudge server:',
              res.json())
        return False
    else:
        print(OK_SYMBOL, 'Successfully sent the package to the DOMjudge server.')
        return True # res.json()['problem_id'] TODO

def add_problem_to_contest_api(problem, config):
    api_address = '/api/v4/contests/%s/problems/add-data' % config['contest_id']
    externalid = generate_externalid(problem)
    

    with tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='w',
                                     encoding='utf-8') as f:
        problem_yaml = f.name
        yaml.safe_dump([{'id': externalid, 'label': problem['label'], 'name': problem['name']}],
                       f, default_flow_style=False, sort_keys=False)

    with open(problem_yaml, 'rb') as f:
        res = call_domjudge_api(config, api_address, {}, {'data': (problem_yaml, f)})
    os.unlink(problem_yaml)

    if res.status_code != 200:
        print(ERROR_SYMBOL, 'Error adding the problem to the contest:',
              res.json())
        return False

    problem['id'] = res.json()[0]
    problem['externalid'] = externalid

    return True

def prepare_argument_parser():
    parser = ArgumentParser(description='Utility script to import a whole contest from polygon into domjudge.')
    parser.add_argument('--config', required=True, help='Yaml file describing the contest. It contains a list of the problems to convert (with some metadata). It contains also: where to find the Polygon packages, where to save the DOMjudge packages, how to access the DOMjudge server.')
    parser.add_argument('--ignore-local-version', action='store_true', help='All packages are generated.')
    parser.add_argument('--ignore-server-version', action='store_true', help='All packages are sent to the server.')
    parser.add_argument('--import', action='store_true', dest='import_', help='Whether the packages updated shall be imported into the domjudge server instance.')
    
    return parser

def generate_problemset_pdf(contest, labels, frontpage, domjudge):
    labels.sort()
    problemset_tex = ''

    if frontpage:
        frontpage = os.path.abspath(frontpage)
        problemset_tex += '\\includepdf{%s}\n' % frontpage
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    for label in labels:
        maybe_tex = os.path.join(domjudge, 'tex', label + '-statement.tex')
        if not os.path.isfile(maybe_tex):
            continue
        problemset_tex += '\\input{%s-statement.tex}\n' % label
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    # Executing pdflatex twice because otherwise the command
    # \insertblankpageifnecessary does not produce the correct output.
    for _ in range(2):
        p2d_problem.compile_statements_template(
                os.path.join(p2d_problem.RESOURCES_PATH, 'statements_template.tex'),
                contest, problemset_tex,
                os.path.join(domjudge, 'tex', 'problemset.tex'),
                os.path.join(domjudge, 'problemset.pdf'))

def generate_solutions_pdf(contest, labels, frontpage, domjudge):
    labels.sort()
    solutions_tex = ''

    if frontpage:
        frontpage = os.path.abspath(frontpage)
        solutions_tex += '\\includepdf{%s}\n\n' % frontpage

    for label in labels:
        maybe_tex = os.path.join(domjudge, 'tex', label + '-solution.tex')
        if not os.path.isfile(maybe_tex):
            continue
        solutions_tex += '\\input{%s-solution.tex}\n' % label
        solutions_tex += '\\clearpage\n'
    
    p2d_problem.compile_statements_template(
            os.path.join(p2d_problem.RESOURCES_PATH, 'statements_template.tex'),
            contest, solutions_tex,
            os.path.join(domjudge, 'tex', 'solutions.tex'),
            os.path.join(domjudge, 'solutions.pdf'))

def p2d_contest(args):
    with open(args.config, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(exc)
            exit(1)
    
    if 'polygon_dir' not in config or 'domjudge_dir' not in config:
        print(ERROR_SYMBOL, 'The yaml configuration file must have the entries \'polygon_dir\' and \'domjudge_dir\'.')
        exit(1)

    config['polygon_dir'] = os.path.expanduser(config['polygon_dir'])
    config['domjudge_dir'] = os.path.expanduser(config['domjudge_dir'])
    
    pathlib.Path(os.path.join(config['domjudge_dir'], 'tex')) \
            .mkdir(exist_ok=True)

    problems = config['problems']
    for p in problems:
        old_local_version = p['local_version'] if 'local_version' in p else -1
        if args.ignore_local_version:
            old_local_version = -1
        p['local_version'] = run_p2d_problem(
                p['name'], old_local_version, p['label'], p['color'],
                config['contest_name'],
                config['polygon_dir'], config['domjudge_dir'])

        if not args.import_: continue

        old_server_version = p['server_version'] if 'server_version' in p else -1
        if args.ignore_server_version:
            old_server_version = -1
        if p['local_version'] <= old_server_version: continue

        if 'id' not in p:
            if not add_problem_to_contest_api(p, config):
                continue
        assert('externalid' in p and 'id' in p)
        zip_file = os.path.join(config['domjudge_dir'], p['label'] + '.zip')
        zip_file_copy = os.path.join(config['domjudge_dir'],
                                     p['externalid'] + '.zip')
        os.rename(zip_file, zip_file_copy)
        
        if update_problem_api(zip_file_copy, p['id'], config):
            p['server_version'] = p['local_version']
        os.rename(zip_file_copy, zip_file)
    
    with open(args.config, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    generate_problemset_pdf(
            config['contest_name'], [p['label'] for p in problems],
            config.get('front_page_problemset'), config['domjudge_dir'])

    generate_solutions_pdf(
            config['contest_name'], [p['label'] for p in problems],
            config.get('front_page_solutions'), config['domjudge_dir'])

def main():
    args = prepare_argument_parser().parse_args()
    p2d_contest(args)

if __name__ == "__main__":
    main()

# Make the error printing uniform. Maybe using logging?
