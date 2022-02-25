import os

from setuptools import setup, find_packages

import re


def get_version():
    VERSIONFILE = "p2d/_version.py"
    dictionary_for_exec = {}
    exec(open(VERSIONFILE).read(), dictionary_for_exec)
    return dictionary_for_exec['__version__']


setup(
    name='pol2dom',
    version=get_version(),
    description='Convert Polygon Problem Package to DOMjudge Problem Package.',
    author='dario2994',
    author_email='dario2994@gmail.com',
    url='https://github.com/dario2994/pol2dom',
    license='MIT',
    packages=find_packages(),
    package_data={'': ['resources/*']},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'p2d=p2d.main:main'
        ]
    },
    python_requires='>=3.5',
    platforms='any',
    install_requires=[
        'pyyaml >= 5.3',
        'requests >= 2.26'
    ]
)
