import requests
import os
import re

from p2d._version import __version__

HEADER_COMMENT = '''\
// Modified by a script to work with DOMjudge.
// Differences with the standard testlib.h:
// - The values of some exit codes.
// - The functions registerInteraction and registerTestlibCmd.
'''

NEW_EXIT_CODES = {
    'OK_EXIT_CODE': 42,
    'WA_EXIT_CODE': 43,
    'PE_EXIT_CODE': 43,
    'DIRT_EXIT_CODE': 43,
    'UNEXPECTED_EOF_EXIT_CODE': 43
}

NEW_REGISTER_INTERACTION = '''\
void registerInteraction(int argc, char *argv[]) {
    __testlib_ensuresPreconditions();

    testlibMode = _interactor;
    __testlib_set_binary(stdin);

    if (argc > 1 && !strcmp("--help", argv[1]))
        __testlib_help();
    if (argc == 3) {
        resultName = "";
        appesMode = false;
    }

    if (argc == 4) {
        resultName = std::string(argv[3]) + "/judgemessage.txt";
        tout.open(std::string(argv[3]) + "/teammessage.txt",
                  std::ios_base::out);
        if (tout.fail() || !tout.is_open())
            quit(_fail, "Can not write to the test-output-file '" +
                        std::string(argv[2]) + "'");
        appesMode = false;
    }

    inf.init(argv[1], _input);

    ouf.init(stdin, _output);
    if (argc >= 3)
        ans.init(argv[2], _answer);
    else
        ans.name = "unopened answer stream";
}'''


NEW_REGISTER_TESTLIB_CMD = '''\
void registerTestlibCmd(int argc, char *argv[]) {
    __testlib_ensuresPreconditions();

    testlibMode = _checker;
    __testlib_set_binary(stdin);

    if (argc > 1 && !strcmp("--help", argv[1]))
        __testlib_help();

    appesMode = false;

    if (argc == 3) {
        resultName = "";
        appesMode = false;
    }

    if (argc == 4) {
        resultName = std::string(argv[3]) + "/judgemessage.txt";
        appesMode = false;
    }

    inf.init(argv[1], _input);
    ouf.init(stdin, _output);
    ans.init(argv[2], _answer);
}'''


def add_header(lines, header):
    return [header] + lines


def replace_exit_code(lines, name, value):
    for i in range(len(lines)):
        match = re.fullmatch(r'(# *define +%s +)[a-zA-Z0-9]+( *)' % name, lines[i])
        if match:
            lines[i] = match.groups()[0] + str(value) + match.groups()[1]
    return lines


def replace_function(lines, function):
    begin = function.splitlines()[0]
    end = function.splitlines()[-1]

    state = 0
    new_lines = []
    for line in lines:
        if line == begin:
            assert(state == 0)
            state += 1
        if state != 1:
            new_lines.append(line)
        if state == 1 and line == end:
            state += 1
            new_lines.append(function)
    assert(state == 2)
    return new_lines


# Download the latest testlib.h version from github and apply a patch
# to make it compatible with DOMjudge.
#
# The applied patch is copied from
#   https://github.com/cn-xcpc-tools/testlib-for-domjudge.
def generate_testlib_for_domjudge(dst_path):
    logging.debug('Downloading testlib.h from github.')
    req = requests.get(
        'https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h')
    lines = req.text.splitlines()

    logging.debug('Patching testlib.h')
    lines = add_header(lines, HEADER_COMMENT)
    for exit_code in NEW_EXIT_CODES:
        lines = replace_exit_code(lines, exit_code, NEW_EXIT_CODES[exit_code])
    lines = replace_function(lines, NEW_REGISTER_INTERACTION)
    lines = replace_function(lines, NEW_REGISTER_TESTLIB_CMD)

    with open(dst_path, 'w') as f:
        for line in lines:
            f.write(line + '\n')
    logging.info('The file testlib.h was successfully downloaded and patched. The local version can be found at \'%s\'.' % dst_path)
