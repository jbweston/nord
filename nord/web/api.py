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
"""Main API for the nord web app."""

import asyncio
import json
import sys
import functools

import aiohttp
from aiohttp import web, http_websocket

from .. import vpn


async def on_startup(app):
    """invoked on app startup."""
    app['queue'] = queue = asyncio.Queue(loop=app.loop)
    app['peers'] = peers = set()
    app['vpn_coroutine'] = app.loop.create_task(
        _run_vpn(
            functools.partial(_connect, app, app['client']),
            functools.partial(_send, peers),
            functools.partial(app['shutdown_signal'].set),
            queue,
            app['log'],
        )
    )
    app['log'].info('started')
    app['shutdown_signal'].clear()


async def on_cleanup(app):
    """invoked on app cleanup."""
    app['log'].info('closing downstream websockets')
    if app['peers']:
        await asyncio.wait([
            ws.close(code=http_websocket.WSCloseCode.GOING_AWAY,
                     message='Server shutdown')
            for ws in app['peers']
        ])
    app['log'].info('closing NordVPN client connection')
    await _stop(app['vpn_coroutine'])


async def _run_vpn(connect_vpn, send_peers, on_shutdown, queue, log):
    """Manage the single OpenVPN connection."""
    vpn_task = None
    while True:
        try:
            message = await queue.get()
            if message['method'] == 'connect':
                country = message['country']
                log.info('VPN connect', country=country)
                await send_peers(state='connecting', country=country)
                host, vpn_task = await connect_vpn(country)
                await send_peers(state='connected', host=host)
            elif message['method'] == 'disconnect':
                log.info('VPN disconnect')
                await send_peers(state='disconnecting')
                await _stop(vpn_task)
                vpn_task = None
                await send_peers(state='disconnected')
        except asyncio.CancelledError:
            break
        except Exception as err:
            log.error('unexpected exception occurred', exc_info=sys.exc_info())
            await _stop(vpn_task)
            await send_peers(state='error', message=err.args[0])

    log.info('stopping VPN')
    await _stop(vpn_task)
    on_shutdown()
    await send_peers(state='error', message='Backend disconnected')


async def handler(request):
    """Manage a given client websocket connection."""
    log = request.app['log'].bind(ip_address=request.remote)
    peers = request.app['peers']
    queue = request.app['queue']

    websocket = web.WebSocketResponse(autoping=True, heartbeat=1)
    await websocket.prepare(request)
    log.debug('websocket ready')

    peers.add(websocket)
    try:
        async for msg in websocket:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            if msg.data == 'close':
                await websocket.close()
            else:
                try:
                    parsed_msg = _parse_message(msg.data)
                except Exception:
                    log.warning('received malformed message', message=msg.data)
                else:
                    await queue.put(parsed_msg)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.error('unexpected exception occurred', exc_info=sys.exc_info())
    finally:
        peers.remove(websocket)
    return websocket


# Utilities

def _parse_message(raw):
    msg = json.loads(raw)
    assert msg['method'] in ('connect', 'disconnect')
    if msg['method'] == 'connect':
        msg['country'] = msg['country'].lower()
    return msg



async def _send(peers, **message):
    if peers:
        await asyncio.wait([
            p.send_json(message)
            for p in peers
        ])


async def _connect(app, client, country):
    dns = await client.dns_servers()
    try:
        hosts = await client.rank_hosts(country)
    except ValueError:
        raise ValueError(f'{country} has no available servers')

    host = None
    for host in hosts:
        try:
            config = await client.host_config(host)
            break
        except aiohttp.ClientResponseError as error:
            if error.code != 404:
                raise  # unexpected error

    username, password = app['credentials']
    vpn_proc = await vpn.start(config, username, password)
    vpn_task = app.loop.create_task(vpn.supervise_with_context(vpn_proc, dns))
    return host, vpn_task


async def _stop(coro):
    if coro:
        coro.cancel()
        await coro
