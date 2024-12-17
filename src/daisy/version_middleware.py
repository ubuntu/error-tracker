#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2013 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from daisy.version import version_info
from oopsrepository import __version__


class VersionMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            if "revno" in version_info:
                rev = version_info["revno"]
                headers.append(("X-Daisy-Revision-Number", str(rev)))
            ver = ".".join(str(component) for component in __version__[0:3])
            headers.append(("X-Oops-Repository-Version", ver))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)
