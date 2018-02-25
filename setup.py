#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2017 Joseph Weston
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
from setuptools import setup, find_packages


if sys.version_info < (3, 6):
    print('nord requires Python 3.6 or above.')
    sys.exit(1)

requirements = [
    'decorator',
    'structlog',
    'aiohttp',
    'termcolor',
]

dev_requirements = [
    'pylint',
    'pep8',
    'sphinx',
    'sphinx-autobuild',
    'sphinx-rtd-theme',
]

classifiers =[
    'Development Status :: 2 - Pre-Alpha',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3.6',
    'Intended Audience :: End Users/Desktop',
    'Intended Audience :: Developers',
    'Topic :: Utilities',
]

with open('README.rst') as readme_file:
    long_description = readme_file.read()


# Loads _version.py module without importing the whole package.
def get_version_and_cmdclass(package_name):
    import os
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location('version',
                                   os.path.join(package_name, '_version.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__version__, module.cmdclass


version, cmdclass = get_version_and_cmdclass('nord')


class sdist(cmdclass['sdist']):
    def run(self):
        import subprocess
        subprocess.check_call(['yarn', 'install'])
        subprocess.check_call(['yarn', 'build'])
        super().run()


cmdclass.update(dict(sdist=sdist))

setup(
    name='nord',
    author='Joseph Weston',
    author_email='joseph@weston.cloud',
    description='Unofficial NordVPN client',
    license='GNU General Public License v3',
    version=version,
    url='https://github.com/jbweston/nord',
    cmdclass=cmdclass,
    platforms=['GNU/Linux'],
    packages=find_packages('.'),
    long_description=long_description,
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements,
    },
    entry_points='''
        [console_scripts]
        nord=nord.cli:main
    ''',
    package_data={'nord.web': ['static/*']},
    include_package_data=True,
)
