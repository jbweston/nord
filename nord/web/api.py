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

import asyncio
import json

import aiohttp
from aiohttp import web
from structlog import get_logger

_log = get_logger('web')


async def handle_message(log, data, peers):
    message = json.loads(data)
    if message['method'] == 'connect':
        log.info('VPN connect', country=message['country'].lower())
        # TODO: call into api
        await asyncio.sleep(4)
        response = dict(state='connected',
                        host=message['country'].lower() + '123')
    elif message['method'] == 'disconnect':
        log.info('VPN disconnect')
        # TODO: call into api
        await asyncio.sleep(5)
        response = dict(state='disconnected')

    await asyncio.wait([p.send_json(response) for p in peers])


async def handler(request):
    log = _log.bind(ip_address=request.remote)
    peers = request.app['peers']

    log.info('new connection')
    ws = web.WebSocketResponse(autoping=True, heartbeat=1)
    await ws.prepare(request)
    log.info('websocket ready')
    peers.add(ws)

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == 'close':
                await ws.close()
            else:
                log.debug('received', message=msg.data)
                request.loop.create_task(handle_message(log, msg.data, peers))

    peers.remove(ws)
    log.info('connection closed')
    return ws
