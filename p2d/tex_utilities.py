import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from p2d._version import __version__
RESOURCES_PATH = os.path.join(
    os.path.split(os.path.realpath(__file__))[0], 'resources')


# Execute pdflatex on `from_` and copies the generated pdf document
# in the `to` file.
# from_ is a .tex file, to is a .pdf file.
def tex2pdf(from_, to):
    logging.debug('Compiling \'%s\' into \'%s\' (pdflatex).' % (from_, to))
    if not from_.endswith('.tex'):
        logging.error('The argument from_=\'%s\' passed to tex2pdf is not a .tex file.' % from_)
        exit(1)
    if not to.endswith('.pdf'):
        logging.error('The argument to=\'%s\' passed to tex2pdf is not a .pdf file.' % to)
        exit(1)
    
    from_dir = os.path.dirname(from_)
    from_name = os.path.basename(from_)[:-4] # Without extension
    command_as_list = ['pdflatex', '-interaction=nonstopmode', '--shell-escape',
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

    from_pdf = os.path.join(from_dir, from_name + '.pdf')
    if not os.path.isfile(to) or not os.path.samefile(from_pdf, to):
        shutil.copyfile(from_pdf, to)

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

    replacements_statement = {
        'LABEL': problem['label'],
        'COLOR': problem['color'],
        'TITLE': problem['title'],
        'TIMELIMIT': problem['timelimit'],
        'MEMORYLIMIT': problem['memorylimit'],
        'LEGEND': problem['statement']['legend'],
        'INPUT': problem['statement']['input'],
        'OUTPUT': problem['statement']['output'],
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
        statement_template = statement_template.replace(image[0], image_unique_name)
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
# 3. Save the resulting tex in from_;
# 4. Compile from_ into the pdf to.
#
# from_ is a .tex file, to is a .pdf file.
# params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def compile_document_template(document_content, from_, to, params):
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

    with open(from_, 'w') as f:
        f.write(document_template)

    tex2pdf(from_, to)

# Produces the statement (in pdf) of a problem in pdf_file.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_statement_pdf(problem, pdf_file, params):
    tex_dir = tempfile.mkdtemp(
        prefix='%s-p2d-pdflatex' % problem['name'])
    logging.debug('Temporary directory for pdflatex: \'%s\'.' % tex_dir)

    statement_tex = generate_statement_tex(problem, tex_dir)
    compile_document_template(statement_tex,
                              os.path.join(tex_dir, 'statement.tex'),
                              pdf_file,
                              params)

    # TODO: Handle debugging in some way
    #  if not args.keep_dirs:
        #  shutil.rmtree(tex_dir)

# Produces the solution (in pdf) of a problem in pdf_file.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_solution_pdf(problem, pdf_file, params):
    tex_dir = tempfile.mkdtemp(prefix='%s-p2d-pdflatex' % problem['name'])
    logging.debug('Temporary directory for pdflatex: \'%s\'.' % tex_dir)

    solution_tex = generate_solution_tex(problem, tex_dir)
    compile_document_template(solution_tex,
                                os.path.join(tex_dir, 'solution.tex'),
                                pdf_file,
                                params)

    # TODO: Handle debugging in some way
    #  if not args.keep_dirs:
        #  shutil.rmtree(tex_dir)

# Produces the complete problem set of a contest and saves it as
# tex_dir/problemset.pdf.
#   problems is a list of problem names, in the order they shall appear.
#   tex_dir must contain problem-statement.tex for each problem in problems.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_problemset_pdf(problems, frontpage, tex_dir, params):
    problemset_tex = ''

    if frontpage:
        frontpage = os.path.abspath(frontpage)
        problemset_tex += '\\includepdf{%s}\n' % frontpage
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    for problem in problems:
        maybe_tex = os.path.join(tex_dir, problem + '-statement.tex')
        if not os.path.isfile(maybe_tex):
            logging.warning('The tex source \'%s\' does not exist; but it is required to generate the pdf with all problems.' % maybe_tex)
            continue
        problemset_tex += '\\input{%s-statement.tex}\n' % problem
        problemset_tex += '\\insertblankpageifnecessary\n\n'

    # Executing pdflatex twice because otherwise the command
    # \insertblankpageifnecessary does not produce the correct output.
    for _ in range(2):
        compile_document_template(
                problemset_tex,
                os.path.join(tex_dir, 'problemset.tex'),
                os.path.join(tex_dir, 'problemset.pdf'),
                params)

# Produces the complete editorial of a contest and saves it as tex_dir/solutions.pdf.
#   problems is a list of problem names, in the order they shall appear.
#   tex_dir must contain problem-solution.tex for each problem in problems.
#   params is a dictionary with keys contest_name, hide_balloon, hide_tlml.
def generate_solutions_pdf(problems, frontpage, tex_dir, params):
    solutions_tex = ''
    
    if frontpage:
        frontpage = os.path.abspath(frontpage)
        solutions_tex += '\\includepdf{%s}\n\n' % frontpage

    for problem in problems:
        maybe_tex = os.path.join(tex_dir, problem + '-solution.tex')
        if not os.path.isfile(maybe_tex):
            logging.warning('The tex source \'%s\' does not exist; but it is required to generate the pdf with all solutions.' % maybe_tex)
            continue
        solutions_tex += '\\input{%s-solution.tex}\n' % problem
        solutions_tex += '\\clearpage\n'
    
    compile_document_template(
            solutions_tex,
            os.path.join(tex_dir, 'solutions.tex'),
            os.path.join(tex_dir, 'solutions.pdf'),
            params)
