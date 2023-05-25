# pol2dom

Tool to convert a set of problems prepared in [Polygon](https://polygon.codeforces.com/) into a [DOMjudge](https://www.domjudge.org/) contest.

The whole process is automated: downloading the Polygon package, converting it into a DOMjudge package (which is a descendant of the [Problem Package Format](https://icpc.io/problem-package-format/)), and uploading the DOMjudge package to a DOMjudge server.

This tool offers the command `p2d`.
Its main features are:

- Download, with a caching mechanism, the most recent Polygon package of a problem through Polygon APIs.
- Upload, with a caching mechanism, the converted DOMjudge package of a problem into a DOMjudge server.
- Handling many problems as a contest.
- Convert a Polygon package into a DOMjudge package without human intervention (with the possibility to tweak time and memory limit in the process).
- Generation of the statement (here is an [example of statement](examples/statement.pdf)) in pdf with the option to add some custom features to it (e.g., the contest name, a balloon with the color of the problem, time limit and memory limit, etc..). The samples' explanations are [detected from the notes section in Polygon through the use of special markers](#samples-explanation-detection).
- Generation of a pdf with the complete problem set of a contest featuring a custom front page. Same for the pdf of the solutions of the problems.
- Checkers using testlib.h are supported transparently (by using a modified `testlib.h` which is DOMjudge compatible).
- Through the `Judging verifier` feature of DOMjudge, it enforces that the submissions present in Polygon get the correct result also in DOMjudge.

This project was born as a refactoring of [polygon2domjudge](https://github.com/cubercsl/polygon2domjudge) and evolved into something more.
It was used for [SWERC 2021-2022](https://swerc.eu/2021/about/).

## Installation
### Method 1: Install the Python package using `pipx`
<sub>The tool `pipx` is like `pip` (so it allows to install python packages in the local system) but uses virtual-environments transparently to avoid polluting the global python environment.</sub>

Run
```bash
$ pipx install git+https://github.com/dario2994/pol2dom
```
This provides you with the command `p2d` available in any shell terminal.

### Method 2: Run directly from the repository

Clone the repository with `git clone https://github.com/dario2994/pol2dom` and run the command with `./p2d.sh` directly from the repository directory.

## Usage

Running

```p2d contest_directory --polygon --convert --domjudge --pdf```

downloads the packages of the problems of the contest from Polygon, converts them to DOMjudge packages, and uploads them to the DOMjudge server, and generates a pdf with the statements of all the problems and a pdf with all the solutions.
The list of the problems, as well as the credentials to access Polygon and the DOMjudge server are contained in the configuration file `contest_directory/config.yaml`. The content and the format of `config.yaml` are described in [Structure of config.yaml](#structure-of-configyaml).

Let us describe the five, almost independent, fundamental operations that can be performed by `p2d`:

- `--polygon`: For each problem, download its latest valid package from Polygon. The package must be a *full* package (and the linux version will be downloaded). A caching mechanism is employed to avoid downloading a package which is already up to date locally.
For this to work, `config.yaml` must contain the credentials to access Polygon APIs.
For each problem, the directory `contest_directory/polygon/problem_name/` is generated. Such directory contains the Polygon package (extracted) as well as its zip (named `problem_name.zip`).
- `--convert`: For each problem (which was previously, possibly during a different execution, downloaded from Polygon), convert it to a DOMjudge package, adding the information needed by DOMjudge but absent in Polygon (i.e., the label, the color, the statement in pdf, possibly changing time and memory limit) as described in `config.yaml`. A caching mechanism is employed to avoid converting problems that were converted previously and whose Polygon package did not change in the meanwhile.
For each problem, the directory `contest_directory/domjudge/problem_name` is generated. Such directory contains the DOMjudge package (extracted) as well as its zip (named `problem_name.zip`).
For each problem, also `contest_directory/tex/problem_name-statement.pdf` and `contest_directory/tex/problem_name-solution.pdf` are generated.
- `--domjudge`: For each problem, upload its package to the DOMjudge server. A caching mechanism is employed to avoid uploading a package which is already up to date in the DOMjudge server.
For this to work, `config.yaml` must contain the credentials to access DOMjudge APIs.
- `--from-contest <contest-id>`: Fetch the problems of an existing Polygon contest. The configuration file `config.yaml` will be updated with the problems from the contest that were not present before (some fields, such as `color` and `author`, are to be set manually). The problem packages will not be downloaded unless the `--polygon` flag is specified.
- `--pdf`: Generate in `contest_directory/tex/` the full problem set `statements.pdf` and the editorial of the contest `solutions.pdf`. The problems that will appear in these files are those that were ever converted to a valid DOMjudge package by the command (even in a previous execution).

Here is a schematic description of the structure of `contest_directory` after the execution of the command (the user needs only to create a properly set up `config.yaml`):

```
config.yaml
polygon/
    problem_name/
        the content of the package.
        problem_name.zip = the zipped package itself
domjudge/
    problem_name/
        the content of the package
        problem_name.zip = the zipped package itself
tex/
    samples/ (containing all the samples)
    images/ (containing all the images, for statements and solutions)
    statements.pdf
    solutions.pdf
    For each problem:
    problem_name-statement.pdf
    problem_name-solution.pdf
```

Let us describe some additional flags:
- `--problems <problem_name> [<problem_name> [...]]`: Process only the specified problems.
- `--no-cache`: Ignore the cache for a single run.
- `--clear-dir`: Clear the directory `contest_directory` (without removing `config.yaml`) and permanently delete the cache.
- `--clear-domjudge-ids`: Clear the DOMjudge IDs assigned to the problems when importing them in DOMjudge. This is necessary if the DOMjudge instance changes, or if the DOMjudge instance is reset, or if the DOMjudge contest is changed in `config.yaml`.
- `--help`: Show a list of the available flags, with their descriptions.

## Structure of `config.yaml`

The file `config.yaml` must be present in the contest directory to instruct `p2d` on the properties of the contest.
It must be a valid `yaml` file containing the following top-level keys:

- `contest_name` (mandatory): The name of the contest. It appears in the statements of the problems (and in the solutions).
- `front_page_statements`: Absolute path of the single-page pdf to use as front page of the document containing the statements of all the problems. This key is not mandatory, if it is not provided then the pdf will not have a front page.
- `front_page_solutions`: Absolute path of the single-page pdf to use for the front page of the editorial containing the solutions to all the problems. This key is not mandatory, if it is not provided then the pdf with the solutions will not have a front page.
- `hide_balloon`: A boolean which decides whether a balloon with the color of the problem shall appear in the statement. By default it appears, set this to `1` to not show it.
- `hide_tlml`: A boolean which decides whether the time limit and the memory limit of the problem shall appear in the statement. By default it appears, set this to `1` to not show it. This can be useful when one has to print the statements before having the opportunity to test the computers that will evaluate the submissions during the contest.
- `polygon`: A dictionary containing the credentials to use Polygon's APIs. This is necessary only if you want to use `p2d` to download the problem packages from Polygon. It must have the keys `key` and `secret`. The credentials can be generated in the menu `settings` in Polygon.
- `domjudge`: A dictionary containing the credentials to use DOMjudge's APIs. This is necessary only if you want to use `p2d` to upload the problems in a DOMjudge instance (i.e., if you want to use the flag `--domjudge`). This subdictionary must contain the following keys:
    - `server`: Address of the server hosting the DOMjudge instance.
    - `username`: The username of an admin user of the DOMjudge instance.
    - `password`: The password of the abovementioned user.
    - `contest_id`: The external ID of the DOMjudge contest. 
- `problems`: This is a list of problems. A problem is a dictionary with the following keys:
  - `name` (mandatory): Short-name, in Polygon, of the problem. This is used as identifier of the problem (denoted above as `problem_name`).
  - `polygon_id`: The problem id in Polygon. Can be found in the right-side menu after opening the problem in Polygon. It is necessary to download the Polygon package.
  - `label`: The label -- usually an uppercase letter -- used to identify the problem in the DOMjudge scoreboard. Problems will be appear in DOMjudge sorted according to this label.
  - `color`: Color of the problem in DOMjudge. It can be either the name of an HTML color (see the list https://htmlcolorcodes.com/color-names/) or the hexadecimal representation of a color (e.g., '#FF12AB'). If the hexadecimal representation is used, it must start with # and it must be enclosed in single or double quotes. 
  - `author`: The author of the problem. Used in the pdf of the solutions.
  - `preparation`: The person who prepared the problems. Used in the pdf of the solutions.
  - `override_time_limit`: Value (in seconds) of the time limit of the problem in DOMjudge. If this is present the value set in Polygon is ignored.
  - `override_memory_limit`: Value (in MiB) of the memory limit of the problem in DOMjudge. If this is present the value set in Polygon is ignored.

Some more keys are added (and managed) by `p2d` for caching purposes. Namely each problem will also contain the additional keys: `polygon_version`, `domjudge_local_version`, `domjudge_server_version`.
These additional keys are managed by `p2d` and should not be created or modified by the user. In order to clear entirely the keys related to caching, use the flag `--clear-dir` (which will also clear the directory of the contest).

Moreover, each problem (after being uploaded for the first time on DOMjudge) is assigned a `domjudge_id` (a number) and a `domjudge_externalid` (which corresponds to the external ID of the problem in DOMjudge).
In order to clear the DOMjudge IDs, use the flag `--clear-domjudge-ids`.

See [this example](examples/config.yaml) for a valid `config.yaml` file.

## Samples explanation detection

In Polygon the explanation of samples (when present) is contained in the Notes section without a specific structure.
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
2. Replace the string `??LEGEND??`, `??INPUT??`, `??OUTPUT??`, `??INTERACTION??` with the content of the corresponding sections in the Polygon statement (if present);
3. Generate an initially empty string `samples`.
For each problem sample, create two files `sample_id.in` and `sample_id.out` and append to the string `samples` the code `\sample{sample_id}`.
If the sample has an explanation (see [Samples explanation detection](#samples-explanation-detection)), append also `\sampleexplanation{Content of the sample explanation.}`.
4. Replace the string `??SAMPLES??` with the string `samples` generated in the previous step.

It is clear from the operations performed that `resources/statement_template.tex` contains the placeholders `??LABEL??`, `??TITLE??`, `??TIMELIMIT??`, `??MEMORYLIMIT??`, `??LEGEND??`, `??INPUT??`, `??OUTPUT??`, `??SAMPLES??`.

Then, the tex source code generated is inserted in `resources/document_template.tex` (by replacing the string `??DOCUMENTCONTENT??`). Finally the string `??CONTEST??` is replaced with the corresponding metadata (given by the argument `--contest`).

The tex file `resources/document_template.tex` implements the commands: `\problemlabel`, `\problemtitle`, `\timelimit`, `\memorylimit`, `\problemheader`, `\inputsection`, `\outputsection`, `\samplessection`, `\sample`, `\smallsample`, `\bigsample`, `\sampleexplanation`.
