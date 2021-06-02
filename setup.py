#!/usr/bin/env python

from setuptools import setup, find_packages
setup(
    name="relations-sqlite3",
    version="0.1.5",
    package_dir = {'': 'lib'},
    py_modules = [
        'relations_sqlite3'
    ],
    install_requires=[]
)
