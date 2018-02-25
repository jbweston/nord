# -*- coding: utf-8 -*-
#
# copyright 2018 joseph weston
#
# this program is free software: you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation, either version 3 of the license, or
# (at your option) any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program.  if not, see <http://www.gnu.org/licenses/>.

import os.path
from os.path import abspath, dirname

from aiohttp import web


STATIC_FOLDER_PATH = os.path.join(abspath(dirname(__file__)), 'static')


async def index(request):
    return web.FileResponse(os.path.join(STATIC_FOLDER_PATH, 'index.html'))

app = web.Application()

app.router.add_get('/', index)
app.router.add_static('/', path=STATIC_FOLDER_PATH, name='static')

app['websockets'] = set()

def get_app(*args):
    return app
