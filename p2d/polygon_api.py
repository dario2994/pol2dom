import hashlib
import io
import os
import random
import requests
import string
import sys
import time
import json

from p2d._version import __version__
from p2d.logging_utils import logger
from p2d import p2d_utils

POLYGON_ADDRESS = 'https://polygon.codeforces.com/api/'

# Call to a Polygon API.
# It returns the response, checking that the return status is ok.
def call_polygon_api(key, secret, method_name, params, desc=None, decode=False):
    params['apiKey'] = key
    params['time'] = int(time.time())
    
    rand = ''.join(random.choices(string.ascii_uppercase, k=6))
    pref = rand + '/' + method_name + '?'
    params_arr = []
    for p in params:
        params_arr.append((p, params[p]))
    params_arr.sort()
    middle = ""
    for pp in params_arr:
        if middle:
            middle += '&'
        middle += str(pp[0]) + '=' + str(pp[1])
    suff = '#' + secret

    to_hash = pref + middle + suff
    params['apiSig'] = rand + hashlib.sha512(to_hash.encode()).hexdigest()

    logger.debug(('Sending API request:\n'
                  '\t method = {}\n'
                  '\t params = {}').format(method_name, params))
    
    response = requests.post(POLYGON_ADDRESS + method_name, data=params, stream=True)
    content = bytes()   # Request stream yields chunks in bytes
    for chunk in p2d_utils.wrap_iterable_in_tqdm(
        response.iter_content(chunk_size=1024),
        int(response.headers.get('content-length', 0)) // 1024,
        desc=desc
    ):
        if chunk:
            content += chunk
    if not response.ok:
        logger.error('API call to Polygon returned status {}. The content of the response is {}.'.format(response.status_code, response.text))
        exit(1)
    assert(response.ok)
    return content.decode() if decode else content

# Returns the pair (revision, package_id) corresponding to the latest
# revision of the problem which has a package of type linux ready.
# It returns (-1, -1) if no valid package is found.
def get_latest_package_id(key, secret, problem_id):
    packages_list = json.loads(
        call_polygon_api(key, secret, 'problem.packages', {'problemId': problem_id}, decode=True)
    )

    if packages_list['status'] != 'OK':
        logger.error('API problem.packages request to Polygon failed with error: {}'.format(packages_list['comment']))
        exit(1)

    revision = -1
    package_id = -1
    for p in packages_list['result']:
        if p['revision'] > revision and p['state'] == 'READY' \
           and p['type'] == 'linux':
            revision = p['revision']
            package_id = p['id']
    return (revision, package_id)

# Downloads the Polygon package into polygon_zip (as a .zip archive).
def download_package(key, secret, problem_id, package_id, polygon_zip):
    package = call_polygon_api(key, secret, 'problem.package',
                               {'problemId': problem_id,
                                'packageId': package_id,
                                'type': 'linux'},
                                desc='Downloading Polygon package')
    with open(polygon_zip, "wb") as f:
        f.write(io.BytesIO(package).getbuffer())

# Fetches the list of problems of the specified contest.
def get_contest_problems(key , secret, contest_id):
    return json.loads(call_polygon_api(
        key, secret, 'contest.problems', {'contestId': contest_id}, desc='Fetching contest problems', decode=True
    ))['result']
