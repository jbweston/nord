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

from setuptools import setup

import versioneer


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

setup(
    name='nord',
    author='Joseph Weston',
    author_email='joseph@weston.cloud',
    description='Unofficial NordVPN client',
    license='GNU General Public License v3',
    version=versioneer.get_version(),
    url='https://github.com/jbweston/nord',
    cmdclass=versioneer.get_cmdclass(),
    platforms=['GNU/Linux'],
    packages=['nord'],
    long_description=long_description,
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements,
    },
    entry_points='''
        [console_scripts]
        nord=nord.cli:main
    ''',
)
