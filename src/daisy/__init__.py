from functools import reduce

# !/usr/bin/python
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

config = None
try:
    import local_config as config
except ImportError:
    pass
if not config:
    from daisy import configuration as config


def validate_and_set_configuration():
    """Validate the set configuration at module import time, to prevent
    exceptions at random points during the lifetime of the application.

    This will modify the in-memory configuration data if deprecated parameters
    are used, to structure them in the non-deprecated format."""

    write_weights = getattr(config, "storage_write_weights", "")
    core_storage = getattr(config, "core_storage", "")
    if core_storage and not write_weights:
        msg = "storage_write_weights must be set alongside core_storge."
        raise ImportError(msg)
    if not core_storage:
        swift = getattr(config, "swift_bucket", "")
        ec2 = getattr(config, "ec2_bucket", "")
        local = getattr(config, "san_path", "")
        if ec2 and swift:
            raise ImportError("ec2_bucket and swift_bucket cannot both be set.")

        # Match the old behaviour. Put everything on swift, if available.
        # Failing that, fall back to EC2, then local.
        if swift:
            # If there is no swift configuration set in local_config or the
            # default config check swift_config as that's what the charms
            # write to. Yes, this is messy and there should be a better
            # solution.
            try:
                import swift_config
            except ImportError:
                pass
            os_auth_url = getattr(config, "os_auth_url", "")
            if not os_auth_url:
                os_auth_url = getattr(swift_config, "os_auth_url", "")
            os_username = getattr(config, "os_username", "")
            if not os_username:
                os_username = getattr(swift_config, "os_username", "")
            os_password = getattr(config, "os_password", "")
            if not os_password:
                os_password = getattr(swift_config, "os_password", "")
            os_tenant_name = getattr(config, "os_tenant_name", "")
            if not os_tenant_name:
                os_tenant_name = getattr(swift_config, "os_tenant_name", "")
            os_region_name = getattr(config, "os_region_name", "")
            if not os_region_name:
                os_region_name = getattr(swift_config, "os_region_name", "")
            config.storage_write_weights = {"swift": 1.0}
            config.core_storage = {
                "default": "swift",
                "swift": {
                    "type": "swift",
                    "bucket": swift,
                    "os_auth_url": os_auth_url,
                    "os_username": os_username,
                    "os_password": os_password,
                    "os_tenant_name": os_tenant_name,
                    "os_region_name": os_region_name,
                },
            }
        elif ec2:
            host = getattr(config, "ec2_host", "")
            aws_access_key = getattr(config, "aws_access_key", "")
            aws_secret_key = getattr(config, "aws_secret_key", "")
            if not (host and aws_access_key and aws_secret_key):
                msg = (
                    "EC2 provider set but host, bucket, aws_access_key, or"
                    " aws_secret_key not set."
                )
                raise ImportError(msg)
            config.storage_write_weights = {"s3": 1.0}
            config.core_storage = {
                "default": "s3",
                "s3": {
                    "type": "s3",
                    "host": host,
                    "bucket": ec2,
                    "aws_access_key": aws_access_key,
                    "aws_secret_key": aws_secret_key,
                },
            }
        elif local:
            config.storage_write_weights = {"local": 1.0}
            config.core_storage = {
                "default": "local",
                "local": {"type": "local", "path": local},
            }
        else:
            raise ImportError("no core storage provider is set.")

    if not getattr(config, "storage_write_weights", ""):
        d = config.core_storage.get("default", "")
        if not d:
            msg = "No storage_write_weights set, but no default set in core" " storage"
            raise ImportError(msg)
        config.storage_write_weights = {d: 1.0}

    for k, v in config.core_storage.items():
        if k == "default":
            continue
        t = v.get("type", "")
        if not t:
            raise ImportError("You must set a type for %s." % k)
        if t == "swift":
            keys = [
                "bucket",
                "os_auth_url",
                "os_username",
                "os_password",
                "os_tenant_name",
                "os_region_name",
            ]
        elif t == "s3":
            keys = ["host", "bucket", "aws_access_key", "aws_secret_key"]
        elif t == "local":
            keys = ["path"]
        missing = set(keys) - set(v.keys())
        if missing:
            missing = ", ".join(missing)
            raise ImportError("Missing keys for %s: %s." % (k, missing))

    if reduce(lambda x, y: x + y, list(config.storage_write_weights.values())) != 1.0:
        msg = "storage_write_weights values do not add up to 1.0."
        raise ImportError(msg)


def gen_write_weight_ranges(d):
    total = 0
    r = {}
    for key, val in d.items():
        r[key] = (total, total + val)
        total += val
    return r


validate_and_set_configuration()

config.write_weight_ranges = None
if getattr(config, "storage_write_weights", ""):
    ranges = gen_write_weight_ranges(config.storage_write_weights)
    config.write_weight_ranges = ranges
