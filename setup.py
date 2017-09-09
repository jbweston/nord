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
]

setup(
    name='nord',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements,
    },
    entry_points='''
        [console_scripts]
        nord=nord.cli:main
    ''',
)
