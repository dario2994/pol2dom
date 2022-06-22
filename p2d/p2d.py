import logging
import os
import pathlib
import sys
from argparse import ArgumentParser

from p2d._version import __version__
from p2d import (domjudge_api,
                 generate_domjudge_package,
                 generate_testlib_for_domjudge,
                 parse_polygon_package,
                 polygon_api,
                 p2d_utils,
                 tex_utilities)
RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')

    
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
    parser.add_argument('--clear-dir', action='store_true', help='If set, problems\' data in the contest directory is deleted (as a consequence, the cache is deleted). The file \'config.yaml\' is not deleted.')
    parser.add_argument('--clear-domjudge-ids', action='store_true', help='If set, the domjudge IDs saved in config.yaml (for the problems that were uploaded to the DOMjudge server) are deleted. As a consequence, next time the flag `--domjudge` is passed, the problems will be uploaded as new problems to DOMjudge. This should be used either if the DOMjudge server changed, if the DOMjudge contest changed, or if the problems were deleted in the DOMjudge server.')
    parser.add_argument('--update-testlib', action='store_true', help='Whether to update the local version of testlib (syncing it with the latest version from the official github repository and patching it for DOMjudge).')
    
    return parser


def p2d(args):
    p2d_utils.configure_logging(args.verbosity)

    # Downloading and patching testlib.h if necessary.
    testlib_h = os.path.join(RESOURCES_PATH, 'testlib.h')
    if not os.path.isfile(testlib_h) or args.update_testlib:
        generate_testlib_for_domjudge.generate_testlib_for_domjudge(testlib_h)
        logging.info('The file testlib.h was successfully downloaded and patched. The local version can be found at \'%s\'.' % testlib_h)
    
    contest_dir = args.contest_directory

    config = p2d_utils.load_config_yaml(contest_dir)

    p2d_utils.validate_config_yaml(config)

    if args.clear_dir:
        for problem in config['problems']:
            if args.problem and args.problem != problem['name']:
                continue
            p2d_utils.remove_problem_data(problem, contest_dir)

        p2d_utils.save_config_yaml(config, contest_dir)
        logging.info('Deleted the problems\' data from \'%s\'.' % contest_dir)

    if args.clear_domjudge_ids:
        for problem in config['problems']:
            if args.problem and args.problem != problem['name']:
                continue
            problem['domjudge_server_version'] = -1
            problem.pop('domjudge_id', None)

        p2d_utils.save_config_yaml(config, contest_dir)
        logging.info('Deleted the DOMjudge IDs from config.yaml.')
        
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
       and not args.clear_dir and not args.clear_domjudge_ids:
        logging.error('At least one of the flags --polygon, --convert, --domjudge, --clear-dir, --clear-domjudge-ids is necessary.')
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
        if not args.polygon and not args.convert and not args.domjudge:
            continue

        problem_selected_exists = True
        print()
        print('\033[1m' + problem['name'] + '\033[0m') # Bold

        if 'label' not in problem:
            logging.warning('The problem does not have a label.')

        if args.polygon:
            if args.no_cache:
                problem['polygon_version'] = -1
            p2d_utils.manage_download(
                config, os.path.join(contest_dir, 'polygon', problem['name']), problem)
            p2d_utils.save_config_yaml(config, contest_dir)

        if args.convert:
            if args.no_cache:
                problem['domjudge_local_version'] = -1
            p2d_utils.manage_convert(
                config,
                os.path.join(contest_dir, 'polygon', problem['name']),
                os.path.join(contest_dir, 'domjudge', problem['name']),
                os.path.join(contest_dir, 'tex'),
                problem)
            p2d_utils.save_config_yaml(config, contest_dir)
            
        if args.domjudge:
            if args.no_cache:
                problem['domjudge_server_version'] = -1
            p2d_utils.manage_domjudge(
                config, os.path.join(
                    contest_dir, 'domjudge', problem['name']), problem)
            p2d_utils.save_config_yaml(config, contest_dir)

    if args.problem and not problem_selected_exists:
        logging.warning('The problem specified with --problem does not appear '
                        'in config.yaml.')
        return

    if args.problem:
        return

    p2d_utils.generate_problemset_solutions(config, contest_dir)

# Guidelines for error tracing and logging:
#
# Use logging everywhere for info/warning/error printing.
# Do not use print.
# Use exceptions when appropriate.
#
# For errors, use logging.error followed by exit(1) or raise an exception.
# For warnings, use logging.warning.
#
# For information:
# - Use logging.info in this p2d.py (for useful information).
# - Use logging.debug in all other files (and for not-so-useful information
#   in this file).
def main():
    args = prepare_argument_parser().parse_args()
    p2d(args)

if __name__ == "__main__":
    main()


# TODO: Everything should be tested appropriately.
# TODO: Handle better the logic for generating the problemset and the solutions.
#       Here is a proposal:
#           Add a flag, like --problemset or --editorial (or a single flag for
#           both) which generates the problemset and the editorial.
#           The problem_name-statement-content.tex are still generated all the
#           time (and the pdf of single statements and single solutions are
#           still generated all the time).
# TODO: Add the support for interactive problems.
