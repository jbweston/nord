# -*- coding: utf-8 -*-
#
# copyright 2017 joseph weston
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
"""Miscellaneous utilities."""

import os
import fcntl
import tempfile
import functools as ft
import asyncio
from asyncio.subprocess import PIPE, DEVNULL
from asyncio import create_subprocess_exec as subprocess
from subprocess import SubprocessError
from collections import OrderedDict
from pathlib import Path

from decorator import decorator


# Generic utilities

def silence(*exceptions_to_silence):
    """Catch and discard selected exception types.

    this is a coroutine decorator.
    """

    async def _wrapper(func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as error:
            if not isinstance(error, exceptions_to_silence):
                raise

    return decorator(_wrapper)


class MultiError(Exception):
    """Combine several exceptions"""
    def __init__(self, *exceptions):
        super().__init__()
        self.children = exceptions

    def __str__(self):
        return ','.join(repr(c) for c in self.children)


class multi_context:  # pylint: disable=invalid-name,too-few-public-methods
    """Async context manager that manages several child contexts."""

    def __init__(self, *managers):
        self.managers = managers

    async def __aenter__(self):
        futures = [asyncio.ensure_future(m.__aenter__())
                   for m in self.managers]
        await asyncio.wait(futures)  # make sure all are run to completion
        exceptions = [f.exception() for f in futures if f.exception()]
        if exceptions:
            first_exception, *other_exceptions = exceptions
            if not other_exceptions:
                raise first_exception
            else:
                MultiError(first_exception, *other_exceptions)

    async def __aexit__(self, *exc_details):
        futures = [m.__aexit__(*exc_details) for m in self.managers]
        await asyncio.wait(futures)  # make sure all are run to completion


@decorator
def run_sync(func, *args, **kwargs):
    """Run the decorated coroutine synchronouslyin the default event loop.

    This decordator converts an async function to a regular function.
    """
    return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))


# Created by Github user 'jaredlunde':
# https://gist.github.com/jaredlunde/7a118c03c3e9b925f2bf
# with minor modifications.
def async_lru_cache(size=float('inf')):
    """LRU cache for coroutines."""
    cache = OrderedDict()

    async def _memoized(func, *args, **kwargs):
        key = str((args, kwargs))
        if key not in cache:
            if len(cache) >= size:
                cache.popitem(last=False)
            cache[key] = await func(*args, **kwargs)
        return cache[key]

    return decorator(_memoized)


def write_to_tmp(content):
    """Write text content to a temporary file a return a handle to it."""
    tmp = tempfile.NamedTemporaryFile(mode='w+t')
    tmp.write(content)
    tmp.flush()
    return tmp


# Sudo-related functions

async def sudo_requires_password():
    """Return True if 'sudo' requires a password to run."""
    proc = await subprocess('sudo', '-n', '-v', stdout=DEVNULL, stderr=DEVNULL)
    await proc.wait()
    return proc.returncode != 0


async def prompt_for_sudo():
    """Run 'sudo' to prompt the user for their password."""
    proc = await subprocess('sudo', '-v')
    await proc.wait()
    if proc.returncode != 0:
        raise PermissionError('sudo requires a password')


@decorator
async def require_sudo(func, *args, **kwargs):
    """Raise PermissionError if 'sudo' cannot be used without a password."""
    if await sudo_requires_password():
        raise PermissionError('sudo requires a password')
    else:
        return await func(*args, **kwargs)


class maintain_sudo:  # pylint: disable=invalid-name,too-few-public-methods
    """Run 'sudo -v' every 'timeout' seconds to maintain cached credentials."""

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.maintainer = None

    async def __aenter__(self):
        if await sudo_requires_password():
            raise PermissionError('sudo requires password')

        async def _maintainer():
            while True:
                await asyncio.wait([prompt_for_sudo(),
                                    asyncio.sleep(self.timeout)])

        self.maintainer = asyncio.ensure_future(_maintainer())

    async def __aexit__(self, *exc_info):
        self.maintainer.cancel()
        await self.maintainer


# Functions requiring sudo

