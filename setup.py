#!/usr/bin/env python
# coding: utf-8

import os

from io import open
from setuptools import setup, find_packages


here = os.path.dirname(__file__)

with open(os.path.join(here, 'README.rst'), 'r', encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='sphinxcontrib-openapi',
    description='OpenAPI (fka Swagger) spec renderer for Sphinx',
    long_description=long_description,
    license='BSD',
    url='https://github.com/ikalnytskyi/sphinxcontrib-openapi',
    keywords='sphinx openapi swagger rest api renderer docs',
    author='Ihor Kalnytskyi',
    author_email='ihor@kalnytskyi.com',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    use_scm_version=False,
    python_requires='>=3.6',
    setup_requires=[
        'setuptools_scm >= 8.1.0',
    ],
    install_requires=[
        'sphinxcontrib-httpdomain >= 1.5.0',
        'sphinx-jsondomain >= 0.0.2',
        'PyYAML >= 3.12',
        'jsonschema >= 2.5.1',
    ],
    classifiers=[
        'Topic :: Documentation',
        'License :: OSI Approved :: BSD License',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    namespace_packages=['sphinxcontrib'],
)
