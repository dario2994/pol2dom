import json
import logging
import os
import pathlib
import shutil
import string
import sys
import tempfile
import yaml
import zipfile
from argparse import ArgumentParser

from p2d._version import __version__
from p2d import (domjudge_api,
                 generate_domjudge_package,
                 generate_testlib_for_domjudge,
                 parse_polygon_package,
                 polygon_api,
                 tex_utilities)
RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')

# TODO
#  OK_SYMBOL = u'\u2705'
#  NEUTRAL_SYMBOL = '  '
#  ERROR_SYMBOL = u'\u274C'


def manage_download(config, polygon_dir, problem):
    if 'polygon_id' not in problem:
        logging.warning('Skipped because polygon_id is not specified.')
        return
    
    # Check versions
    local_version = problem.get('polygon_version', -1)
    latest_package = polygon_api.get_latest_package_id(
        config['polygon']['key'], config['polygon']['secret'], problem['polygon_id'])

    logging.debug('For problem %s the selected package is %s.'
                  % (problem['name'], latest_package[1]))

    if latest_package[0] == -1:
        logging.warning('No packages were found on polygon.')
        return

    if latest_package[0] < local_version:
        logging.warning('The local version is newer than the polygon version.')
        return

    if latest_package[0] == local_version:
        logging.info('The polygon package is up to date.')
        return

    pathlib.Path(polygon_dir).mkdir(exist_ok=True)
    
    # Download the package
    package_zip = os.path.join(polygon_dir, problem['name'] + '.zip')
    polygon_api.download_package(
        config['polygon']['key'], config['polygon']['secret'],
        problem['polygon_id'], latest_package[1], package_zip)

    # Unzip the package
    if not zipfile.is_zipfile(package_zip):
        logging.error(
            'There was an error downloading the package zip to \'%s\'.'
            % package_zip)
        return

    with zipfile.ZipFile(package_zip, 'r') as f:
        logging.debug('Unzipping the polygon package \'%s\'.' % package_zip)
        f.extractall(polygon_dir)

    logging.info('Downloaded and unzipped the polygon package into '
                 '\'%s\'.' % os.path.join(polygon_dir))
    problem['polygon_version'] = latest_package[0]

# Transforms the polygon package contained in polygon_dir (already extracted)
# into an equivalent domjudge package in domjudge_dir. In domjudge_dir the
# package is contained extracted, but also a zip of the package itself is
# present.
# Moreover, this function creates the two tex files:
#   tex_dir/problem['name']-statement.tex
#   tex_dir/problem['name']-solution.tex
def manage_convert(config, polygon_dir, domjudge_dir, tex_dir, problem):
    # Check versions
    polygon_version = problem.get('polygon_version', -1)
    domjudge_version = problem.get('domjudge_local_version', -1)

    if polygon_version == -1:
        logging.warning('The polygon package is not present locally.')
        return

    if polygon_version < domjudge_version:
        logging.warning('The version of the local domjudge package is more '
                        'up to date the the local polygon package.')
        return

    if polygon_version == domjudge_version:
        logging.info('The local domjudge package is already up to date.')
        return

    # Parse the polygon package
    problem_package = parse_polygon_package.parse_problem_from_polygon(polygon_dir)

    if problem_package['name'] != problem['name']:
        logging.error('The name of the problem does not coincide with the name of the problem in polygon, which is \'%s\'.' % problem_package['name'])
        exit(1)

    # Set some additional properties of the problem (not present in polygon)
    problem_package['label'] = problem.get('label', '?')
    problem_package['color'] = problem.get('color', 'Black')

    if 'override_time_limit' in problem:
        problem_package['timelimit'] = problem['override_time_limit']

    if 'override_memory_limit' in problem:
        problem_package['memorylimit'] = problem['override_memory_limit']

    problem_package['author'] = problem.get('author', '')
    problem_package['preparation'] = problem.get('preparation', '')

    
    missing_keys = list(filter(lambda key: key not in problem,
                               ['label', 'color', 'author', 'preparation']))
    if missing_keys:
        logging.warning('The keys %s are not set in config.yaml for this problem.' % missing_keys)

    logging.debug(json.dumps(problem_package, sort_keys=True, indent=4))

    # Generate the tex sources of statement and solution.
    problem_tex = tex_utilities.generate_statement_tex(problem_package, tex_dir)
    solution_tex = tex_utilities.generate_solution_tex(problem_package, tex_dir)

    statement_file = problem['name'] + '-statement-content.tex'
    solution_file = problem['name'] + '-solution-content.tex'
    
    with open(os.path.join(tex_dir, statement_file), 'w') as f:
        f.write(problem_tex)
    with open(os.path.join(tex_dir, solution_file), 'w') as f:
        f.write(solution_tex)

    # Generate the DOMjudge package.
    
    # The following three lines guarantee that in the end domjudge_dir
    # directory is empty.
    pathlib.Path(domjudge_dir).mkdir(exist_ok=True)
    shutil.rmtree(domjudge_dir)
    pathlib.Path(domjudge_dir).mkdir()

    generate_domjudge_package.generate_domjudge_package(
        problem_package, domjudge_dir, tex_dir,
        {
            'contest_name': config['contest_name'],
            'hide_balloon': config.get('hide_balloon', 0),
            'hide_tlml': config.get('hide_tlml', 0)
        })

    logging.info('Converted the polygon package to the DOMjudge package \'%s\'.',
                 domjudge_dir)

    # Zip the package
    # A temporary file is necessary since make_archive goes crazy if the .zip
    # belongs to the directory that must be compressed.
    with tempfile.NamedTemporaryFile(suffix='.zip', mode='w', encoding='utf-8') as f:
        shutil.make_archive(f.name[:-4], 'zip', domjudge_dir)
        shutil.copyfile(f.name, os.path.join(domjudge_dir, problem['name'] + '.zip'))
    problem['domjudge_local_version'] = polygon_version

