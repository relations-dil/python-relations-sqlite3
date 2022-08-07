#!/usr/bin/env python

from setuptools import setup

with open("README.md", "r") as readme_file:
    long_description = readme_file.read()

setup(
    name="relations-sqlite3",
    version="0.6.6",
    package_dir = {'': 'lib'},
    py_modules = [
        'relations_sqlite3'
    ],
    install_requires=[
        'relations-sqlite>=0.6.1'
    ],
    url="https://github.com/relations-dil/python-relations-sqlite3",
    author="Gaffer Fitch",
    author_email="relations@gaf3.com",
    description="DB Modeling for SQLite using the sqlite3 library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license_files=('LICENSE.txt',),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
    ]
)
