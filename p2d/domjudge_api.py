import io
import logging
import os
import random
import requests
import string
import sys
import tempfile
import yaml

from p2d._version import __version__

def generate_externalid(problem):
    random_suffix = ''.join(random.choice(string.ascii_uppercase) for _ in range(6))
    return problem['label'] + '-' + problem['name'] + '-' + random_suffix


# credentials is a dictionary with keys contest_id, server, username, password.
def call_domjudge_api(api_address, data, files, credentials):
    res = requests.post(
        credentials['server'] + api_address,
        auth=requests.auth.HTTPBasicAuth(
            credentials['username'], credentials['password']),
        data=data,
        files=files)
    return res

# Updates the problem on the server with the package_zip.
# Returns true if the update was successful.
# TODO: This depends on the (still to be merged) PR
#       https://github.com/DOMjudge/domjudge/pull/1522.
# credentials is a dictionary with keys contest_id, server, username, password.
def update_problem_api(package_zip, problem_id, credentials):
    api_address = '/api/v4/contests/%s/problems' % credentials['contest_id']
    
    with open(package_zip, 'rb') as f:
        res = call_domjudge_api(api_address,
                                {'problem': problem_id},
                                {'zip': (package_zip, f)},
                                credentials)

    if res.status_code != 200 or not res.json()['problem_id']:
        logging.error('Error sending the package to the DOMjudge server: %s.'
                      % res.json())
        return False
    else:
        logging.debug('Successfully sent the package to the DOMjudge server.')
        return True

# Adds an "empty" problem to a contest.
# Returns true if the problem was successfully added. In such case, it set
# the 'domjudge_id' of the problem.
# credentials is a dictionary with keys contest_id, server, username, password.
def add_problem_to_contest_api(problem, credentials):
    api_address = '/api/v4/contests/%s/problems/add-data' % credentials['contest_id']
    externalid = generate_externalid(problem)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='w',
                                     encoding='utf-8') as f:
        problem_yaml = f.name
        yaml.safe_dump([{
                'id': externalid,
                'label': problem['label'],
                'name': problem['name']
            }],
            f, default_flow_style=False, sort_keys=False)

    with open(problem_yaml, 'rb') as f:
        res = call_domjudge_api(api_address, {}, {'data': (problem_yaml, f)}, credentials)
    os.unlink(problem_yaml)

    if res.status_code != 200:
        logging.error('Error adding the problem to the contest: %s.' % res.json())
        return False

    problem['domjudge_id'] = externalid

    return True
