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
import asyncio
from asyncio.subprocess import PIPE, DEVNULL
from collections import OrderedDict
from pathlib import Path

from asyncio_extras.contextmanager import async_contextmanager
from decorator import decorator


def silence(*exceptions_to_silence):
    """Catch and discard selected exception types.

    this is a coroutine decorator.
    """

    # pylint: disable=missing-docstring
    async def wrapper(func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as error:
            if not isinstance(error, exceptions_to_silence):
                raise

    return decorator(wrapper)


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

    # pylint: disable=missing-docstring
    async def memoized(func, *args, **kwargs):
        key = str((args, kwargs))
        if key not in cache:
            if len(cache) >= size:
                cache.popitem(last=False)
            cache[key] = await func(*args, **kwargs)
        return cache[key]

    return decorator(memoized)


def write_to_tmp(content):
    """Write text content to a temporary file a return a handle to it."""
    tmp = tempfile.NamedTemporaryFile(mode='w+t')
    tmp.write(content)
    tmp.flush()
    return tmp


def _secure_opener(path, flags):
    return os.open(path, flags, mode=0o600)


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

    file = open(lockfile, 'w', opener=_secure_opener)
    try:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise LockError(lockfile) from error
    file.write(str(os.getpid()))  # write pid to lockfile
    file.flush()

    # pylint: disable=missing-docstring
    def unlock(*_):
        fcntl.flock(file, fcntl.LOCK_UN)
        file.truncate(0)
        file.close()

    try:
        proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    except:
        unlock()
        raise
    else:
        when_dead = asyncio.ensure_future(proc.wait())
        when_dead.add_done_callback(unlock)

    return proc


@silence(ProcessLookupError)
async def kill_process(proc, timeout=None):
    """Terminate a process as gracefully as possible.

    sends sigterm and follows up with a sigkill if the process is not
    dead after 'timeout' seconds, and flushes stdout and stderr
    by calling 'proc.communicate()'.

    Parameters
    ----------
    proc : asyncio.subprocess.process
    timeout : int
    """
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:  # process didn't die in time
        proc.kill()
    finally:
        # flush buffers
        await proc.communicate()


@decorator
async def require_root(func, *args, **kwargs):
    """Raise PermissionError if 'sudo' cannot be used without a password."""
    if (await sudo_requires_password()):
        raise PermissionError('sudo requires a password')
    else:
        return await func(*args, **kwargs)


async def sudo_requires_password():
    """Return True if 'sudo' requires a password to run."""
    proc = await asyncio.create_subprocess_exec(
        'sudo', '-n', '-v',
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    return proc.returncode != 0


async def prompt_for_sudo():
    """Run 'sudo' to prompt the user for their password."""
    proc = await asyncio.create_subprocess_exec('sudo', '-v')
    await proc.wait()
    if proc.returncode != 0:
        raise PermissionError('sudo requires a password')


@async_contextmanager
@require_root
async def replace_content_as_root(path, content):
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

    # get existing content from file
    path = Path(path).resolve()
    get_content = ['sudo', '-n', 'cat',  path]
    proc = await asyncio.create_subprocess_exec(*get_content,
                                                stdout=PIPE, stderr=PIPE)
    saved_content, errors = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(errors.decode())

    # write temporary content to file
    write_content = ['sudo', '-n', 'tee', path]
    proc = await asyncio.create_subprocess_exec(*write_content,
                                                stdout=DEVNULL, stderr=PIPE,
                                                stdin=PIPE)
    _, errors = await proc.communicate(content.encode())
    if proc.returncode != 0:
        raise RuntimeError(errors.decode())

    try:
        yield
    finally:
        # restore saved content
        proc = await asyncio.create_subprocess_exec(*write_content,
                                                    stdout=DEVNULL,
                                                    stderr=PIPE,
                                                    stdin=PIPE)
        _, errors = await proc.communicate(saved_content)
        if proc.returncode != 0:
            raise RuntimeError(errors.decode())