def manage_domjudge(config, domjudge_dir, problem):
    # Check versions
    local_version = problem.get('domjudge_local_version', -1)
    server_version = problem.get('domjudge_server_version', -1)

    if local_version == -1:
        logging.warning('The DOMjudge package is not present locally.')
        return

    if local_version < server_version:
        logging.warning('The version of the DOMjudge package on the server is '
                        'more up to date than the local one.')
        return

    if local_version == server_version:
        logging.info('The DOMjudge package on the server is already up to date.')
        return

        
    # Adding the problem to the contest if it was not already done.
    if 'domjudge_id' not in problem:
        if not domjudge_api.add_problem_to_contest_api(problem, config['domjudge']):
            logging.error('There was an error while adding the problem '
                          'to the contest in the DOMjudge server.')
            return

    # Sending the problem package to the server.
    assert('domjudge_id' in problem and 'domjudge_externalid' in problem)
    zip_file = os.path.join(domjudge_dir, problem['name'] + '.zip')
    zip_file_copy = os.path.join(domjudge_dir,
                                 problem['domjudge_externalid'] + '.zip')
    shutil.copyfile(zip_file, zip_file_copy)
    
    if not domjudge_api.update_problem_api(
            zip_file_copy, problem['domjudge_externalid'], config['domjudge']):
        logging.error('There was an error while updating the problem '
                      'in the DOMjudge server.')
        return
            
    problem['domjudge_server_version'] = local_version

    logging.info('Updated the DOMjudge package on the server \'%s\', with externalid = \'%s\'.' % (config['domjudge']['server'], problem['domjudge_externalid']))
    
def prepare_argument_parser():
    parser = ArgumentParser(description='Utility script to import a whole contest from polygon into DOMjudge.')
    parser.add_argument('contest_directory', help='The directory containing the config.yaml file describing the contest. This directory will store also the polygon and DOMjudge packages.')
    parser.add_argument('--problem', help='Use this flag to pass the name of a problem if you want to execute the script on a single problem instead of all the problems.')
    parser.add_argument('--polygon', '--import', '--get', '--download', action='store_true', help='Whether the problem packages should be downloaded from Polygon. Otherwise only the packages already present in the system will be considered.')
    parser.add_argument('--convert', action='store_true', help='Whether the polygon packages should be converted to DOMjudge packages. Otherwise only the DOMjudge packages already present in the system will be considered.')
    parser.add_argument('--domjudge', '--export', '--send', '--upload', action='store_true', help='Whether the DOMjudge packages shall be uploaded to the DOMjudge instance specified in config.yaml.')
    parser.add_argument('--verbosity', choices=['debug', 'info', 'warning'],
                        default='info', help='Verbosity of the logs.')
    parser.add_argument('--no-cache', action='store_true', help='If set, the various steps (polygon, convert, domjudge) are run even if they would not be necessary (according to the caching mechanism).')
    parser.add_argument('--clear-dir', action='store_true', help='Whether to remove all the files and directory, apart from \'config.yaml\' from the contest directory (as a consequence, all the cache is deleted).')
    parser.add_argument('--update-testlib', action='store_true', help='Whether to update the local version of testlib (syncing it with the latest version from the official github repository and patching it for DOMjudge).')
    
    return parser

