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
"""Interface to the NordVPN web API.

This module contains a single class, `Client`, which encapsulates
all the methods provided by NordVPN.
"""
from subprocess import SubprocessError
from collections import defaultdict
from hashlib import sha512
import asyncio

from structlog import get_logger
import aiohttp

from ._version import get_versions
from ._utils import async_lru_cache, ping


PORTS = dict(tcp=443, udp=1194)
TRACE = 5  # custom log level


# Low-level utilities

def normalized_hostname(hostname):
    """Return the fully qualified domain name of a NordVPN host."""
    host, *domain = hostname.split('.')
    if not domain:
        return f'{host}.nordvpn.com'
    elif tuple(domain) != ('nordvpn', 'com'):
        raise ValueError(f'invalid NordVPN host {hostname}')
    return hostname


def _config_filename(vpn_host, protocol='tcp'):
    return f'{vpn_host}.{protocol}{PORTS[protocol]}'


def _openvpn_compatible(host):
    features = host['features']
    return features['openvpn_udp'] and features['openvpn_tcp']


class Client:
    """Interface to the NordVPN web API.

    Instances of this class can be used as async context managers
    to auto-close the session with the Nord API on exit.

    Parameters
    ----------
    api_url : str, default: 'https://api.nordvpn.com'
    """
    def __init__(self, api_url='https://api.nordvpn.com/'):
        self.api_url = api_url
        client_version = get_versions()['version'].split('+')[0]
        self.headers = {
            'User-Agent': f"nord/{client_version}"
        }
        self._session = aiohttp.ClientSession(raise_for_status=True)
        self._log = get_logger(__name__)

    def close(self):
        """Close the underlying aiohttp.ClientSession."""
        self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_typ, exc, traceback):
        self.close()

    async def _get_json(self, endpoint):
        url = ''.join((self.api_url, endpoint))
        self._log.log(TRACE, f"hitting {url} for JSON")
        async with self._session.get(url, headers=self.headers) as resp:
            return await resp.json()

    async def _get_text(self, endpoint):
        url = ''.join((self.api_url, endpoint))
        self._log.log(TRACE, f"hitting {url} for text")
        async with self._session.get(url, headers=self.headers) as resp:
            return await resp.text()

    # API methods

    @async_lru_cache()
    async def host_config(self, host, protocol='tcp'):
        """Return the OpenVPN config file contents for a NordVPN host.

        Parameters
        ----------
        host : str
            This hostname may be provided either with or without
            the trailing '.nordvpn.com'.
        protocol: str, 'tcp' or 'udp'
        """
        host = normalized_hostname(host)
        endpoint = f'files/download/{_config_filename(host, protocol)}'
        self._log.debug(f"getting host config for {host}")
        return await self._get_text(endpoint)

    async def host_load(self, host=None):
        """Return the load on a NordVPN host.

        Parameters
        ----------
        host : str, optional
            This hostname may be provided either with or without the trailing
            '.nordvpn.com'. If not provided, get the load on all NordVPN hosts.

        Returns
        -------
        load : int or (dict: str → int)
            If 'host' was provided, returns the load on the host as
            a percentage, otherwise returns a map from hostname
            to percentage load.
        """
        if host:
            host = normalized_hostname(host)
        endpoint = f'server/stats/{host}' if host else 'server/stats'
        self._log.debug(f"getting load for "
                        + f"{host}" if host else "all hosts")
        resp = await self._get_json(endpoint)
        if host:
            if len(resp) != 1:
                # Nord API returns load on all hosts if 'host' does not exist.
                raise KeyError(f'{host} does not exist')
            return resp['percent']
        else:
            return {host: load['percent'] for host, load in resp.items()}

    async def current_ip(self):
        """Return our current public IP address, as detected by NordVPN."""
        self._log.debug("getting current IP address")
        return await self._get_text('user/address')

    @async_lru_cache()
    async def host_info(self):
        """Return detailed information about all hosts.

        Returns
        -------
        host_info : (dict: str → dict)
            A map from hostnames to host info dictionaries.
        """
        self._log.debug("getting information on all hosts")
        info = await self._get_json('server')
        return {h['domain']: h for h in info}

    @async_lru_cache()
    async def dns_servers(self):
        """Return a list of ip addresses of NordVPN DNS servers."""
        self._log.debug("getting DNS servers")
        return await self._get_json('dns/smart')

    async def valid_credentials(self, username, password):
        """Return True if NordVPN accepts the username and password.

        Sometimes connecting to the VPN server gives an authentication
        error even if the correct credentials are given. This function
        is useful to first verify credentials so as to avoid unecessary
        reconnection attempts.

        Parameters
        ----------
        username, password : str
        """
        try:
            resp = await self._get_json(f'token/token/{username}')
        except aiohttp.ClientResponseError as error:
            # If the username is incorrect the Nord API returns at 200
            # response, but the mimetype is set to HTML. lol.
            if error.code == 0 and 'unexpected mimetype' in error.message:
                return False
            else:
                raise

        token, salt, key = (resp[k] for k in ['token', 'salt', 'key'])

        round1 = sha512(salt.encode() + password.encode())
        round2 = sha512(round1.hexdigest().encode() + key.encode())
        response = round2.hexdigest()

        try:
            return await self._get_json(f'token/verify/{token}/{response}')
        except aiohttp.ClientResponseError as error:
            if error.code == 401:
                return False
            else:
                raise

    async def rank_hosts(self, country_code, max_load=70, ping_timeout=1):
        """Return hosts ranked by their suitability.

        First, all the NordVPN hosts are filtered to get a list of candidates,
        then the round-trip time is calculated using 'ping', then the
        candidates are sorted according to some scoring function.

        The initial filtering is done based on the country where the host is,
        and the max.

        Parameters
        ----------
        country_code : str
            2-letter country code (e.g. US for United States).
        max_load : int, default: 70
            An integer between 0 and 100. Hosts with a load
            greater than this are filtered out.
        ping_timeout : int
            Each host will be pinged for this amount of time.
            Larger values yield more accurate round-trip times.

        Returns
        -------
        hosts : list of str
            Fully qualified domain names of valid hosts, sorted by their rank.
        """
        country_code = country_code.upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise ValueError("'country_code' must be a 2-letter string")

        max_load = int(max_load)
        if max_load < 0 or max_load > 100:
            raise ValueError("'max_load' must be an integer "
                             "between 0 and 100")

        # filter out invalid hosts
        info = await self.host_info()

        def _valid_host(info):
            return (_openvpn_compatible(info)
                    and info['flag'] == country_code
                    and info['load'] < max_load)

        candidates = [info for info in info.values()
                      if _valid_host(info)]

        if not candidates:
            raise ValueError('No host meets the required criteria')

        # select host from each datacenter with lowest load
        candidates_per_location = defaultdict(lambda: dict(load=float('inf')))
        for c in candidates:
            loc = c['location']['lat'], c['location']['long']
            if c['load'] < candidates_per_location[loc]['load']:
                candidates_per_location[loc] = c

        candidates = [host['domain']
                      for host in candidates_per_location.values()]

        if len(candidates) == 1:
            return candidates

        # Get round-trip time to each datacenter representative.
        # We assume this will be equal for machines in the same
        # datacenter, which justifies our pre-selecting only
        # the host with the smallest load from each datacenter.

        async def _ping(host):
            try:
                return await ping(host, ping_timeout)
            except SubprocessError:
                return float('inf')

        self._log.info(f"pinging {len(candidates)} servers")
        self._log.debug(f"pinging {candidates}")
        host_rtt = await asyncio.gather(*[_ping(host) for host in candidates])
        for host, rtt in zip(candidates, host_rtt):
            info[host]['rtt'] = rtt

        # sort by candidate score

        def _score(host):
            load, rtt = info[host]['load'], info[host]['rtt']
            # TODO: come up with a better ranking
            return (load / max_load) * rtt

        return sorted(candidates, key=_score)
