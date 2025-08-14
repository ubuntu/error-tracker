import logging
import re
import socket
import uuid

import apt
from amqp import ConnectionError as AMQPConnectionException

from oopsrepository import oopses

# From oops-amqp
# These exception types always indicate an AMQP connection error/closure.
# However you should catch amqplib_error_types and post-filter with
# is_amqplib_connection_error.
amqplib_connection_errors = (socket.error, AMQPConnectionException)
# A tuple to reduce duplication in different code paths. Lists the types of
# exceptions legitimately raised by amqplib when the AMQP server goes down.
# Not all exceptions *will* be such errors - use is_amqplib_connection_error to
# do a second-stage filter after catching the exception.
amqplib_error_types = amqplib_connection_errors + (IOError,)

EOL_RELEASES = {
    "Ubuntu 10.04": "lucid",
    "Ubuntu 10.10": "maverick",
    "Ubuntu 11.04": "natty",
    "Ubuntu 11.10": "oneiric",
    "Ubuntu 12.04": "precise",
    "Ubuntu 12.10": "quantal",
    "Ubuntu 13.04": "raring",
    "Ubuntu 13.10": "saucy",
    "Ubuntu 14.04": "trusty",
    "Ubuntu RTM 14.09": "vivid",
    "Ubuntu 14.10": "utopic",
    "Ubuntu 15.04": "vivid",
    "Ubuntu 15.10": "wily",
    "Ubuntu 16.04": "xenial",
    "Ubuntu 16.10": "yakkety",
    "Ubuntu 17.04": "zesty",
    "Ubuntu 17.10": "artful",
    "Ubuntu 18.04": "bionic",
    "Ubuntu 18.10": "cosmic",
    "Ubuntu 19.04": "disco",
    "Ubuntu 19.10": "eoan",
    "Ubuntu 20.10": "groovy",
    "Ubuntu 21.04": "hirsute",
    "Ubuntu 21.10": "impish",
    "Ubuntu 22.10": "kinetic",
    "Ubuntu 23.04": "lunar",
    "Ubuntu 23.10": "mantic",
}


def get_fields_for_bucket_counters(problem_type, release, package, version, pkg_arch):
    fields = []
    if release:
        if package and version:
            fields.append("%s:%s:%s" % (release, package, version))
            fields.append("%s:%s" % (release, package))
            fields.append(release)
            fields.append("%s:%s" % (package, version))
            fields.append(package)
            if pkg_arch:
                fields.append("%s:%s:%s:%s" % (release, package, version, pkg_arch))
                fields.append("%s:%s:%s" % (release, package, pkg_arch))
                fields.append("%s:%s" % (release, pkg_arch))
                fields.append("%s:%s:%s" % (package, version, pkg_arch))
                fields.append("%s:%s" % (package, pkg_arch))
                fields.append("%s" % pkg_arch)
        else:
            fields.append(release)
            # package w/o version is somewhat useful, version w/o package
            # isn't so only record this counter
            if package:
                fields.append("%s:%s" % (release, package))
                fields.append(package)
            if pkg_arch:
                fields.append("%s:%s" % (release, pkg_arch))
                fields.append("%s" % pkg_arch)
    elif package and version:
        fields.append("%s:%s" % (package, version))
        fields.append("%s" % (package))
        if pkg_arch:
            fields.append("%s:%s:%s" % (package, version, pkg_arch))
            fields.append("%s:%s" % (package, pkg_arch))
            fields.append("%s" % pkg_arch)

    if problem_type:
        fields.extend(["%s:%s" % (problem_type, field) for field in fields])
    return fields


def split_package_and_version(package):
    if not package:
        return ("", "")
    s = package.split()[:2]
    if len(s) == 2:
        package, version = s
    else:
        package, version = (package, "")
    if version == "(not":
        # The version is set to '(not installed)'
        version = ""
    # according to debian policy neither the package or version should have
    # utf8 in it but either some archives do not know that or something is
    # wonky with apport
    package = package.encode("ascii", errors="replace").decode()
    version = version.encode("ascii", errors="replace").decode()
    return (package, version)


def get_package_architecture(report_dict):
    # return the system arch if the package is arch all
    pkg_arch = report_dict.get("PackageArchitecture", "")
    if pkg_arch == "all":
        arch = report_dict.get("Architecture", "")
        pkg_arch = arch
    elif pkg_arch == "unknown":
        pkg_arch = ""
    return pkg_arch


def format_crash_signature(crash_signature) -> str:
    # https://errors.ubuntu.com/oops-local/2013-03-07/50428.daisy.ubuntu.com3
    # Exception-Value: InvalidRequestException(why='Key length of 127727 is
    # longer than maximum of 65535')
    # We use 32768 rather than 65535 to provide padding when the bucket ID
    # forms part of a composite key, as it does in daybuckets.
    if not crash_signature:
        return ""

    # Translate back to unicode so we can correctly slice this.
    if type(crash_signature) is bytes:
        crash_signature = crash_signature.decode("utf-8")

    crash_signature = crash_signature[:32768]

    return crash_signature