def p2d_contest(args):
    logging.basicConfig(
        stream=sys.stdout,
        format='%(levelname)s: %(message)s',
        level=eval('logging.' + args.verbosity.upper())
    )

    # Downloading and patching testlib.h if necessary.
    testlib_h = os.path.join(RESOURCES_PATH, 'testlib.h')
    if not os.path.isfile(testlib_h) or args.update_testlib:
        generate_testlib_for_domjudge.generate_testlib_for_domjudge(testlib_h)
        logging.info('The file testlib.h was successfully downloaded and patched. The local version can be found at \'%s\'.' % testlib_h)
    
    contest_dir = args.contest_directory
    config_yaml = os.path.join(contest_dir, 'config.yaml')

    if not os.path.isfile(config_yaml):
        logging.error('The file %s was not found.' % config_yaml)
        exit(1)
    with open(config_yaml, 'r') as f:
        try:
            config = yaml.safe_load(f)
            logging.debug(config)
        except yaml.YAMLError as exc:
            print(exc)
            exit(1)

    def save_config_yaml():
        with open(config_yaml, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    if args.clear_dir:
        # Remove the versions from config.yaml
        for problem in config['problems']:
            problem['polygon_version'] = -1
            problem['domjudge_local_version'] = -1
            problem['domjudge_server_version'] = -1

        save_config_yaml()

        # Delete the directories polygon/, domjudge/, tex/.
        for dir_name in ['polygon', 'domjudge', 'tex']:
            dir_path = os.path.join(contest_dir, dir_name)
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)

        logging.info('Deleted the content of \'%s\' apart from config.yaml.' % contest_dir)
        
    if args.polygon and ('polygon' not in config
                         or 'key' not in config['polygon']
                         or 'secret' not in config['polygon']):
        logging.error('The entries polygon:key and polygon:secret must be '
                      'present in config.yaml to download problems from polygon.')
        exit(1)

    if args.domjudge and ('domjudge' not in config
                         or 'contest_id' not in config['domjudge']
                         or 'server' not in config['domjudge']
                         or 'username' not in config['domjudge']
                         or 'password' not in config['domjudge']):
        logging.error('The entries domjudge:contest_id, domjudge:server, '
                      'domjudge:username, domjudge:password must be present '
                      'in config.yaml to download problems from polygon.')
        exit(1)

    if not args.polygon and not args.convert and not args.domjudge \
       and not args.clear_dir:
        logging.error('At least one of the flags --polygon, --convert, --domjudge, --clear is necessary.')
        exit(1)

    pathlib.Path(os.path.join(contest_dir, 'polygon')).mkdir(exist_ok=True)
    pathlib.Path(os.path.join(contest_dir, 'domjudge')).mkdir(exist_ok=True)
    pathlib.Path(os.path.join(contest_dir, 'tex')).mkdir(exist_ok=True)

    # Process the problems, one at a time.
    # For each problem some of the following operations are performed (depending
    # on the command line flags used to run the command):
    #  1. Download the polygon package (from polygon).
    #  2. Convert the polygon package to a DOMjudge package.
    #  3. Upload the DOMjudge package (to a running DOMjudge server).
    problem_selected_exists = False
    for problem in config['problems']:
        if args.problem and args.problem != problem['name']:
            continue
        problem_selected_exists = True
        print()
        print('\033[1m' + problem['name'] + '\033[0m') # Bold

        if 'label' not in problem:
            logging.warning('The problem does not have a label.')

        if args.polygon:
            if args.no_cache:
                problem['polygon_version'] = -1
            manage_download(
                config, os.path.join(contest_dir, 'polygon', problem['name']), problem)
            save_config_yaml()

        if args.convert:
            if args.no_cache:
                problem['domjudge_local_version'] = -1
            manage_convert(
                config,
                os.path.join(contest_dir, 'polygon', problem['name']),
                os.path.join(contest_dir, 'domjudge', problem['name']),
                os.path.join(contest_dir, 'tex'),
                problem)
            save_config_yaml()
            
        if args.domjudge:
            if args.no_cache:
                problem['domjudge_server_version'] = -1
            manage_domjudge(
                config, os.path.join(
                    contest_dir, 'domjudge', problem['name']), problem)
            save_config_yaml()

    if args.problem and not problem_selected_exists:
        logging.warning('The problem specified with --problem does not appear '
                        'in config.yaml.')
        return

    # Generate the pdfs of the full problemset and of the solutions.
    if args.problem:
        return

    pdf_generation_params = {
        'contest_name': config['contest_name'],
        'hide_balloon': config.get('hide_balloon', False),
        'hide_tlml': config.get('hide_tlml', False)
    }

    label_and_name = [(p['label'], p['name']) for p in config['problems']]
    label_and_name.sort()
    sorted_names = [p[1] for p in label_and_name]
    
    tex_utilities.generate_problemset_pdf(
            sorted_names,
            config.get('front_page_problemset'),
            os.path.join(contest_dir, 'tex'),
            pdf_generation_params)

    tex_utilities.generate_solutions_pdf(
            sorted_names,
            config.get('front_page_solutions'),
            os.path.join(contest_dir, 'tex'),
            pdf_generation_params)

    print()
    logging.info('Successfully generated \'%s\' and \'%s\'.' %
        (os.path.join(contest_dir, 'tex', 'problemset.tex'),
        os.path.join(contest_dir, 'tex', 'solutions.tex')))
    
