import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import logging

from p2d._version import __version__
RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')


# Execute pdflatex on tex_file.
# tex_file is a .tex file
def tex2pdf(tex_file):
    logging.debug('Executing pdflatex on \'%s\'.' % tex_file)
    if not tex_file.endswith('.tex'):
        logging.error('The argument tex_file=\'%s\' passed to tex2pdf is not a .tex file.' % tex_file)
        exit(1)
    
    tex_dir = os.path.dirname(tex_file)
    tex_name = os.path.basename(tex_file)[:-4] # Without extension
    command_as_list = ['pdflatex', '-interaction=nonstopmode', '--shell-escape',
                       '-output-dir=' + tex_dir, '-jobname=%s' % tex_name,
                       tex_file]
    logging.debug('pdflatex command = ' + ' '.join(command_as_list))
    pdflatex = subprocess.run(command_as_list, stdout=subprocess.PIPE,
                              shell=False)
    if pdflatex.returncode != 0:
        logging.error(' '.join(command_as_list) + '\n'
                      + pdflatex.stdout.decode("utf-8"))
        logging.error('The pdflatex command returned an error.')
        exit(1)

    tex_pdf = os.path.join(tex_dir, tex_name + '.pdf')

# Returns a string containing the tex of the statement (only what shall go
# inside \begin{document} \end{document}).
# The samples (.in/.out) and the images are copied in tex_dir/samples and
# tex_dir/images respectively.
def generate_statement_tex(problem, tex_dir):
    pathlib.Path(os.path.join(tex_dir, 'samples')).mkdir(exist_ok=True)
    pathlib.Path(os.path.join(tex_dir, 'images')).mkdir(exist_ok=True)
    
    samples_tex = ''

    sample_cnt = 0
    for sample in problem['statement']['samples']:
        sample_cnt += 1

        sample_path = os.path.join(tex_dir, 'samples',
                                   problem['name'] + '-' + str(sample_cnt))

        shutil.copyfile(sample['in'], sample_path + '.in')
        shutil.copyfile(sample['out'], sample_path + '.out')

        samples_tex += '\\sample{%s}\n' % sample_path

        if sample['explanation']:
            samples_tex += '\\sampleexplanation{%s}\n' % sample['explanation']

    if sample_cnt == 0:
        logging.error('No samples found.')
        exit(1)

    with open(os.path.join(RESOURCES_PATH, 'statement_template.tex')) as f:
        statement_template = f.read()
    
    # Some of these sections may be empty, in that case remove them.
    for section_title in ['input', 'output', 'interaction']:
        section_content = problem['statement'][section_title]
        if section_content is None or str(section_content).strip() == '':
            statement_template = statement_template.replace(
                '\\section*{%s}' % section_title.capitalize(), ''
            )

    replacements_statement = {
        'LABEL': problem['label'],
        'COLOR': problem['color'],
        'TITLE': problem['title'],
        'TIMELIMIT': problem['timelimit'],
        'MEMORYLIMIT': problem['memorylimit'],
        'LEGEND': problem['statement']['legend'],
        'INPUT': problem['statement']['input'],
        'OUTPUT': problem['statement']['output'],
        'INTERACTION': problem['statement']['interaction'],
        'SAMPLES': samples_tex
    }
    for placeholder in replacements_statement:
        statement_template = statement_template.replace(
            '??%s??' % placeholder, str(replacements_statement[placeholder]))

    for image in problem['statement']['images']:
        # Giving a name depending on the problem name to the image to avoid
        # collisions with images of other statements/solutions.
        image_unique_name = os.path.join(
            'images', problem['name'] + '-' + image[0])
        statement_template = statement_template.replace(
            '{' + image[0] + '}', 
            '{' + image_unique_name + '}')
        shutil.copyfile(image[1], os.path.join(tex_dir, image_unique_name))

    return statement_template


# Returns a string containing the tex source of the solution (only what shall
# go inside \begin{document} \end{document}).
# The images are copied in tex_dir/images.
def generate_solution_tex(problem, tex_dir):
    with open(os.path.join(RESOURCES_PATH, 'solution_template.tex')) as f:
        solution_template = f.read()

    replacements_solution = {
        'LABEL': problem['label'],
        'COLOR': problem['color'],
        'TITLE': problem['title'],
        'AUTHOR': problem['author'],
        'PREPARATION': problem['preparation'],
        'SOLUTION': problem['statement']['tutorial']
    }
    for placeholder in replacements_solution:
        solution_template = solution_template.replace(
            '??%s??' % placeholder, str(replacements_solution[placeholder]))

    for image in problem['statement']['images']:
        # Giving a name depending on the problem name to the image to avoid
        # collisions with images of other statements/solutions.
        image_unique_name = os.path.join(
            'images', problem['name'] + '-' + image[0])
        solution_template = solution_template.replace(image[0], image_unique_name)
        shutil.copyfile(image[1], os.path.join(tex_dir, image_unique_name))

    return solution_template


