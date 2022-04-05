# pol2dom

Tool to import a problem/contest prepared in [Polygon](https://polygon.codeforces.com/) into a [DOMjudge](https://www.domjudge.org/) instance.

This tool, offers two commands: `p2d-problem` and `p2d-contest`.

- `p2d-problem` converts a Polygon (full) package into a DOMjudge package (which is a descendant of the [Problem Package Format](https://icpc.io/problem-package-format/)).
- `p2d-contest` handles the conversion of a whole problem set, its import into a DOMjudge instance, the generation of the pdf of the whole problem set, the generation of the solutions of the whole problem set.

The main features are:

- The conversion from a Polygon package into a DOMjudge package is fully automatic and requires no human intervention.
- Parses the statement from the Polygon package and generates the statement in pdf (with the possibility of [customizing the LaTeX template](#customization-of-the-latex-statement-template)). The samples' explanations are [detected from the notes section in polygon through the use of special markers](#samples-explanation-detection).
- Can generate a pdf with the complete problem set of a contest featuring a custom front page.
- Can generate a pdf with the solutions of a contest featuring a custom front page. In the solutions, the author of the problem and the person who prepared it are mentioned (see the section [Author Detection](#author-detection)).
- Checkers using testlib.h are supported transparently (by using a modified testlib.h which is DOMjudge compatible).
- Through the `Judging verifier` feature of DOMjudge, it enforces that the submissions present in polygon get the correct result also in DOMjudge.
- Through DOMjudge APIs, it imports the problems (if updated) directly into the DOMjudge instance.

This project was born as a refactoring of [polygon2domjudge](https://github.com/cubercsl/polygon2domjudge) and evolved into something more.

## Usage

### p2d-problem

Running

```p2d-problem --contest "CONTEST NAME" --color "COLOR NAME" --from polygon_package --to domjudge_package```

converts the Polygon problem package `polygon_package` into an equivalent DOMjudge problem package `domjudge_package`.
The name of the file `domjudge_package` corresponds to the label used to identify the problem in DOMjudge.
The arguments `polygon_package` and `domjudge_package` can be either folders or zip files.

The polygon package must be a *full* package, i.e., it must contain the generated tests.

*Example*: `p2d-problem --contest "SWERC 2022" --color red --from my_problems/sum-integers.zip --to C.zip`.

Use `p2d-problem --help` for a guide.

### p2d-contest

Running 

```p2d-contest --config contest.yaml --import```

searches the latest package of the problems specified in `contest.yaml` in `polygon_dir` (specified in `contest.yaml`); converts them into DOMjudge packages in `domjudge_dir` (specified in `contest.yaml`) updating previous versions; and imports, through the APIs, the updated packages into the DOMjudge instance specified in `contest.yaml`. Moreover, it creates the document `domjudge_dir/problemset.pdf` containing all the problem statements. It is possible to use a custom front page for the problem set pdf through the argument `--front-page`.

The content and the format of `contest.yaml` are described in [Structure of contest.yaml](#structure-of-contestyaml).

Use `p2d-contest --help` for a guide.

*Example*: `p2d-contest --config swerc.yaml --import`.

## Installation
### Method 1: Install the Python package using `pipx`
The tool `pipx` is like `pip` (so it allows to install python packages in the local system) but uses virtual-environments transparently to avoid polluting the global python environment)

Run
```bash
$ pipx install git+https://github.com/dario2994/pol2dom
```
This provides you with the commands `p2d-problem` and `p2d-contest` available in any shell terminal.

### Method 2: Run directly from the repository

Clone the repository with `git clone https://github.com/dario2994/pol2dom` and run the commands with `bin/p2d-problem.sh` and `bin/p2d-contest.sh` directly from the repository folder.

## Customization of the LaTeX statement template

The statement is generated starting from `resources/problem_template.tex` by performing the following operations:

1. Replace the strings `??LABEL??`, `??NAME??`, `??TIMELIMIT??`, `??MEMORYLIMIT??` with the corresponding metadata.
2. Replace the string `??LEGEND??`, `??INPUT??`, `??OUTPUT??` with the content of the corresponding sections in the polygon statement;
3. Generate an initially empty string `samples`.
For each problem sample, create two files `sample_id.in` and `sample_id.out` and append to the string `samples` the code `\sample{sample_id}` or `\bigsample{sample_id}`. The command `\bigsample` is used if there is a line in `sample_id.in` or `sample_id.out` longer than `BIG_SAMPLE_CHARS_NUM=40` characters (the value of `BIG_SAMPLE_CHARS_NUM` can be configured via `--big_sample_chars_num`), so that big samples can have a different formatting if desired.
If the sample has an explanation (see [Samples explanation detection](#samples-explanation-detection)), append also `\sampleexplanation{Content of the sample explanation.}`.
4. Replace the string `??SAMPLES??` with the string `samples` generated in the previous step.

It is clear from the operations performed that `resources/problem_template.tex` contains the placeholders `??LABEL??`, `??NAME??`, `??TIMELIMIT??`, `??MEMORYLIMIT??`, `??LEGEND??`, `??INPUT??`, `??OUTPUT??`, `??SAMPLES??`.

Then, the tex source code generated is inserted in `resources/statements_template.tex` (by replacing the string `??DOCUMENTCONTENT??`). Finally the string `??CONTEST??` is replaced with the corresponding metadata (given by the argument `--contest`).

The tex file `resources/statements_template.tex` implements the commands: `\problemlabel`, `\problemtitle`, `\timelimit`, `\memorylimit`, `\problemheader`, `\inputsection`, `\outputsection`, `\samplessection`, `\sample`, `\bigsample`, `\sampleexplanation`.

If you want to customize the visual aspect of the generated pdf, use the command argument `--statements_template 'my_statements_template.tex'` (it will be used instead of `resources/statements_template.tex`).

## Samples explanation detection

In polygon the explanation of samples (when present) is contained in the Notes section without a specific structure.
Since we want to parse explanation "sample-wise", we need to add some structure.

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

## Author Detection

In order to include in the booklet with the solutions the names of those who authored and prepared the various problems, one shall include such metadata in the `tutorial` section in Polygon.

In particolar, the first two lines of the `tutorial` section shall be

```
%AUTHOR: Name Of The Author Of The Problem
%PREPARATION: Name Of The Person Who Prepared The Problem
```

For example, a correctly formatted `tutorial` section may start with

```
%AUTHOR: Will Smith
%PREPARATION: ac1112
The problem is equivalent to...
```

## Structure of `contest.yaml`

The file `contest.yaml` (passed to `p2d-contest` via the argument `--config`) must be a valid `yaml` file containing the following top-level keys:

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
