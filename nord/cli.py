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
    args = parse_arguments()

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
    # pylint: disable=protected-access
    structlog.stdlib.TRACE = 5
    structlog.stdlib._NAME_TO_LEVEL['trace'] = 5
    structlog.stdlib._LEVEL_TO_NAME[5] = 'trace'
    logging.addLevelName(5, "TRACE")
    logging.basicConfig(
        stream=sys.stdout,
        level=(logging.DEBUG if hasattr(args, 'debug') and args.debug
               else logging.INFO),
        format='%(message)s',
    )

    # silence 'asyncio' logging
    logging.getLogger('asyncio').propagate = False


def parse_arguments():
    """Return a parser for the Nord command-line interface."""
    parser = argparse.ArgumentParser(
        'nord',
        description='An unofficial NordVPN client')
    subparsers = parser.add_subparsers(dest='command')

    version = _version.get_versions()['version']
    parser.add_argument('--version', action='version',
                        version=f'nord {version}')

    subparsers.add_parser(
        'ip_address',
        help="Get our public IP address, as reported by NordVPN.")

    connect_parser = subparsers.add_parser(
        'connect',
        help="connect to a NordVPN server",
        description="Connect to a nordVPN server. If the '--server' argument "
                    "is provided, connect to that specific server, otherwise "
                    "select all hosts in the provided country, filter them "
                    "by their load, and select the closest one.")
    connect_parser.add_argument('--debug', action='store_true',
                                help='Print debugging information')
    connect_parser.add_argument('-u', '--username', type=str,
                                required=True,
                                help='NordVPN account username')
    # methods of password entry
    passwd = connect_parser.add_mutually_exclusive_group(required=True)
    passwd.add_argument('-p', '--password', type=str,
                        help='NordVPN account password')
    passwd.add_argument('-f', '--password-file', type=argparse.FileType(),
                        help='Path to file containing NordVPN password')

    # pre-filters on the hostlist. Either specify a country or a single host
    hosts = connect_parser.add_mutually_exclusive_group(required=True)

    def _flag(country):
        country = str(country).upper()
        if len(country) != 2 or not str.isalpha(country):
            raise argparse.ArgumentTypeError(
                'must be a 2 letter country code')
        return country

    hosts.add_argument('country_code', type=_flag, nargs='?',
                       help='2-letter country code, e.g. US, GB')
    hosts.add_argument('-s', '--server',
                       help='NordVPN host or fully qualified domain name, '
                            'e.g us720, us270.nordvpn.com')

    # arguments to filter the resulting hostlist
    connect_parser.add_argument('--ping-timeout', type=int, default=2,
                                help='Wait for this long for responses from '
                                     'potential hosts')
    connect_parser.add_argument('--max-load', type=int, default=70,
                                help='Reject hosts that have a load greater '
                                     'than this threshold')

    args = parser.parse_args()

    if not args.command:
        parser.error('no command provided')

    return args


# Subcommands

async def ip_address(_):
    """Get our public IP address."""
    async with api.Client() as client:
        print(await client.current_ip())


async def connect(args):
    """Connect to a NordVPN server."""

    username = args.username
    password = args.password or args.password_file.readline().strip()

    # Group requests together to reduce overall latency
    async with api.Client() as client:
        output = await asyncio.gather(
            _get_host_and_config(client, args),
            client.valid_credentials(username, password),
            client.dns_servers(),
            sudo_requires_password(),
        )
    (host, config), valid_credentials, dns_servers, require_sudo = output

    if not valid_credentials:
        raise Abort('invalid username/password combination')

    log = structlog.get_logger(__name__)
    log.info(f"connecting to {host}")

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


async def _get_host_and_config(client, args):
    # get the host
    if args.server:
        try:
            hosts = [api.normalized_hostname(args.server)]
        except ValueError as error:
            raise Abort(f'{args.server} is not a NordVPN server')
    else:
        assert args.country_code
        hosts = await client.rank_hosts(args.country_code,
                                        args.max_load, args.ping_timeout)
        if not hosts:
            raise Abort('no hosts available '
                        '(try a higher load or ping threshold?)')
    # get the config
    for host in hosts:
        try:
            config = await client.host_config(host)
            return host, config
        except aiohttp.ClientResponseError as error:
            if error.code != 404:
                raise  # unexpected error
    # pylint: disable=undefined-loop-variable
    raise Abort(f"config unavailable for {host}")
