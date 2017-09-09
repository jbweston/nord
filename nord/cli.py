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
"""Command-line interface to the NordVPN client."""

import sys
import traceback
import signal
import logging
import argparse
import asyncio

import structlog
from termcolor import colored
import aiohttp

from . import api, vpn, _version
from ._utils import sudo_requires_password, prompt_for_sudo, LockError


class Abort(RuntimeError):
    """Signal the command-line interface to abort."""


def main():
    """Execute the nord command-line interface"""
    # parse command line arguments
    parser = command_parser()
    args = parser.parse_args()
    if not args.command:
        parser.error('no command provided')
    command = globals()[args.command]

    setup_logging(args)

    # set up the event loop
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, cancel_all_tasks)

    # dispatch
    try:
        returncode = loop.run_until_complete(command(args))
    except asyncio.CancelledError:
        returncode = 1
    except Abort as error:
        print(f"{colored('Error', 'red', attrs=['bold'])}:", error)
        returncode = 1
    finally:
        remaining_tasks = cancel_all_tasks()
        if remaining_tasks:
            loop.run_until_complete(asyncio.wait(remaining_tasks))
        loop.close()

    sys.exit(returncode)


def cancel_all_tasks():
    """Cancel all outstanding tasks on the default event loop."""
    remaining_tasks = asyncio.Task.all_tasks()
    for task in remaining_tasks:
        task.cancel()
    return remaining_tasks


def render_logs(logger, _, event):
    """Render logs into a format suitable for CLI output."""
    if event.get('stream', '') == 'status':
        if event['event'] == 'up':
            msg = colored('connected', 'green', attrs=['bold'])
        elif event['event'] == 'down':
            msg = colored('disconnected', 'red', attrs=['bold'])
    elif event.get('stream', '') == 'stdout':
        msg = f"[stdout @ {event['timestamp']}] {event['event']}"
    elif event.get('exc_info'):
        msg = traceback.format_exception(*event['exc_info'])
    else:
        msg = f"{event['event']}"
    return f"[{colored(logger.name, attrs=['bold'])}] {msg}"


def setup_logging(args):
    """Set up logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="%x:%X", utc=False),
            structlog.processors.UnicodeDecoder(),
            render_logs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # set up stdlib logging to be the most permissive, structlog
    # will handle all filtering and formatting
    logging.basicConfig(
        stream=sys.stdout,
        level=(logging.DEBUG if hasattr(args, 'debug') and args.debug
               else logging.INFO),
        format='%(message)s',
    )

    # silence 'asyncio' logging
    logging.getLogger('asyncio').propagate = False


def command_parser():
    """Return a parser for the Nord command-line interface."""
    parser = argparse.ArgumentParser('nord')
    subparsers = parser.add_subparsers(dest='command')

    version = _version.get_versions()['version']
    parser.add_argument('--version', action='version',
                        version=f'nord {version}')

    subparsers.add_parser('ip_address')

    connect_parser = subparsers.add_parser('connect')
    connect_parser.add_argument('--debug', action='store_true',
                                help='print debugging information')
    connect_parser.add_argument('-u', '--username', type=str,
                                required=True,
                                help='NordVPN username')
    # methods of password entry
    passwd = connect_parser.add_mutually_exclusive_group(required=True)
    passwd.add_argument('-p', '--password', type=str,
                        help='NordVPN password')
    passwd.add_argument('-f', '--password-file', type=argparse.FileType(),
                        help='path to file containing NordVPN password')

    connect_parser.add_argument('host',
                                help='nordVPN host or fully qualified '
                                     'domain name')
    return parser


# Subcommands

async def ip_address(_):
    """Get our public IP address."""
    async with api.Client() as client:
        print(await client.current_ip())


async def connect(args):
    """Connect to a NordVPN server."""

    username = args.username
    password = args.password or args.password_file.readline().strip()

    # Catch simple errors before we even make a web request
    host = args.host
    try:
        host = api.normalized_hostname(host)
    except ValueError as error:
        raise Abort(f'{host} is not a NordVPN server')

    # Group requests together to reduce overall latency
    try:
        async with api.Client() as client:
            output = await asyncio.gather(
                client.valid_credentials(username, password),
                client.host_config(host),
                client.dns_servers(),
                sudo_requires_password(),
            )
            valid_credentials, config, dns_servers, require_sudo = output
    except aiohttp.ClientResponseError as error:
        # The only request that can possibly 404 is 'host_config'
        if error.code != 404:
            raise
        raise Abort(f'{host} is not a NordVPN server')

    if not valid_credentials:
        raise Abort('invalid username/password combination')

    if require_sudo:
        print('sudo password required for OpenVPN')
        try:
            await prompt_for_sudo()
        except PermissionError:
            # 'sudo' will already have notified the user about the failure
            raise Abort()

    try:
        await vpn.run(config, username, password, dns_servers)
    except LockError:
        raise Abort('Failed to obtain a lock: is another instance '
                    'of nord running?')
    except vpn.OpenVPNError as error:
        raise Abort(str(error))
