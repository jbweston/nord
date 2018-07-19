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
"""Serve nord as a web app.

The API can be accessed by opening a websocket connection to '/api'.

Requests
========
The API accepts 2 types of request.

Connect
*******
A request to connect to a server in the provided country. Countries
are specified as case-insensitive ISO alpha-2 codes. An example
request is::

    {
      "method" : "connect",
      "country" : "NL"
    }

Disconnect
**********
A request to disconnect the current OpenVPN connection. An
example request is::

    {
      "method" : "disconnect"
    }


Responses
=========

Connecting
**********
After receiving a "connect" request, the API will send a message
to all connected peers with the following example format::

    {
      "state" : "connecting",
      "country" : "nl",
    }

Connected
*********
When an OpenVPN connection is established, the API will send
a message to all connected peers with the following example
format::

    {
      "state" : "connected",
      "host" : "nl123.nordvpn.com"
    }

Disconnecting
*************
After receiving a "disconnect" request, the API will send a message
to all connected peers with the following example format::

    {
      "state" : "disconnecting"
    }

Disconnected
************
When an OpenVPN connection is established, the API will send
a message to all connected peers with the following example
format::

    {
      "state" : "disconnected"
    }

Error
*****
If there was some error on the server side the API will send a
message to all connected peers in the following example format::

    {
      "state" : "error",
      "message" : "Something went wrong!"
    }
"""

import asyncio
import os.path
from os.path import abspath, dirname

from structlog import get_logger
from aiohttp import web

from . import api

STATIC_FOLDER_PATH = os.path.join(abspath(dirname(__file__)), 'static')


async def index(_):
    """Serve frontend files."""
    return web.FileResponse(os.path.join(STATIC_FOLDER_PATH, 'index.html'))


def init_app(client, credentials):
    """Instantiate a new nord web app.

    Parameters
    ----------
    client : nord.api.Client
    credentials: (username, password)

    Returns
    -------
    aiohttp.web.Application
    """
    app = web.Application()

    app.router.add_get('/', index)
    app.router.add_get('/api', api.handler)
    app.router.add_static('/', path=STATIC_FOLDER_PATH, name='static')

    app['credentials'] = credentials
    app['client'] = client
    app['peers'] = set()
    app['queue'] = asyncio.Queue(loop=app.loop)
    app['log'] = get_logger(__name__)
    app['shutdown_signal'] = asyncio.Event(loop=app.loop)

    app.on_startup.append(api.on_startup)
    app.on_cleanup.append(api.on_cleanup)

    return app
