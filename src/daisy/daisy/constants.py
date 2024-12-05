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


# The number of days that we use to weight the errors in the average errors per
# calendar day calculation such that an error counts as:
# 
# min(number of days since its first error in the given release, 90) / 90.0
#
# The lower it is, the greater the spikes from user influxes. The higher it is,
# the slower the warning of actual worsening.
# 
# The sum of these weighted errors form the numerator of the average errors per
# calendar day calculation. The denominator is the number of unique machines
# seen in the 90 days prior to the calculated day that are responsible for the
# errors in the numerator. This latter clarification is necessary as we receive
# plenty of errors from non-Official releases.

RAMP_UP = 90
