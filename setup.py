#!/usr/bin/env python3

"""
Setup file for the SSI API client subpackage in SSI's python library.
"""

from setuptools import setup


with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='ssi.api-client',
    version='1.2.0',
    author='Erek Alper, Doug Johnson',
    author_email='erek.alper@subsurfaceinsights.com, dougvj@gmail.com',
    description='A subpackage containing commonly used SSI API client functions.',
    long_description=open('README.md').read(),
    packages=['ssi'],
    package_data = {
        'ssi': ['py.typed']
    },
    zip_safe=False,
    install_requires=requirements,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],
)