def bucket(oops_config, oops_id, crash_signature, report_dict):
    release = report_dict.get("DistroRelease", "")
    package = report_dict.get("Package", "")
    src_package = report_dict.get("SourcePackage", "")
    problem_type = report_dict.get("ProblemType", "")
    dependencies = report_dict.get("Dependencies", "")
    system_uuid = report_dict.get("SystemIdentifier", "")

    if "[origin:" in package or "[origin:" in dependencies:
        # This package came from a third-party source. We do not want to show
        # its version as the Last Seen field on the most common problems table,
        # so skip updating the bucket metadata.
        third_party = True
    else:
        third_party = False

    version = None
    if package:
        package, version = split_package_and_version(package)
    pkg_arch = get_package_architecture(report_dict)

    automated_testing = False
    if system_uuid.startswith("deadbeef"):
        automated_testing = True

    if automated_testing:
        fields = None
    else:
        fields = get_fields_for_bucket_counters(
            problem_type, release, package, version, pkg_arch
        )
    if version:
        oopses.update_bucket_systems(
            oops_config, crash_signature, system_uuid, version=version
        )
    # DayBucketsCount is only added to if fields is not None, so set fields to
    # None for crashes from systems running automated tests.
    oopses.bucket(oops_config, oops_id, crash_signature, fields)

    if hasattr(oopses, "update_bucket_hashes"):
        oopses.update_bucket_hashes(oops_config, crash_signature)

    # BucketMetadata is displayed on the main page and shouldn't include
    # derivative or custom releases, so don't write them to the table.
    release_re = re.compile(r"^Ubuntu \d\d.\d\d$")
    if (package and version) and release_re.match(release):
        oopses.update_bucket_metadata(
            oops_config,
            crash_signature,
            package,
            version,
            apt.apt_pkg.version_compare,
            release,
        )
        if hasattr(oopses, "update_source_version_buckets"):
            oopses.update_source_version_buckets(
                oops_config, src_package, version, crash_signature
            )
    if version and release:
        oopses.update_bucket_versions(
            oops_config, crash_signature, version, release=release, oopsid=oops_id
        )

    if hasattr(oopses, "update_errors_by_release"):
        if (system_uuid and release) and not third_party:
            oops_uuid = uuid.UUID(oops_id)
            oopses.update_errors_by_release(
                oops_config, oops_uuid, system_uuid, release
            )


def attach_error_report(report, context):
    # We only attach error report that was submitted by the client if we've hit
    # a MaximumRetryException from Cassandra.
    if "type" in report and report["type"] == "MaximumRetryException":
        env = context["wsgi_environ"]
        if "wsgi.input.decoded" in env:
            data = env["wsgi.input.decoded"]
            if "req_vars" not in report:
                report["req_vars"] = {}
            report["req_vars"]["wsgi.input.decoded"] = data


def wrap_in_oops_wsgi(wsgi_handler):
    import oops_dictconfig
    from oops_wsgi import install_hooks, make_app

    from daisy import config

    cfg = oops_dictconfig.config_from_dict(config.oops_config)
    cfg.template["reporter"] = "daisy"
    install_hooks(cfg)
    return make_app(wsgi_handler, cfg, oops_on_status=["500"])


def retraceable_release(release):
    if release in EOL_RELEASES:
        logging.info("%s is EoL, not retraceable", release)
        return False
    derivative_re = re.compile(r"^Ubuntu( RTM| Kylin)? \d\d.\d\d$")
    if derivative_re.match(release):
        return True
    else:
        logging.info("%s doesn't match %s, not retraceable", release, derivative_re)
        return False


def retraceable_package(package):
    if "[origin: " not in package:
        return True
    elif "[origin: Ubuntu RTM]" in package:
        return True
    # confirm how this can happen
    # elif "[origin: Ubuntu]" in package:
    #     return True
    elif "[origin: LP-PPA-ci-train-ppa-service" in package:
        return True
    else:
        return False


def blocklisted_device(system_token):
    """Return True if a device is not allowed to report crashes.

    Used for devices that have repeatedly failed to submit a crash.
    """

    blocklist = [
        # 20150814 - OOPS count was at 43
        "2f175cea621bda810f267f1da46409a111f58011435f410aa198362e9372da78b6fafe6827ff26e025a5ab7d2859346de6b188f0622118c15a119c58ca538acb",
        # 20150826 - OOPS count was at 18
        "81b75a0bdd531a5c02a4455b05674ea45fbb65324bcae5fe51659bce850aa40bcd1388e3eed4d46ce9abb4e56d1dd7dde45ded473995feb0ac2c01518a841efe",
        # 20150903 - OOPS count was at 27
        "b5329547bdab8adea4245399ff9656ca608e825425fbb0ad2c68e182b75ce80c13f9186e4e9b8e7a17dd15dd196b12a65e1b7f513184296320dad50c587754f5",
    ]
    if system_token in blocklist:
        return True
    return False


# From oops-amqp
def is_amqplib_ioerror(e):
    """Returns True if e is an amqplib internal exception."""
    # Raised by amqplib rather than socket.error on ssl issues and short reads.
    if type(e) is not IOError:
        return False
    if e.args == ("Socket error",) or e.args == ("Socket closed",):
        return True
    return False


# From oops-amqp
def is_amqplib_connection_error(e):
    """Return True if e was (probably) raised due to a connection issue."""
    return isinstance(e, amqplib_connection_errors) or is_amqplib_ioerror(e)
