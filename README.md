# pol2dom

Tool to set of problems prepared in [Polygon](https://polygon.codeforces.com/) into a [DOMjudge](https://www.domjudge.org/) contest.

The whole process is automated: downloading the Polygon package, converting it into a DOMjudge package (which is a descendant of the [Problem Package Format](https://icpc.io/problem-package-format/)), and uploading the DOMjudge package to a DOMjudge server.

This tool offers the command `p2d`.
Its main features are:

- Download, with a caching mechanism, the most recent Polygon package of a problem through polygon APIs.
- Upload, with a caching mechanism, the converted DOMjudge package of a problem into a DOMjudge server.
- Handling many problems as a contest
- Convert a Polygon package into a DOMjudge package without human intervention (with the possibility to tweak time and memory limit in the process).
- Generation of the statement in pdf with the option to add some custom features to it (e.g., the contest name, a balloon with the color of the problem, time limit and memory limit, etc..). The samples' explanations are [detected from the notes section in polygon through the use of special markers](#samples-explanation-detection).
- Generation of a pdf with the complete problem set of a contest featuring a custom front page. Same for the pdf of the solutions of the problems.
- Checkers using testlib.h are supported transparently (by using a modified `testlib.h` which is DOMjudge compatible).
- Through the `Judging verifier` feature of DOMjudge, it enforces that the submissions present in polygon get the correct result also in DOMjudge.

This project was born as a refactoring of [polygon2domjudge](https://github.com/cubercsl/polygon2domjudge) and evolved into something more.
It was used for [SWERC 2021-2022](https://swerc.eu/2021/about/).

## Installation
### Method 1: Install the Python package using `pipx`
The tool `pipx` is like `pip` (so it allows to install python packages in the local system) but uses virtual-environments transparently to avoid polluting the global python environment)

Run
```bash
$ pipx install git+https://github.com/dario2994/pol2dom
```
This provides you with the command `p2d` available in any shell terminal.

### Method 2: Run directly from the repository

Clone the repository with `git clone https://github.com/dario2994/pol2dom` and run the command with `bin/p2d.sh` directly from the repository directory.

## Usage

Running

```p2d contest_directory --polygon --convert --domjudge```

downloads the packages of the problems of the contest from polygon, converts them to DOMjudge packages, and uploads them to the DOMjudge server.
The list of the problems, as well as the credentials to access polygon and the DOMjudge server are contained in the configuration file `contest_directory/config.yaml`. The content and the format of `config.yaml` are described in [Structure of config.yaml](#structure-of-configyaml).

Let us describe the three, almost independent, operations that can be performed by `p2d`:

- `--polygon`: For each problem, download its latest valid package from polygon. A caching mechanism is employed to avoid downloading a package which is already up to date locally.
For this to work, `config.yaml` must contain the credentials to access polygon APIs.
For each problem, the directory `contest_directory/polygon/problem_name/` is generated. Such directory contains the polygon package (extracted) as well as its zip (named `problem_name.zip`).
- `--convert`: For each problem (which was previously, possibly during a different execution, downloaded from polygon), convert it to a DOMjudge package, setting also the information missing in polygon (i.e., the label, the color, the statement in pdf, possibly changing time and memory limit) as described in `config.yaml`. A caching mechanism is employed to avoid converting problems that were converted previously and whose polygon package did not change in the meanwhile.
For each problem, the directory `contest_directory/DOMjudge/problem_name` is generated. Such directory contains the DOMjudge package (extracted) as well as its zip (named `problem_name.zip`).
- `--domjudge`: For each problem, uploade its package to the DOMjudge server. A caching mechanism is employed to avoid uploading a package which is already up to date in the DOMjudge server.
For this to work, `config.yaml` must contain the credentials to access DOMjudge APIs.

Moreover, in `contest_directory/tex/` the full problem set `problemset.pdf` and the editorial of the contest `solutions.pdf` are generated (for the problems that were ever converted to a valid DOMjudge package by the command).
For each problem, also `contest_directory/tex/problem_name-statement.pdf` and `contest_directory/tex/problem_name-solution.pdf` are generated.

Additional flags:
- `--problem problem_name`: Process a single problem.
- `--no-cache`: Ignore the cache for a single run.
- `--clear-dir`: Clear the directory `contest_directory` (without removing `config.yaml`) and permanently delete the cache, use `--clear-dir`.
- `p2d --help`: Show a list of the available flags, with their descriptions.

## Structure of `config.yaml`

The file `config.yaml` must be present in the contest directory to instruct `p2d-contest` on the properties of the contest.
It must be a valid `yaml` file containing the following top-level keys:

TODO: This section is badly outdated.

- polygon_dir: The directory where the polygon packages shall be searched. It is handy to set it to the local Downloads folder, so that after downloading the packages from Polygon no further action is required.
- domjudge_dir: The directory where the DOMjudge packages shall be saved. The pdf of the whole problem set is saved in this directory too, with the name `problemset.pdf`.
- server: The URL of the DOMjudge instance (necessary only if you want to directly import the problems with `--send`).
- username: Username of an admin user of the DOMjudge instance (necessary only if you want to directly import the problems with `--send`).
- password: Password of the admin user (necessary only if you want to directly import the problems with `--send`).
- contest_id: Id of the contest in the DOMjudge instance (necessary only if you want to directly import the problems with `--send`).
- contest_name: Name of the contest, used to generate properly the pdf of the statements.
- front_page_problemset: The single-page pdf file to be used as front page of the problem set. This key is not mandatory, if it is not provided then the problem set will not have a front page.
- front_page_solutions: The single-page pdf file to be used as front page of the pdf with the solutions. This key is not mandatory, if it is not provided then the pdf with the solutions will not have a front page.
- problems: This is a list of problems. A problem is a dictionary with the following keys:
  - name: Short-name, in polygon, of the problem. This is used to find the polygon package in the directory specified by `--polygon`.
          So, if the name is `lis`, the tool will look for a file (in the directory `--polygon`) with name `lis-VERSION$windows.zip` or `lis-VERSION$linux.zip` (depending on the platform). Notice that this name format is exactly the one used by polygon, so after downloading the package no renaming is necessary.
  - label: The label used to identify the problem in the scoreboard (usually it is an uppercase letter).
  - color: Color of the problem in DOMjudge.
  - override_time_limit: Value (in seconds) of the time limit of the problem in DOMjudge. If this is present the value set in polygon is ignored.
  - override_memory_limit: Value (in MiB) of the memory limit of the problem in DOMjudge. If this is present the value set in polygon is ignored.
  - local-version: This key is created, and updated, by `p2d-contest`. It is the version of the latest Polygon package which was succesfully converted in a DOMjudge package.
  - server-version: This key is created, and updated, by `p2d-contest`. It is the version of the latest Polygon package which was succesfully imported into the DOMjudge instance.
  - id: This key is created by `p2d-contest`. It corresponds to the (numeric) id of the problem in the DOMjudge instance.
  - externalid: This key is created by `p2d-contest`. It corresponds to the (alphanumeric) id of the problem in the DOMjudge instance and it must be unique among all problems (it is generated appending a random string to the name of the problem).

*Example*: The following one is a valid `contest.yaml` file.

```
polygon_dir: ~/Downloads/
domjudge_dir: all_problems/
server: https://www.domjudge.org/demoweb/
username: admin
password: admin
contest_id: 123
contest_name: International Competition of Programmers
front_page_problemset: data/officialproblemset.pdf
front_page_solutions: data/solutions_frontpage.pdf
problems:
- name: maximum-subarray
  label: A
  color: red
- name: lis
  label: B
  color: purple
```

## Samples explanation detection

In polygon the explanation of samples (when present) is contained in the Notes section without a specific structure.
Since we want to parse the explanations "sample-wise", we need to add some structure.

The explanation of the i-th sample shall be preceded by the line `%BEGIN i` and followed by the line `%END`. For example:

```
BLAH BLAH BLAH

\textbf{Explanation of the first sample}
%BEGIN 1
There are $3$ people and...
%END

In the second sample
%BEGIN 2
there are $5$ people and...
%END
```

Notice that only the explanation itself shall be among the two magic lines, and not the title. The first letter of the explanation of each sample will be capitalized.


## Internal working of the generation of the LaTeX statement

We provide a description of the process which generates the tex source of the statement, so that if someone wants to customize the final result (by modifying `resources/statement_template.tex` or `resources/document_template.tex`) it should have no troubles doing it. The same applies for the LaTeX of the solutions (whose template is `resources/solution_template.tex`).

The statement is generated starting from `resources/statement_template.tex` by performing the following operations:

1. Replace the strings `??LABEL??`, `??TITLE??`, `??TIMELIMIT??`, `??MEMORYLIMIT??` with the corresponding metadata.
2. Replace the string `??LEGEND??`, `??INPUT??`, `??OUTPUT??` with the content of the corresponding sections in the polygon statement;
3. Generate an initially empty string `samples`.
For each problem sample, create two files `sample_id.in` and `sample_id.out` and append to the string `samples` the code `\sample{sample_id}`.
If the sample has an explanation (see [Samples explanation detection](#samples-explanation-detection)), append also `\sampleexplanation{Content of the sample explanation.}`.
4. Replace the string `??SAMPLES??` with the string `samples` generated in the previous step.

It is clear from the operations performed that `resources/statement_template.tex` contains the placeholders `??LABEL??`, `??TITLE??`, `??TIMELIMIT??`, `??MEMORYLIMIT??`, `??LEGEND??`, `??INPUT??`, `??OUTPUT??`, `??SAMPLES??`.

Then, the tex source code generated is inserted in `resources/document_template.tex` (by replacing the string `??DOCUMENTCONTENT??`). Finally the string `??CONTEST??` is replaced with the corresponding metadata (given by the argument `--contest`).

The tex file `resources/document_template.tex` implements the commands: `\problemlabel`, `\problemtitle`, `\timelimit`, `\memorylimit`, `\problemheader`, `\inputsection`, `\outputsection`, `\samplessection`, `\sample`, `\smallsample`, `\bigsample`, `\sampleexplanation`.
