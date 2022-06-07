import json
import logging
import os
import pathlib
import re
import shutil
import sys
import tempfile
import zipfile
from argparse import ArgumentParser

from p2d._version import __version__
from p2d import generate_testlib_for_domjudge, parse_polygon_package, tex_utilities,                generate_domjudge_package
RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')

def prepare_argument_parser():
    parser = ArgumentParser(description='Convert Polygon Problem Package to DOMjudge Problem Package.')
    parser.add_argument('--polygon', '--from', required=True, help='Path of the polygon package. Can be either a directory or a zip.')
    parser.add_argument('--domjudge', '--to', required=True, help='Name of the domjudge package that will be created. Can be either a directory or a zip.')
    parser.add_argument('--force', '-f', action='store_true', help='Whether the script can overwrite the destination given by --to.')
    parser.add_argument('--label', default='?', help='Label of the problem.')
    parser.add_argument('--color', default='black', help='Color of the problem.')
    parser.add_argument('--contest', default='', help='Name of the contest, used only to generate the statement.')
    parser.add_argument('--save-tex', default='', help='If provided, the tex of the statement and of the solution (only the content of \begin{document}... \end{document}, not a full working tex file) are saved into this path as:\n\
      problem[\'name\']-statement.tex,\n\
      problem[\'name\']-solution.tex.')
    parser.add_argument('--only-tex', action='store_true', help='Whether only the tex (as described in the help section of --save-tex) should be generated without generating a DOMjudge package. This can be passed only if --save-tex is passed.')
    parser.add_argument('--override-time-limit', type=float, help='Override the time limit set in the polygon package with the value (in seconds) given with this argument.')
    parser.add_argument('--override-memory-limit', type=int, help='Override the memory limit set in the polygon package with the value (in MiB) given with this argument.')
    parser.add_argument('--hide-balloon', action='store_true', help='Whether the colored picture of a balloon shall be shown in the statement.') 
    parser.add_argument('--hide-tlml', action='store_true', help='Whether the time limit and the memory limit shall be shown in the statement.')
    parser.add_argument('--author', default='', help='Author of the problem.')
    parser.add_argument('--preparation', default='', help='The person (possibly more than one) who prepared the problem in polygon.')
    parser.add_argument('--update-testlib', action='store_true', help='Whether to update the local version of testlib (syncing it with the last version from the official github repository).')
    parser.add_argument('--verbosity', choices=['debug', 'info', 'warning'],
                        default='info', help='Verbosity of the logs.')
    parser.add_argument('--keep-dirs', action='store_true', help='Whether the temporary directories created shall be kept or removed (useful for debugging).')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

    return parser

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
    problem = parse_polygon_package.parse_problem_from_polygon(polygon)

    # The fact that the label is deduced from args.domjudge is bad.
    # It is a consequence that, possibly only in an old version of DOMjudge,
    # the label of the problem could be set only through the name of the zip file!
    # Moreover the name of the zip file was also important to decide the
    # externalid of the problem (or something similar).
    problem['label'] = args.label
    problem['color'] = args.color

    if args.override_time_limit:
        problem['timelimit'] = args.override_time_limit

    if args.override_memory_limit:
        problem['memorylimit'] = args.override_memory_limit

    problem['author'] = args.author
    problem['preparation'] = args.preparation

    if args.save_tex:
        if not os.path.isdir(args.save_tex):
            logging.error('The directory \'%s\' passed through the command line argument \'--save-tex\' does not exist.' % args.save_tex)
            exit(1)

        tex_dir = os.path.abspath(args.save_tex)
            
        problem_tex = tex_utilities.generate_problem_tex(problem, tex_dir)
        solution_tex = tex_utilities.generate_solution_tex(problem, tex_dir)

        with open(os.path.join(tex_dir, problem['name'] + '-statement.tex'),
                  'w') as f:
            f.write(problem_tex)
        with open(os.path.join(tex_dir, problem['name'] + '-solution.tex'),
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
        generate_domjudge_package.generate_domjudge_package(problem, domjudge, {
            'contest_name': args.contest,
            'hide_balloon': args.hide_balloon,
            'hide_tlml': args.hide_tlml
        })

        # Create the domjudge zip if required.
        if args.domjudge.endswith('.zip'):
            logging.info('Zipping the DOMjudge package \'%s\'.' % args.domjudge)
            shutil.make_archive(args.domjudge[:-4], 'zip', domjudge)
            if not args.keep_dirs:
                shutil.rmtree(domjudge)

    logging.info('Converted \'%s\' to the DOMjudge format.'
                 % problem['name'])

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

# TODO:
# In problem, it might be better to use name/title instead of shortname/name.
