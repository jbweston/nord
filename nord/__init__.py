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
"""NordVPN client."""

import logging
import structlog

from ._version import __version__
del _version  # pylint: disable=undefined-variable

from . import vpn, api


# Set up default logging on import, in case nord is used as a library

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%x:%X", utc=False),
        structlog.processors.UnicodeDecoder(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
    context_class=dict,
)

# pylint: disable=protected-access
structlog.stdlib.TRACE = 5
structlog.stdlib._NAME_TO_LEVEL['trace'] = 5
structlog.stdlib._LEVEL_TO_NAME[5] = 'trace'
logging.addLevelName(5, "TRACE")

# Even after we remove these references, these are still present in
# sys.modules, so they remain loaded.
del structlog
del logging
