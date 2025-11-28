#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright © 2011-2015 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
#         Brian Murray <brian.murray@canonical.com>
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

from errors.version import version_info as errors_version_info
from daisy.version import version_info as daisy_version_info


class VersionMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            if "revno" in daisy_version_info:
                headers.append(("X-Daisy-Revision-Number", str(daisy_version_info["revno"])))
            if "revno" in errors_version_info:
                headers.append(("X-Errors-Revision-Number", str(errors_version_info["revno"])))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)
