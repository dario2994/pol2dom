# pol2dom

Tool to transform a Polygon problem package into a DOMjudge problem package. It does all the job and no human intervention is necessary after the conversion.

- Parses from the Polygon package: metadata (name, time limit, memory limit), samples, checker, interactor, input files, output files, solutions (submitted as jury submissions on DOMJudge). Checkers and interactors using testlib.h are supported transparently.
- Generates the statement pdf (with the possibility of customizing the LaTeX template) starting from the statement sections written in polygon (legend, input, output, notes). The samples' explanations are detected from the notes section in polygon through the use of special markers (see [Samples explanation detection](#samples-explanations-detection) for the details).
- Accepts as optional arguments the color of the problem (which is not contained in the Polygon package) and the contest name (to properly generate the statement).
- Supports both zip archives and folders.

This project was born as a refactoring of [polygon2domjudge](https://github.com/cubercsl/polygon2domjudge).

## Usage

Running `p2d --contest "CONTEST NAME" --color "COLOR NAME" --from polygon_package --to domjudge_package` will convert the Polygon problem package `polygon_package` into an equivalent DOMjudge problem package `domjudge_package`. The name of the file `domjudge_package` corresponds to the letter used to identify the problem in DOMjudge.
The arguments `polygon_package` and `domjudge_package` can be either folders or zip files.

The polygon package must be a *full* package, i.e., it must contain the generated tests.

Example: `p2d --contest SWERC 2022" --color red --from my_problems/sum-integers.zip --to C.zip`.

Use `p2d --help` for a guide.

## Installation
### Method 1: Install the Python package using `pipx`
The tool `pipx` is like `pip` (so it allows to install python packages in the local system) but uses virtual-environments transparently to avoid polluting the global python environment)

Run
```bash
$ pip install git+https://github.com/dario2994/pol2dom
```
This provides you with the command `p2d` available in any shell terminal.

### Method 2: Run directly from the repository

Clone the repository with `git clone https://github.com/dario2994/pol2dom` and run the command with `bin/p2d.sh` directly from the repository folder.

## Customization of the LaTeX statement template

The statement is generated starting from `resources/problem_template.tex` by performing the following operations:

1. Replace the strings `??LETTER??`, `??NAME??`, `??TIMELIMIT??`, `??MEMORYLIMIT??` with the corresponding metadata.
2. Replace the string `??LEGEND??`, `??INPUT??`, `??OUTPUT??` with the content of the corresponding sections in the polygon statement;
3. Generate an initially empty string `samples`.
For each problem sample, create two files `sample_id.in` and `sample_id.out` and append to the string `samples` the code `\sample{sample_id}` or `\bigsample{sample_id}`. The command `\bigsample` is used if there is a line in `sample_id.in` or `sample_id.out` longer than `BIG_SAMPLE_CHARS_NUM=40` characters (the value of `BIG_SAMPLE_CHARS_NUM` can be configured via `--big_sample_chars_num`), so that big samples can have a different formatting if desired.
If the sample has an explanation (see [Samples explanation detection](#samples-explanation-detection)), append also `\sampleexplanation{Content of the sample explanation.}`.
4. Replace the string `??SAMPLES??` with the string `samples` generated in the previous step.

It is clear from the operations performed that `resources/problem_template.tex` contains the placeholders `??LETTER??`, `??NAME??`, `??TIMELIMIT??`, `??MEMORYLIMIT??`, `??LEGEND??`, `??INPUT??`, `??OUTPUT??`, `??SAMPLES??`.

Then, the tex source code generated is inserted in `resources/statements_template.tex` (by replacing the string `??DOCUMENTCONTENT??`). Finally the string `??CONTEST??` is replaced with the corresponding metadata (given by the argument `--contest`).

The tex file `resources/statements_template.tex` implements the commands: `\problemletter`, `\problemtitle`, `\timelimit`, `\memorylimit`, `\problemheader`, `\inputsection`, `\outputsection`, `\samplessection`, `\sample`, `\bigsample`, `\sampleexplanation`.

If you want to customize the visual aspect of the generated pdf, use the command argument `--statements_template 'my_statements_template.tex'` (it will be used instead of `resources/statements_template.tex`).

### Samples explanation detection

In polygon the explanations of samples (when present) are contained in the Notes section without a specific structure.
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