@silence(ProcessLookupError)
@require_sudo
async def kill_root_process(proc, timeout=None):
    """Terminate a process owned by root as gracefully as possible.

    sends sigterm and follows up with a sigkill if the process is not
    dead after 'timeout' seconds, and flushes stdout and stderr
    by calling 'proc.communicate()'.

    Parameters
    ----------
    proc : asyncio.subprocess.process
    timeout : int
    """
    kill_cmd = ['sudo', '-n', 'kill']
    pid = str(proc.pid)
    try:
        killer = await subprocess(*kill_cmd, pid, stdout=DEVNULL,
                                  stderr=DEVNULL)
        await killer.wait()
        await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:  # process didn't die in time
        killer = await subprocess(*kill_cmd, '-9', pid, stdout=DEVNULL,
                                  stderr=DEVNULL)
        await killer.wait()
    finally:
        # flush buffers
        await proc.communicate()


class replace_content_as_root:
    # pylint: disable=invalid-name,too-few-public-methods
    """Context manager that replaces a file's content and restores it on exit.

    This context manager uses subprocesses and 'sudo' with 'cat' and 'tee'
    to write the files, to avoid giving root permissions to *this* process.

    Parameters
    ----------
    path, content : str

    Raises
    ------
    FileNotFoundError if no file exists at 'path'
    PermissionError if 'sudo' cannot be used without a password.
    RuntimeError if we were unable to read or write the file at 'path'
    """

    def __init__(self, path, content):
        self.path = str(Path(path).resolve())
        self.content = content.encode()
        self.saved_content = None
        self._write_content = ['sudo', '-n', 'tee', self.path]
        self._read_content = ['sudo', '-n', 'cat', self.path]

    async def __aenter__(self):
        # can't use 'require_sudo' decorator as this is an async generator.
        if await sudo_requires_password():
            raise PermissionError('sudo requires a password')

        # get existing content from file
        proc = await subprocess(*self._read_content, stdout=PIPE, stderr=PIPE)
        self.saved_content, errors = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(errors.decode())

        # write temporary content to file
        proc = await subprocess(*self._write_content, stdout=DEVNULL,
                                stderr=PIPE, stdin=PIPE)
        _, errors = await proc.communicate(self.content)
        if proc.returncode != 0:
            raise RuntimeError(errors.decode())

    async def __aexit__(self, *exc_info):
        # restore saved content
        proc = await subprocess(*self._write_content, stdout=DEVNULL,
                                stderr=PIPE, stdin=PIPE)
        _, errors = await proc.communicate(self.saved_content)
        if proc.returncode != 0:
            raise RuntimeError(errors.decode())


# File locking

class LockError(BlockingIOError):
    """Exception raised on failure to acquire a file lock/"""
    pass


async def lock_subprocess(*args, lockfile, **kwargs):
    """Acquire a lock for launching a subprocess.

    Acquires a lock on a lockfile, launches a subprocess
    and schedules unlocking the lockfile for when the
    subprocess is dead.

    Parameters
    ----------
    *args, **kwargs
        Arguments to pass to 'asyncio.subprocess.create_subprocess_exec'.
    lockfile : str
        Filename of the lockfile.

    Returns
    -------
    proc : asyncio.subprocess.Process

    Raises
    ------
    LockError if the lock could not be acquired.
    """

    file = open(lockfile, 'w', opener=ft.partial(os.open, mode=0o600))
    try:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise LockError(lockfile) from error
    file.write(str(os.getpid()))  # write pid to lockfile
    file.flush()

    def _unlock(*_):
        fcntl.flock(file, fcntl.LOCK_UN)
        file.truncate(0)
        file.close()

    try:
        proc = await subprocess(*args, **kwargs)
    except:
        _unlock()
        raise
    else:
        when_dead = asyncio.ensure_future(proc.wait())
        when_dead.add_done_callback(_unlock)

    return proc


async def ping(host, timeout):
    """Return the round-trip time to a host using ICMP ECHO.

    Parameters
    ----------
    host : str
        The host to ping. May be a hostname, ip address, or anything else
        recognized by 'ping'.
    timeout : int
        Time in seconds after which to stop waiting for a response.

    Returns
    -------
    rtt : float
        The average round trip time in milliseconds.

    Raises
    ------
    SubprocessError if 'ping' returns a non-zero exit code.
    """
    cmd = f"/bin/ping -w{int(timeout)} {host}"
    proc = await asyncio.create_subprocess_exec(*cmd.split(),
                                                stdout=PIPE, stderr=DEVNULL)
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        raise SubprocessError(proc.returncode)

    *_, rtt_line, _ = stdout.decode().split('\n')
    assert _ == ''  # sanity check
    *_, data, _ = rtt_line.split()
    _, avg, *_ = data.split('/')
    return float(avg)
