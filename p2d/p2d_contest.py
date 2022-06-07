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
from p2d import polygon_api, p2d_problem, domjudge_api, tex_utilities


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
    # TODO: Check problem['name'] calling a polygon api?

    if latest_package[0] == -1:
        logging.warning('No packages were found on polygon.')
        return

    if latest_package[0] < local_version:
        logging.warning('The local version is newer than the polygon version')
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

# TODO: Should this call p2d_problem? Or something at a lower-level?
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

    # Prepare the p2d-problem command.
    pathlib.Path(domjudge_dir).mkdir(exist_ok=True)

    args_list = \
        ['--from', polygon_dir,
        '--to', domjudge_dir,
        '--label', problem.get('label', '?'),
        '--color', problem.get('color', 'Black'),
        '--contest', config['contest_name'],
        '--save-tex', tex_dir,
        '--verbosity', 'warning',
        '--force']

    # TODO: This shall be removed, but a --ignore-version flag shall be added
    #       so that if something is changed in config.yaml (e.g., contest name)
    #       the domjudge packages are generated in any case.
    #  if local_version == old_local_version:
        #  args_list.append('--only-tex')

    if 'override_time_limit' in problem:
        args_list.append('--override-time-limit')
        args_list.append(str(problem['override_time_limit'])) # in seconds

    if 'override_memory_limit' in problem:
        args_list.append('--override-memory-limit')
        args_list.append(str(problem['override_memory_limit'])) # in MiB

    if config.get('hide_balloon', 0):
        args_list.append('--hide-balloon')
    
    if config.get('hide_balloon', 0):
        args_list.append('--hide-tlml')
    
    args = p2d_problem.prepare_argument_parser().parse_args(args_list)

    # Run p2d-problem.
    try:
        # This is lengthy in order to have the proper level of logging.
        logging_level = logging.root.getEffectiveLevel()

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        p2d_problem.p2d_problem(args)

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(
            stream=sys.stdout,
            format='%(levelname)s: %(message)s',
            level=logging_level
        )        
    except:
        logging.error(
            'Error during the execution of p2d-problem with arguments %s.' % args)
        raise

    logging.info('Converted the polygon package to the DOMjudge package \'%s\'',
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

    logging.info('Updated the DOMjudge package on the server \'%s\', with externalid = \'%s\'' % (config['domjudge']['server'], problem['domjudge_externalid']))
    
def prepare_argument_parser():
    parser = ArgumentParser(description='Utility script to import a whole contest from polygon into DOMjudge.')
    parser.add_argument('contest_directory', help='The directory containing the config.yaml file describing the contest. This directory will store also the polygon and DOMjudge packages.')
    parser.add_argument('--problem', help='Use this flag to pass the name of a problem if you want to execute the script on a single problem instead of all the problems.')
    parser.add_argument('--polygon', '--import', '--get', '--download', action='store_true', help='Whether the problem packages should be downloaded from Polygon. Otherwise only the packages already present in the system will be considered.')
    parser.add_argument('--convert', action='store_true', help='Whether the polygon packages should be converted to DOMjudge packages. Otherwise only the DOMjudge packages already present in the system will be considered.')
    parser.add_argument('--domjudge', '--export', '--send', '--upload', action='store_true', help='Whether the DOMjudge packages shall be uploaded to the DOMjudge instance specified in config.yaml.')
    parser.add_argument('--verbosity', choices=['debug', 'info', 'warning'],
                        default='info', help='Verbosity of the logs.')
    parser.add_argument('--no-cache', action='store_true', help='If set, the various steps (polygon, convert, domjudge) are run even they would not be necessary taking into account the cache.')
    #  parser.add_argument('--ignore-local-version', action='store_true', help='All packages are generated.')
    #  parser.add_argument('--ignore-server-version', action='store_true', help='All packages are sent to the server.')
    
    return parser

def p2d_contest(args):
    logging.basicConfig(
        stream=sys.stdout,
        format='%(levelname)s: %(message)s',
        level=eval('logging.' + args.verbosity.upper())
    )
    
    contest_dir = args.contest_directory
    config_yaml = os.path.join(contest_dir, 'config.yaml')

    if not os.path.isfile(config_yaml):
        logging.error('The file %s was not found.' % config_yaml)
        exit(1)
    with open(config_yaml, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(exc)
            exit(1)

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

    if not args.polygon and not args.convert and not args.domjudge:
        logging.error('At least one of the flags --polygon, --convert, --domjudge '
                      'is necessary.')
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
    problems = config['problems']
    for problem in problems:
        if args.problem and args.problem != problem['name']:
            continue
        problem_selected_exists = True
        print('\033[1m' + problem['name'] + '\033[0m') # Bold

        if 'label' not in problem:
            logging.warning('The problem does not have a label.')

        if args.polygon:
            if args.no_cache:
                problem['polygon_version'] = -1
            manage_download(
                config, os.path.join(contest_dir, 'polygon', problem['name']), problem)

        if args.convert:
            if args.no_cache:
                problem['domjudge_local_version'] = -1
            manage_convert(
                config,
                os.path.join(contest_dir, 'polygon', problem['name']),
                os.path.join(contest_dir, 'domjudge', problem['name']),
                os.path.join(contest_dir, 'tex'),
                problem)
            
        if args.domjudge:
            if args.no_cache:
                problem['domjudge_server_version'] = -1
            manage_domjudge(
                config, os.path.join(
                    contest_dir, 'domjudge', problem['name']), problem)

    if args.problem and not problem_selected_exists:
        logging.warning('The problem specified with --problem does not appear '
                        'in config.yaml.')
        return
    
    # Save the updated config.yaml.
    with open(config_yaml, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    # Generate the pdfs of the full problemset and of the solutions.
    if args.problem:
        return

    pdf_generation_params = {
        'contest_name': config['contest_name'],
        'hide_balloon': config.get('hide_balloon', False),
        'hide_tlml': config.get('hide_tlml', False)
    }

    label_and_name = [(p['label'], p['name']) for p in problems]
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

def main():
    args = prepare_argument_parser().parse_args()
    p2d_contest(args)

if __name__ == "__main__":
    main()

# TODO:
# Make the error printing uniform. Maybe using logging.
#
# Show uploading status in a progress bar.
#
# Generate also per-problem statement and editorial (useful to upload it on the
# website after the contest ends).
#
# Download the package directly from polygon if updated. Polygon API now allow
# to specify the type of the package (which shall be linux!). This would make
# the tool entirely automatic.

# contest dir structure:
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
#   editorial.pdf
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
# TODO: The logging should be per-file, so that when p2d_contest calls
#       p2d_problem is not a mess to get everything right.
# TODO: Use logging everywhere for the error printing (maybe it is already true).
# TODO: Samples and images should use problem['name'], not problem['label'],
#       unless such a choice generates errors because latex does not support
#       non-letters in the name of files to be included.
# TODO: The samples should be put in a subdirectory of tex/. Same for the images.
# TODO: Use exceptions more when appropriate.
# TODO: The logic of p2d-contest calling p2d-problem for the conversion should
#       be thought better (but most likely, it is good as it is now).