def main():
    args = prepare_argument_parser().parse_args()
    p2d_contest(args)

if __name__ == "__main__":
    main()

# On error tracing and logging:
#
# For errors, use logging.error and exit(1) or raise an exception.
# For warnings, use logging.warning.
#
# For informations:
# - Use logging.info in this file (for useful information).
# - Use logging.debug in all other files (and for not-so-useful information
#   in this file.
#
#
# contest dir structure:
#
# config.yaml
# polygon/
#   problemname/
#       the content of the package.
#       problemname.zip = the zipped package itself.
# domjudge/
#   problemname/
#       the content of the package
#       problemname.zip = the zipped package itself
# tex/
#   samples/ (containing all the samples)
#   images/ (containing all the images, for statements and solutions)
#   problemset.pdf
#   solutions.pdf
#   For each problem:
#   problemname-statement.pdf
#   problemname-solution.pdf


# config.yaml structure:

#  contest_name: SWERC 2021-2022
#  front_page_problemset: frontpages/officialproblemset.pdf
#  front_page_solutions: frontpages/officialsolutions.pdf
#  hide_balloons: 0
#  hide_tlml: 0
#  polygon:
    #  key: ??
    #  secret: ??
#  domjudge:
    #  contest_id: swerc2021
    #  server: https://judge.swerc.eu
    #  username: dario2994
    #  password: ??
#  problems:
#  - name: fastlis # Must be the name used in polygon
  #  label: C
  #  color: CornflowerBlue # What are the valid colors?
  
  #  author: Federico Glaudo
  #  preparation: Federico Glaudo

  #  polygon_id: 193671

  #  override_memory_limit: 2048 # MiB
  #  override_time_limit: 3.5 # second

  #  domjudge_id: C-fastlis-OSCSRC # TODO: So domjudge_id = domjudge_externalid??
  #  domjudge_externalid: C-fastlis-OSCSRC

  #  polygon_version: 10
  #  domjudge_local_version: 9
  #  domjudge_server_version: 3

# TODO: Everything should be tested appropriately.
# TODO: The documentation must be updated.
# TODO: Use logging everywhere for the error printing (maybe it is already true).
# TODO: Use exceptions more when appropriate (maybe already done).
# TODO: Use - instead of _ in config.yaml (and everywhere else too).
# TODO: Use editorial.pdf (solutions.pdf is a bad name).
# TODO: The colors belong to what list?
# TODO: The path to the front pages, is relative to what?
# TODO: The contest_id is the external id or it is something else?
# TODO: --clear-domjudge-ids.
