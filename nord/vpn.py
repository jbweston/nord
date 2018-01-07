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
"""Tools for starting and supervising OpenVPN clients."""

import sys
import asyncio

from structlog import get_logger

from ._utils import (write_to_tmp, lock_subprocess, kill_root_process,
                     require_sudo, maintain_sudo, multi_context,
                     replace_content_as_root)


OPENVPN_EXECUTABLE = '/usr/sbin/openvpn'
LOCKFILE = '/run/lock/nordvpn.lockfile'
_OPENVPN_UP = b'Initialization Sequence Completed'


class OpenVPNError(RuntimeError):
    """Errors from the OpenVPN subprocess"""


@require_sudo
async def start(config, username, password):
    """Start an OpenVPN client with the given configuration.

    Parameters
    ----------
    config : str
        The contents of the OpenVPN config file.
    username, password : str
        Credentials for the OpenVPN connection.

    Returns
    -------
    proc : asyncio.subprocess.Process

    Raises
    ------
    PermissionError if we cannot use 'sudo' without a password.
    OpenVPNError if the OpenVPN process does not start correctly.
    LockError if a lock could not be obtained for the lockfile.

    Notes
    -----
    Obtains a lock on a global lockfile before launching an OpenVPN
    client in a subprocess. The lock is released when the process
    dies.
    """
    logger = get_logger(__name__)

    config_file = write_to_tmp(config)
    credentials_file = write_to_tmp(f'{username}\n{password}')

    cmd = ['sudo', '-n', OPENVPN_EXECUTABLE,
           '--suppress-timestamps',
           '--config', config_file.name,
           '--auth-user-pass', credentials_file.name,
          ]

    proc = None

    # detach the child from the current process group so as to
    # avoid signals destined for *this* process.
    # *we* handle signals properly with 'kill_root_process'
    def _protect_child():
        import os
        os.setpgrp()

    try:
        proc = await lock_subprocess(*cmd, stdout=asyncio.subprocess.PIPE,
                                     preexec_fn=_protect_child,
                                     lockfile=LOCKFILE)
        logger = logger.bind(pid=proc.pid)

        # Wait until OpenVPN connects, indicated by a particular line in stdout
        stdout = b''
        while _OPENVPN_UP not in stdout:
            stdout = await proc.stdout.readline()
            if not stdout:
                # 'readline' returned empty; stdout is closed.
                # Even if OpenVPN is not dead, we have no way of knowing
                # whether the connection is up or not, so we kill it anyway.
                raise OpenVPNError('OpenVPN failed to start')
            logger.debug(stdout.decode().rstrip(), stream='stdout')

    except OpenVPNError:
        logger.debug('failed to start')
        raise

    except asyncio.CancelledError:
        logger.debug('received cancellation while starting')
        if proc:
            await asyncio.shield(kill_root_process(proc))
        raise

    except Exception:
        logger.error('unexpected exception', exc_info=sys.exc_info())
        if proc:
            await asyncio.shield(kill_root_process(proc))
        raise

    finally:
        config_file.close()
        credentials_file.close()

    logger.info('up', stream='status')

    return proc


async def supervise(proc):
    """Supervise a process.

    This coroutine supervises a process and writes its stdout to
    a logger until it dies, or until the coroutine is cancelled,
    when the process will be killed.

    Parameters
    ----------
    proc : asyncio.subprocess.Process

    Returns
    -------
    returncode : int
         'proc.returncode'.
    """
    logger = get_logger(__name__).bind(pid=proc.pid)
    try:
        stdout = await proc.stdout.readline()
        while stdout:
            logger.debug(stdout.decode().rstrip(), stream='stdout')
            stdout = await proc.stdout.readline()
        # stdout is closed -- wait for the process to terminate
        await proc.wait()
    except asyncio.CancelledError:
        logger.debug('received cancellation')
    else:
        stdout, _ = await proc.communicate()
        stdout = (l.rstrip() for l in stdout.decode().split('\n'))
        for line in (l for l in stdout if l):
            logger.debug(line, stream='stdout')
        logger.warn('unexpected exit', return_code=proc.returncode)
    finally:
        logger.debug('cleaning up OpenVPN')
        await asyncio.shield(kill_root_process(proc))
        logger.info('down', stream='status')

    return proc.returncode


@require_sudo
async def run(config, username, password, dns_servers=()):
    """Run an OpenVPN client until it dies and return the exit code.

    Optionally provide DNS servers that will replace the contents
    of '/etc/resolv.conf' for the duration of the client.

    Parameters
    ----------
    config : str
        The contents of the OpenVPN config file.
    username, password : str
        Credentials for the OpenVPN connection.
    dns_servers : tuple of str, optional
        IP addresses of DNS servers with which to populate
        '/etc/resolv.conv' when the VPN is up.
    """
    # While OpenVPN is running we need to maintain the cached sudo
    # credentials, otherwise they will time out after 15 minutes or so
    # and we will not be able to kill the OpenVPN process.
    context = [maintain_sudo()]
    if dns_servers:
        dns_servers = ['nameserver ' + server for server in dns_servers]
        context.append(replace_content_as_root('/etc/resolv.conf',
                                               '\n'.join(dns_servers)))

    async with multi_context(*context):
        proc = await start(config, username, password)
        return await supervise(proc)