# Function to transform the statement of one or more problems (the content of
# \begin{document} ... \end{document}) into a pdf file.
#
# It performs the following operations:
# 1. Fill document_template.tex document tag with document_content;
# 2. Replace the placeholders in params using params;
# 3. Save the resulting tex in tex_file;
# 4. Compile tex_file. If tex_file = 'path/name.tex', the pdf file produced is
#    'path/name.pdf'.
#
# params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def compile_document_template(document_content, tex_file, params):
    replacements_document = {
        'CONTESTNAME': params['contest_name'],
        'SHOWBALLOON': 0 if params['hide_balloon'] else 1,
        'SHOWTLML': 0 if params['hide_tlml'] else 1,
        'DOCUMENTCONTENT': document_content
    }
    with open(os.path.join(RESOURCES_PATH, 'document_template.tex')) as f:
        document_template = f.read()

    for placeholder in replacements_document:
        document_template = document_template.replace(
            '??%s??' % placeholder, str(replacements_document[placeholder]))

    with open(tex_file, 'w') as f:
        f.write(document_template)

    tex2pdf(tex_file)

# Produces problemname-statement.{tex,pdf}, which are respectively the tex source
# and the pdf of the statement, in the directory tex_dir.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_statement_pdf(problem, tex_dir, params):
    statement_tex = generate_statement_tex(problem, tex_dir)
    compile_document_template(
        statement_tex,
        os.path.join(tex_dir, problem['name'] + '-statement.tex'),
        params)

# Produces problemname-solution.{tex,pdf}, which are respectively the tex source
# and the pdf of the solution, in the directory tex_dir.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_solution_pdf(problem, tex_dir, params):
    solution_tex = generate_solution_tex(problem, tex_dir)
    compile_document_template(
        solution_tex,
        os.path.join(tex_dir, problem['name'] + '-solution.tex'),
        params)

# Produces the complete problem set of a contest and saves it as
# tex_dir/statements.pdf.
#   problems is a list of problem names, in the order they shall appear.
#   tex_dir must contain problem-statement-content.tex for each problem in
#   problems.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_statements_pdf(problems, frontpage, tex_dir, params):
    problemset_tex = ''

    if frontpage:
        frontpage = os.path.abspath(frontpage)
        problemset_tex += '\\includepdf{%s}\n' % frontpage
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    for problem in problems:
        maybe_tex = os.path.join(tex_dir, problem + '-statement-content.tex')
        if not os.path.isfile(maybe_tex):
            logging.warning('The tex source \'%s\' does not exist; but it is required to generate the pdf with all problems.' % maybe_tex)
            continue
        problemset_tex += '\\input{%s-statement-content.tex}\n' % problem
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    # Executing pdflatex twice because otherwise the command
    # \insertblankpageifnecessary does not produce the correct output.
    for _ in range(2):
        compile_document_template(
                problemset_tex,
                os.path.join(tex_dir, 'statements.tex'),
                params)

# Produces the complete editorial of a contest and saves it as tex_dir/solutions.pdf.
#   problems is a list of problem names, in the order they shall appear.
#   tex_dir must contain problemname-solution-content.tex for each problem
#   in problems.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_solutions_pdf(problems, frontpage, tex_dir, params):
    solutions_tex = ''
    
    if frontpage:
        frontpage = os.path.abspath(frontpage)
        solutions_tex += '\\includepdf{%s}\n\n' % frontpage

    for problem in problems:
        maybe_tex = os.path.join(tex_dir, problem + '-solution-content.tex')
        if not os.path.isfile(maybe_tex):
            logging.warning('The tex source \'%s\' does not exist; but it is required to generate the pdf with all solutions.' % maybe_tex)
            continue
        solutions_tex += '\\input{%s-solution-content.tex}\n' % problem
        solutions_tex += '\\clearpage\n'
    
    compile_document_template(
            solutions_tex,
            os.path.join(tex_dir, 'solutions.tex'),
            params)
