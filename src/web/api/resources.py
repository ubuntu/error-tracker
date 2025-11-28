# Treat strings as UTF-8 instead of ASCII
import sys
from functools import cmp_to_key
import importlib
importlib.reload(sys)
sys.setdefaultencoding('UTF8')

from tastypie.resources import Resource
from tastypie.exceptions import NotFound
from tastypie import fields
from tastypie.authentication import SessionAuthentication, Authentication
from tastypie.authorization import DjangoAuthorization, Authorization
from errors import cassie

TASTYPIE_FULL_DEBUG = True

from django.core.serializers import json
from tastypie.serializers import Serializer
from ..metrics import measure_view
from daisy import launchpad, config
from operator import itemgetter
import apt
import datetime
import json as simplejson
from hashlib import sha1
from urllib.parse import quote
from urllib.parse import unquote

from urllib.error import HTTPError
from collections import OrderedDict

release_color_mapping = OrderedDict()

# If you add or change colors here, also update the colors in
# errors/static/js/most_common_problems.js and
# errors/static/js/retracers.js .

# mpt says they should follow a ROYGBV pattern
# XXX: release colors could repeat (except for LTSes) as they will not appear
# on the same graph e.g. 14.10 and 17.10 will not both be supported at the
# same time
release_color_mapping['Ubuntu 12.04'] = '#29b458' # green
release_color_mapping['Ubuntu 12.10'] = '#05b8ea' # blue
release_color_mapping['Ubuntu 13.04'] = '#4f2f8e' # violet
release_color_mapping['Ubuntu 13.10'] = '#d20700' # red
release_color_mapping['Ubuntu 14.04'] = '#ff8b00' # orange
release_color_mapping['Ubuntu 14.10'] = '#d9c200' # yellow
release_color_mapping['Ubuntu 15.04'] = '#00e600' # green
release_color_mapping['Ubuntu 15.10'] = '#05ead3' # blue
release_color_mapping['Ubuntu 16.04'] = '#7e2f8e' # violet
release_color_mapping['Ubuntu 16.10'] = '#ff0900' # red
release_color_mapping['Ubuntu 17.04'] = '#ffae00' # orange
release_color_mapping['Ubuntu 17.10'] = '#ffe81a' # yellow
release_color_mapping['Ubuntu 18.04'] = '#228b22' # green
release_color_mapping['Ubuntu 18.10'] = '#0066ff' # blue
release_color_mapping['Ubuntu 19.04'] = '#b353c6' # violet
release_color_mapping['Ubuntu 19.10'] = '#d20700' # red
release_color_mapping['Ubuntu 20.04'] = '#dd4814' # orange
release_color_mapping['Ubuntu 20.10'] = '#d9c200' # yellow
release_color_mapping['Ubuntu 21.04'] = '#00e600' # green
release_color_mapping['Ubuntu 21.10'] = '#05ead3' # blue
release_color_mapping['Ubuntu 22.04'] = '#7e2f8e' # violet
release_color_mapping['Ubuntu 22.10'] = '#ff0900' # red
release_color_mapping['Ubuntu 23.04'] = '#ffae00' # orange
release_color_mapping['Ubuntu 23.10'] = '#ffe81a' # yellow
release_color_mapping['Ubuntu 24.04'] = '#00e600' # green
release_color_mapping['Ubuntu 24.10'] = '#05b8ea' # blue
release_color_mapping['Ubuntu 25.04'] = '#7e2f8e' # violet
release_color_mapping['Ubuntu 25.10'] = '#ff0900' # red
release_color_mapping['Ubuntu 26.04'] = '#ffae00' # orange

precise_standards_color_mapping = {
    'Ubuntu 12.10': '#8edbf4',
    'Ubuntu 13.04': '#9f8acb',
    'Ubuntu 13.10': '#d26c69',
    'Ubuntu 14.04': '#ffc580',
    'Ubuntu 14.10': '#ece180',
    'Ubuntu 15.04': '#73e673',
    'Ubuntu 15.10': '#00faed',
    'Ubuntu 16.04': '#9859a5',
    'Ubuntu 16.10': '#ff524d',
    'Ubuntu 17.04': '#fabd39',
    'Ubuntu 17.10': '#f5efbc',
    'Ubuntu 18.04': '#32cd32',
    'Ubuntu 18.10': '#99c2ff',
    'Ubuntu 19.04': '#b88bc1',
    'Ubuntu 19.10': '#d26c69',
    'Ubuntu 20.04': '#f29573',
    'Ubuntu 20.10': '#ece180',
    'Ubuntu 21.04': '#73e673',
    'Ubuntu 21.10': '#00faed',
    'Ubuntu 22.04': '#9859a5',
    'Ubuntu 22.10': '#ff524d',
    'Ubuntu 23.04': '#fabd39',
    'Ubuntu 23.10': '#f5efbc',
    'Ubuntu 24.04': '#73e673',
    'Ubuntu 24.10': '#8edbf4',
    'Ubuntu 25.04': '#00faed',
    'Ubuntu 25.10': '#9859a5',
    'Ubuntu 26.04': '#fabd39'
}
# mapping of releases to codenames
codenames = {
        'Ubuntu 12.04': 'precise',
        'Ubuntu 12.10': 'quantal',
        'Ubuntu 13.04': 'raring',
        'Ubuntu 13.10': 'saucy',
        'Ubuntu 14.04': 'trusty',
        'Ubuntu RTM 14.09': 'rtm-14.09',
        'Ubuntu 14.10': 'utopic',
        'Ubuntu 15.04': 'vivid',
        'Ubuntu 15.10': 'wily',
        'Ubuntu 16.04': 'xenial',
        'Ubuntu 16.10': 'yakkety',
        'Ubuntu 17.04': 'zesty',
        'Ubuntu 17.10': 'artful',
        'Ubuntu 18.04': 'bionic',
        'Ubuntu 18.10': 'cosmic',
        'Ubuntu 19.04': 'disco',
        'Ubuntu 19.10': 'eoan',
        'Ubuntu 20.04': 'focal',
        'Ubuntu 20.10': 'groovy',
        'Ubuntu 21.04': 'hirsute',
        'Ubuntu 21.10': 'impish',
        'Ubuntu 22.04': 'jammy',
        'Ubuntu 22.10': 'kinetic',
        'Ubuntu 23.04': 'lunar',
        'Ubuntu 23.10': 'mantic',
        'Ubuntu 24.04': 'noble',
        'Ubuntu 24.10': 'oracular',
        'Ubuntu 25.04': 'plucky',
        'Ubuntu 25.10': 'questing',
        'Ubuntu 26.04': 'resolute'
}


class APIAuthentication(Authentication):
    def is_authenticated(self, request, **kwargs):
        authorization = request.META.get("HTTP_AUTHORIZATION", None)
        if authorization in config.api_keys:
          return True

        return False


class PrettyJSONSerializer(Serializer):
    json_indent = 2

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        return simplejson.dumps(data, cls=json.DjangoJSONEncoder,
                sort_keys=True, ensure_ascii=False, indent=self.json_indent)

class ResultObject(object):
    def __init__(self, initial=None):
        self.__dict__['_data'] = {}

        if hasattr(initial, 'items'):
            self.__dict__['_data'] = initial

    def __getattr__(self, name):
        return self._data.get(name, None)

    def __setattr__(self, name, value):
        self.__dict__['_data'][name] = value

    def to_dict(self):
        return self._data


class ErrorsResource(Resource):
    # Wrap the view dispatch with a statsd timing.
    @measure_view
    def dispatch(self, *args, **kwargs):
        return Resource.dispatch(self, *args, **kwargs)

    def _handle_500(self, request, exception):
        # Create an OOPS report, then reply with a json-formatted error
        # message.
        import traceback
        formatted = traceback.format_exc(exception)
        exc_info = (type(exception), exception.args[0], formatted)
        request.environ['oops.context']['exc_info'] = exc_info
        return Resource._handle_500(self, request, exception)

class ErrorsMeta:
    object_class = ResultObject
    serializer = PrettyJSONSerializer()
    # Do not include resource_uri = '' on each date
    include_resource_uri = False
    allowed_methods = ['get']
    # The default number of rows to fetch from Cassandra
    limit = 7
    max_limit = 30 * 12

class RetraceResultResource(ErrorsResource):
    date = fields.CharField(attribute='date')
    value = fields.DictField(attribute='value', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'retracers-results'

    def obj_get_list(self, bundle):
        # The results are wrapped in the slice operation for a list to follow
        # the pattern of lazy evalution that tastypie uses for talking to ORMs.
        # The point at which tastypie attempts to slice a list is the first
        # point that the pagination data is known.
        class wrapped(list):
            def __getslice__(self, start, finish):
                for date, val in cassie.get_retracer_counts(start, finish):
                    yield ResultObject({'date' : date, 'value' : val})
        return wrapped()

    def obj_get(self, request, **kwargs):
        date = kwargs['pk']
        value = cassie.get_retracer_count(date)
        return ResultObject({'date': date, 'value' : value})

class RetraceAverageProcessingTimeResource(ErrorsResource):
    date = fields.CharField(attribute='date')
    value = fields.DictField(attribute='value', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'retracers-average-processing-time'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(self, start, finish):
                for date, result in cassie.get_retracer_means(start, finish):
                    yield ResultObject({'date' : date, 'value' : result})
        return wrapped()

class InstanceCountResource(ErrorsResource):
    release = fields.CharField(attribute='release', readonly=True)
    value = fields.ListField(attribute='value', readonly=True)
    color = fields.CharField(attribute='color', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'instances-count'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(self, start, finish):
                for release in release_color_mapping:
                    results = []
                    counts = cassie.get_crash_count(start, finish, release)
                    for date, result in counts:
                        results.append({'date' : date, 'value' : result})
                    if results:
                        result = {'release' : release, 'value' : results,
                                'color': release_color_mapping[release]}
                        yield ResultObject(result)
        return wrapped()

class ProblemCountResource(ErrorsResource):
    date = fields.CharField(attribute='date')
    value = fields.IntegerField(attribute='value', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'problems-count'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(self, start, finish):
                for date, result in cassie.get_total_buckets_by_day(start, finish):
                    yield ResultObject({'date' : date, 'value' : result})
        return wrapped()


class DayOopsResource(ErrorsResource):
    date = fields.CharField(attribute='date')
    value = fields.DictField(attribute='value', readonly=True)

    class Meta(ErrorsMeta):
        resource_name = 'dayoops'

    def obj_get(self, **kwargs):
        date = kwargs['pk']
        try:
            limit = int(kwargs['bundle'].request.GET.get('limit'))
        except Exception:
            limit = 100
        try:
            release = kwargs['bundle'].request.GET.get('release')
        except Exception:
            release = None
        try:
            details = 'details' in kwargs['bundle'].request.GET
        except Exception:
            details = False
        oopses_by_day = set()
        oopses_by_release = set()
        for oops in cassie.get_oopses_by_day(date, limit):
            oopses_by_day.add(str(oops))
        oopses = oopses_by_day

        if release:
            for oops in cassie.get_oopses_by_release(release, limit):
                oopses_by_release.add(str(oops))

            oopses = set.intersection(oopses_by_day, oopses_by_release)

        results = []
        if details:
            for oops in oopses:
                oops_details = cassie.get_crash(str(oops), columns=["ProblemType"])
                results.append({"id": str(oops), "details": oops_details})
        else:
            results = list(oopses)
        return ResultObject({'date': date, 'value' : {"oopses": results}})


class MostCommonProblemsResource(ErrorsResource):
    rank = fields.IntegerField(attribute='rank')
    count = fields.IntegerField(attribute='count')
    package = fields.CharField(attribute='package')
    first_seen = fields.CharField(attribute='first_seen')
    last_seen = fields.CharField(attribute='last_seen')
    first_seen_release = fields.CharField(attribute='first_seen_release')
    last_seen_release = fields.CharField(attribute='last_seen_release')
    function = fields.CharField(attribute='function')
    web_link = fields.CharField(attribute='web_link')
    report = fields.CharField(attribute='report')
    class Meta(ErrorsMeta):
        resource_name = 'most-common-problems'

    def _handle_request(self, bundle, start, finish):
        release = bundle.request.GET.get('release', None)
        rootfs_build_version = bundle.request.GET.get('rootfs_build_version', None)
        channel_name = bundle.request.GET.get('channel_name', None)
        device_name = bundle.request.GET.get('device_name', None)
        device_image_version  = bundle.request.GET.get('device_image_version', None)
        package = bundle.request.GET.get('package', None)
        packageset = bundle.request.GET.get('packageset', None)
        version = bundle.request.GET.get('version', None)
        pkg_arch = bundle.request.GET.get('pkg_arch', None)
        period = bundle.request.GET.get('period', None)
        from_date = str(bundle.request.GET.get('from', '')).translate(None, '/-')
        to_date = str(bundle.request.GET.get('to', '')).translate(None, '/-')
        user = bundle.request.GET.get('user', None)
        first_appearance = bundle.request.GET.get('first_appearance', False)
        snap = bundle.request.GET.get('snap', None)
        results = []
        packages = []
        if user:
            # check to see if the user is in the caching column family first
            binary_packages = cassie.get_binary_packages_for_user(user)
            if binary_packages:
                packages = binary_packages
            else:
                try:
                    subscribed_pkgs = launchpad.get_subscribed_packages(user)
                except HTTPError:
                    raise NotFound('%s was not found.' % user)

                for sub_pkg in subscribed_pkgs:
                    packages.append(sub_pkg)
        # XXX: is returning source package info if package is a binary package
        # the best?
        elif package and launchpad.is_source_package(package):
            for binary in launchpad.get_binaries_in_source_package(package, release):
                packages.append(binary)
            # It is non-trivial to find binaries for PPA packages so just add
            # the source package and hope the binary has the same name
            # LP: #1148015
            if package not in packages:
                packages.append(package)
        elif packageset:
            for package in launchpad.get_packages_in_packageset_name(release, packageset):
                packages.append(package)
        else:
            packages.append(package)

        buckets_combined = []
        minimum = 0

        for package in packages:
            buckets = cassie.get_bucket_counts(release, package,
                                                  version, pkg_arch,
                                                  rootfs_build_version,
                                                  channel_name,
                                                  device_name,
                                                  device_image_version,
                                                  period,
                                                  show_failed=True,
                                                  from_date=from_date,
                                                  to_date=to_date)
            if len(buckets) == 0:
                continue
            # Since fetching the metadata is an expensive operation as it involves
            # seeking the disk and searching other nodes for multiple rows, we
            # filter the set of buckets we're concerned about first.
            buckets = buckets[start:finish]
            # If the buckets_combined across packages are more than our limit
            # find the bucket with the smallest count for that limit and later
            # skip over any buckets with less than than.
            if len(buckets_combined) > finish:
                buckets_combined = sorted(buckets_combined, key=itemgetter(1), reverse=True)
                minimum = buckets_combined[finish][1]
            for bucket, count in buckets:
                if count < minimum:
                    break
                buckets_combined.append((bucket, count))

        buckets_combined = sorted(buckets_combined, key=itemgetter(1), reverse=True)
        # Again filter the set of buckets as fetching metadata is expensive.
        buckets_combined = buckets_combined[start:finish]

        metadata = cassie.get_metadata_for_buckets([x[0] for x in buckets_combined], release)
        rank = 1
        for bucket, count in buckets_combined:
            try:
                m = metadata[bucket]
            except KeyError:
                m = {}
            srcpkg = m.get('Source', '')
            if not srcpkg:
                # Because we weren't always writing the Source field in
                # BucketMetadata, there are going to be a few buckets with an
                # empty value here. Use the old method for looking up the
                # package for now.
                srcpkg, bucket_version = cassie.get_package_for_bucket(bucket)
            if not srcpkg and not snap:
                # if we still don't have a package it is a snap crash or
                # something else
                continue
            if snap == 'True' and srcpkg:
                continue
            last_seen = m.get('LastSeen', '')
            report = m.get('CreatedBug', '') or m.get('LaunchpadBug', '')
            if first_appearance:
                if m.get('FirstSeen', '') != version:
                    continue
            if isinstance(bucket, str):
                bucket = bucket.encode('utf-8')
            hashed = sha1(bucket).hexdigest()
            if cassie.get_problem_for_hash(hashed):
                href = 'problem/%s' % hashed
            else:
                href = 'bucket/?id=%s' % quote(bucket)
            href = '%s%s' % (bundle.request.build_absolute_uri('/'), href)

            results.append(ResultObject({
                'rank': rank,
                'count': count,
                'package': srcpkg.decode('utf-8'),
                'first_seen': m.get('FirstSeen', ''),
                'last_seen': last_seen,
                'first_seen_release': m.get('FirstSeenRelease', ''),
                'last_seen_release': m.get('LastSeenRelease', ''),
                'function': bucket.decode('utf-8'),
                'web_link': href,
                'report': report}))
            rank += 1

        return results

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                return self._handle_request(bundle, start, finish)
        return wrapped()

class CreateBugResource(ErrorsResource):
    signature = fields.CharField(attribute='signature')
    class Meta:
        object_class = ResultObject
        resource_name = 'create-bug-report'
        include_resource_uri = False
        allowed_methods = ['post']
        authentication = SessionAuthentication()
        authorization = DjangoAuthorization()
        # If we do not set this, we get a URL to the created object instead of
        # the object itself.
        always_return_data = True

    def obj_create(self, bundle):
        bundle.obj = ResultObject()
        bundle = self.full_hydrate(bundle)
        bucket = unquote(bundle.obj.signature)
        metadata = cassie.get_metadata_for_bucket(bucket)
        if not metadata:
            return bundle
        if 'LaunchpadBug' in metadata:
            bug = metadata['LaunchpadBug']
            bundle.data['report'], bundle.data['url'] = (bug, 'https://launchpad.net/bugs/' + bug)
        elif 'CreatedBug' in metadata:
            bug = metadata['CreatedBug']
            bundle.data['report'], bundle.data['url'] = (bug, 'https://launchpad.net/bugs/' + bug)
        else:
            src = cassie.get_source_package_for_bucket(bucket)
            lastseen = metadata.get('LastSeen', '')
            releases = set([r[0].replace('Ubuntu ', '') for r in cassie.get_versions_for_bucket(bucket) if r[0].startswith('Ubuntu ')])
            hashed = sha1(bucket).hexdigest()
            if not cassie.get_problem_for_hash(hashed):
                hashed = ''
            report, url = launchpad.create_bug(bucket, src, releases, hashed,
                lastseen)
            if report and url:
                launchpad.subscribe_user(report, bundle.request.user.username)
                cassie.record_bug_for_bucket(bucket, report)
            bundle.data['report'], bundle.data['url'] = (report, url)
        return bundle

    def get_resource_uri(self, bundle_or_obj):
        # We don't support GET, so providing a Location: isn't necessary.
        return ''

class BinaryPackageVersionsResource(ErrorsResource):
    versions = fields.ListField(attribute='versions', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'binary-package-versions'

    def obj_get_list(self, bundle):
        binary_package = bundle.request.GET.get('binary_package', None)
        ubuntu_version = bundle.request.GET.get('release', None)
        if ubuntu_version:
            if ubuntu_version.startswith('Ubuntu '):
                ubuntu_version = ubuntu_version.replace('Ubuntu ', '')
        class wrapped(list):
            def __getslice__(self, start, finish):
                results = launchpad.get_versions_for_binary(binary_package, ubuntu_version)
                return [ResultObject({'versions' : results})]
        return wrapped()

class SystemImageVersionsResource(ErrorsResource):
    versions = fields.ListField(attribute='versions', readonly=True)
    class Meta(ErrorsMeta):
        authentication = SessionAuthentication()
        authorization = DjangoAuthorization()
        resource_name = 'system-image-versions'

    def obj_get_list(self, bundle):
        # image_type can be one of rootfs_build, channel, device_name, or
        # device_image
        image_type = bundle.request.GET.get('image_type', None)
        class wrapped(list):
            def __getslice__(self, start, finish):
                results = cassie.get_system_image_versions(image_type)
                return [ResultObject({'versions' : results})]
        return wrapped()

# TODO make SystemCrashesResource and InstanceResource obj_get only.

class SystemCrashesResource(ErrorsResource):
    # when the report was received
    timestamp = fields.DateTimeField(attribute='timestamp', readonly=True)
    instance = fields.CharField(attribute='instance', readonly=True)
    # when the system recorded the report
    occurred = fields.CharField(attribute='occurred', readonly=True)
    problemtype = fields.CharField(attribute='problemtype', readonly=True)
    program = fields.CharField(attribute='program', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'reports-for-system'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                system_id = bundle.request.GET.get('system', None)
                start = bundle.request.GET.get('start', None)
                cols = ['Date', 'ProblemType', 'Package', 'ExecutablePath']
                crashes = cassie.get_user_crashes(system_id, start=start)
                # TODO: use a cassandra function that does a multiget of the
                # crashes
                for crash, ts in crashes:
                    # cassandra records time in microseconds, convert to
                    # seconds
                    ts = (ts['submitted'][1]) * 1e-6
                    ts = datetime.datetime.utcfromtimestamp(ts)
                    d = cassie.get_crash(str(crash), columns=cols)
                    program = split_package_and_version(d.get('Package', ''))[0]
                    if not program:
                        program = d.get('ExecutablePath', '')
                    yield ResultObject(
                            {'timestamp': ts,
                             'instance': crash,
                             'occurred': d.get('Date', ''),
                             'problemtype': d.get('ProblemType', ''),
                             'program': program,
                            })
        return wrapped()

class RateOfCrashesResource(ErrorsResource):
    increase = fields.BooleanField(attribute='increase', null=True,
        readonly=True)
    difference = fields.IntegerField(attribute='difference', null=True,
        readonly=True)
    web_link = fields.CharField(attribute='web_link', null=True,
        readonly=True)
    previous_period_in_days = fields.IntegerField(
        attribute='previous_period_in_days', null=True, readonly=True)
    previous_average = fields.IntegerField(attribute='previous_average',
        null=True, readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'package-rate-of-crashes'

    def obj_get_list(self, bundle):
        src_package = bundle.request.GET.get('package', None)
        old_version = bundle.request.GET.get('old_version', None)
        new_version = bundle.request.GET.get('new_version', None)
        phased_update_percentage = bundle.request.GET.get('phased_update_percentage', None)
        date = bundle.request.GET.get('date', None)
        release = bundle.request.GET.get('release', None)
        exclude_proposed = bundle.request.GET.get('exclude_proposed', None)
        absolute_uri = bundle.request.build_absolute_uri('/')
        class wrapped(list):
            def __getslice__(self, start, finish):
                result = cassie.get_package_crash_rate(release,
                    src_package, old_version, new_version,
                    phased_update_percentage, date, absolute_uri,
                    exclude_proposed)
                yield ResultObject(result)
        return wrapped()

class PackageVersionNewBuckets(ErrorsResource):
    function = fields.CharField(attribute='function', readonly=True)
    web_link = fields.CharField(attribute='web_link', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'package-version-new-buckets'

    def _handle_request(self, bundle, start, finish):
        src_package = bundle.request.GET.get('package', None)
        previous_version = bundle.request.GET.get('previous_version', None)
        new_version = bundle.request.GET.get('new_version', None)
        if not launchpad.is_valid_source_version(src_package, previous_version):
            raise NotFound('%s version %s was not found in Launchpad.' % (src_package,
                previous_version))
        if not launchpad.is_valid_source_version(src_package, new_version):
            raise NotFound('%s version %s was not found in Launchpad.' % (src_package,
                new_version))
        results = []
        buckets = cassie.get_package_new_buckets(src_package,
                    previous_version, new_version)
        for bucket in buckets:
            if isinstance(bucket, str):
                bucket = bucket.encode('utf-8')
            hashed = sha1(bucket).hexdigest()
            if cassie.get_problem_for_hash(hashed):
                href = 'problem/%s' % hashed
            else:
                href = 'bucket/?id=%s' % quote(bucket)
            href = '%s%s' % (bundle.request.build_absolute_uri('/'), href)
            results.append(ResultObject({
                'function': bucket.decode('utf-8'),
                'web_link': href}))
        return results

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                return self._handle_request(bundle, start, finish)
        return wrapped()

class InstanceResource(ErrorsResource):
    instance = fields.DictField(attribute='instance', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'instance'
        authentication = APIAuthentication()

    def obj_get_list(self, bundle):
        oopsid = bundle.request.GET.get('id', None)
        class wrapped(list):
            def __getslice__(self, start, finish):
                results = cassie.get_crash(oopsid)
                return [ResultObject({'instance' : results})]
        return wrapped()

class AverageCrashesResource(ErrorsResource):
    key = fields.CharField(attribute='key', readonly=True)
    values = fields.ListField(attribute='values', readonly=True)
    color = fields.CharField(attribute='color', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'average-crashes'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                release = bundle.request.GET.get('release', None)
                package = bundle.request.GET.get('package', None)
                version = bundle.request.GET.get('version', None)
                fields = []
                package and fields.append(package)
                version and fields.append(version)
                field = ':'.join(fields)
                if not release:
                    #releases = sorted(release_color_mapping.items())
                    # By default only display non-EoL releases to make the
                    # legend fit better interim fix for LP: #1073560.
                    releases = []
                    for release in release_color_mapping:
                        if release not in ["Ubuntu 12.04", "Ubuntu 12.10",
                                           "Ubuntu 13.04", "Ubuntu 13.10",
                                           "Ubuntu 14.04", "Ubuntu 14.10",
                                           "Ubuntu 15.04", "Ubuntu 15.10",
                                           "Ubuntu 16.04", "Ubuntu 16.10",
                                           "Ubuntu 17.04", "Ubuntu 17.10",
                                           "Ubuntu 18.10",
                                           "Ubuntu 19.04", "Ubuntu 19.10",
                                           "Ubuntu 20.10", "Ubuntu 21.04",
                                           "Ubuntu 21.10", "Ubuntu 22.10",
                                           "Ubuntu 23.04", "Ubuntu 23.10",
                                           ]:
                            releases.append((release,
                                             release_color_mapping[release]))
                else:
                    if release in release_color_mapping:
                        releases = [(release, release_color_mapping[release])]
                    else:
                        releases = [(release, '#000000')]

                for release, color in releases:
                    if field:
                        f = '%s:%s' % (release, field)
                    else:
                        f = release
                    if release != 'Ubuntu 12.04':
                        standards_color = precise_standards_color_mapping[release]
                        problems = cassie.get_average_crashes(f, release, 360)
                        recoverables = cassie.get_average_crashes('RecoverableProblem:' + f, release, 360)

                        # Combine the Crash and RecoverableProblem data.
                        results = {}
                        for item in problems:
                            results[item[0]] = item[1]
                        for item in recoverables:
                            if item[0] in results:
                                results[item[0]] -= item[1]
                        results = sorted(list(results.items()), key=cmp_to_key(lambda x,y: cmp(x[0], y[0])))

                        res = [{'x': result[0] * 1000, 'y': result[1]} for result in results]
                        d = {'key' : '%s (by 12.04 standards)' % release,
                             'values' : res, 'color': standards_color }
                        yield ResultObject(d)

                        res = [{'x': result[0] * 1000, 'y': result[1]} for result in problems]
                        d = {'key' : release, 'values' : res, 'color': color }
                        yield ResultObject(d)
                    else:
                        results = cassie.get_average_crashes(f, release, 360)
                        res = [{'x': result[0] * 1000, 'y': result[1]} for result in results]
                        yield ResultObject({'key' : release, 'values' : res, 'color': color })
        return wrapped()

class AverageInstancesResource(ErrorsResource):
    key = fields.CharField(attribute='key', readonly=True)
    values = fields.ListField(attribute='values', readonly=True)
    color = fields.CharField(attribute='color', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'average-instances'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                bucketid = unquote(bundle.request.GET.get('id', None))
                for release, color in release_color_mapping.items():
                    r = cassie.get_average_instances(bucketid, release, 360)
                    values = [{'x': i[0] * 1000, 'y': i[1]} for i in r]
                    d = {'key': release, 'values': values, 'color': color}
                    yield ResultObject(d)
        return wrapped()

class ReportsStateResource(ErrorsResource):
    # We use POST rather than GET as bug numbers are at present 7 digits long
    # and we request the state for a hundred or so, putting us near the ~2000
    # character accepted limit for a GET.
    reports = fields.DictField(attribute='reports', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'reports-state'
        allowed_methods = ['post']
        authentication = Authentication()
        authorization = Authorization()
        # If we do not set this, we get a URL to the created object instead of
        # the object itself.
        always_return_data = True

    def obj_create(self, bundle):
        bundle.obj = ResultObject()
        bundle = self.full_hydrate(bundle)
        reports = bundle.data['reports']
        release = bundle.data.get('release', None)
        result = {}
        for report in reports:
            report_fixed = launchpad.bug_is_fixed(report, release)
            result[report] = (launchpad.bug_is_fixed(report, release),
                              launchpad.bug_get_master_id(report))
        bundle.obj.reports = result
        return bundle

    def get_resource_uri(self, bundle_or_obj):
        # We don't support GET, so providing a Location: isn't necessary.
        return ''

class PackageVersionIsMostRecent(ErrorsResource):
    packages = fields.DictField(attribute='packages', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'package-version-is-most-recent'
        allowed_methods = ['post']
        authentication = Authentication()
        authorization = Authorization()
        # If we do not set this, we get a URL to the created object instead of
        # the object itself.
        always_return_data = True

    def obj_create(self, bundle):
        bundle.obj = ResultObject()
        bundle = self.full_hydrate(bundle)
        packages = bundle.data['packages']
        release = bundle.data.get('release', None)
        gen = ((result['package'], result['last_seen']) for result in packages)
        most_recent = launchpad.binaries_are_most_recent(gen, release)
        result = {}
        def map_results(p, state):
            result[p['package'] + ' ' + p['last_seen']] = state
        list(map(map_results, packages, most_recent))
        bundle.obj.packages = result
        return bundle

    def get_resource_uri(self, bundle_or_obj):
        # We don't support GET, so providing a Location: isn't necessary.
        return ''

class ReleasePackageVersionPockets(ErrorsResource):
    packages_data = fields.DictField(attribute='packages_data', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'release-package-version-pockets'
        allowed_methods = ['post']
        authentication = Authentication()
        authorization = Authorization()
        # If we do not set this, we get a URL to the created object instead of
        # the object itself.
        always_return_data = True

    def obj_create(self, bundle):
        bundle.obj = ResultObject()
        bundle = self.full_hydrate(bundle)
        packages_data = bundle.data['packages_data']
        gen = ((data['package'], data['seen'], data['release']) for data in packages_data)
        pocket = launchpad.pocket_for_binaries(gen)
        result = {}
        def map_results(p, location):
            result[p['package'] + ' ' + p['seen'] + ' ' + p['release']] = location
        list(map(map_results, packages_data, pocket))
        bundle.obj.packages_data = result
        return bundle

    def get_resource_uri(self, bundle_or_obj):
        # We don't support GET, so providing a Location: isn't necessary.
        return ''

def split_package_and_version(package):
    # Lifted from lp:daisy.
    if not package:
        return ('', '')

    s = package.split()[:2]
    if len(s) == 2:
        package, version = s
    else:
        package, version = (package, '')
    if version == '(not':
        # The version is set to '(not installed)'
        version = ''
    return (package, version)

class InstancesResource(ErrorsResource):
    timestamp = fields.DateTimeField(attribute='timestamp', readonly=True)
    incident = fields.CharField(attribute='incident', readonly=True)
    package_version = fields.CharField(attribute='package_version', readonly=True)
    ubuntu_version = fields.CharField(attribute='ubuntu_version', readonly=True)
    architecture = fields.CharField(attribute='architecture', readonly=True)
    class Meta(ErrorsMeta):
        resource_name = 'instances'

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):
                bucketid = unquote(bundle.request.GET.get('id', None))
                start = bundle.request.GET.get('start', None)
                cols = ['DistroRelease', 'Package', 'Architecture']
                gen = cassie.get_crashes_for_bucket(bucketid, start=start)
                for oops in gen:
                    ts = (oops.time - 0x01b21dd213814000)*100/1e9
                    ts = datetime.datetime.utcfromtimestamp(ts)
                    d = cassie.get_crash(str(oops), columns=cols)
                    ver = split_package_and_version(d.get('Package', ''))[1]
                    yield ResultObject(
                            {'timestamp': ts,
                             'incident': oops,
                             'package_version': ver,
                             'ubuntu_version': d.get('DistroRelease', ''),
                             'architecture': d.get('Architecture', ''),
                            })
        return wrapped()

class VersionsResource(ErrorsResource):
    kwargs = {'readonly': True, 'default': -1}
    version = fields.CharField(attribute='version', **kwargs)
    pockets = fields.DictField(attribute='pockets', readonly=True)
    precise = fields.IntegerField(attribute='precise', **kwargs)
    quantal = fields.IntegerField(attribute='quantal', **kwargs)
    raring = fields.IntegerField(attribute='raring', **kwargs)
    saucy = fields.IntegerField(attribute='saucy', **kwargs)
    trusty = fields.IntegerField(attribute='trusty', **kwargs)
    rtm_1409 = fields.IntegerField(attribute='rtm-14.09', **kwargs)
    utopic = fields.IntegerField(attribute='utopic', **kwargs)
    vivid = fields.IntegerField(attribute='vivid', **kwargs)
    wily = fields.IntegerField(attribute='wily', **kwargs)
    xenial = fields.IntegerField(attribute='xenial', **kwargs)
    yakkety = fields.IntegerField(attribute='yakkety', **kwargs)
    zesty = fields.IntegerField(attribute='zesty', **kwargs)
    artful = fields.IntegerField(attribute='artful', **kwargs)
    bionic = fields.IntegerField(attribute='bionic', **kwargs)
    cosmic = fields.IntegerField(attribute='cosmic', **kwargs)
    disco = fields.IntegerField(attribute='disco', **kwargs)
    eoan = fields.IntegerField(attribute='eoan', **kwargs)
    focal = fields.IntegerField(attribute='focal', **kwargs)
    groovy = fields.IntegerField(attribute='groovy', **kwargs)
    hirsute = fields.IntegerField(attribute='hirsute', **kwargs)
    impish = fields.IntegerField(attribute='impish', **kwargs)
    jammy = fields.IntegerField(attribute='jammy', **kwargs)
    kinetic = fields.IntegerField(attribute='kinetic', **kwargs)
    lunar = fields.IntegerField(attribute='lunar', **kwargs)
    mantic = fields.IntegerField(attribute='mantic', **kwargs)
    noble = fields.IntegerField(attribute='noble', **kwargs)
    oracular = fields.IntegerField(attribute='oracular', **kwargs)
    plucky = fields.IntegerField(attribute='plucky', **kwargs)
    questing = fields.IntegerField(attribute='questing', **kwargs)
    resolute = fields.IntegerField(attribute='resolute', **kwargs)
    derivatives = fields.IntegerField(attribute='derivatives', **kwargs)
    total = fields.IntegerField(attribute='total', **kwargs)
    class Meta(ErrorsMeta):
        resource_name = 'versions'

    def update(self, results, version, release, codename, total, src_pkg=None):
        if not results.get(version):
            results[version] = ResultObject({})
        if not results[version]._data.get(codename):
            results[version]._data[codename] = 0
        if not results[version]._data.get('pockets'):
            results[version]._data['pockets'] = {}
        results[version]._data[codename] += total
        results[version]._data['version'] = version
        # counts for derivatives are lumped together so don't check for the
        # pocket.
        if total != 0 and src_pkg and codename != 'derivatives':
            pocket = launchpad.get_pocket_for_source_version(src_pkg, version, release)
            # The errors bucket page uses rtm_1409 as the key.
            if codename == 'rtm-14.09':
                codename = 'rtm_1409'
            results[version]._data['pockets'][codename] = pocket
        if not results[version]._data.get('total'):
            results[version]._data['total'] = 0
        results[version]._data['total'] += total

    def obj_get_list(self, bundle):
        class wrapped(list):
            def __getslice__(klass, start, finish):

                bucketid = bundle.request.GET.get('id', None)
                vers = cassie.get_versions_for_bucket(bucketid)
                src_pkg = cassie.get_source_package_for_bucket(bucketid)
                total_total = 0
                results = {}
                # store package versions for later sorting
                versions = []
                for ver in vers:
                    release, version = ver
                    total = vers[ver]
                    if release in codenames:
                        codename = codenames[release]
                    else:
                        codename = 'derivatives'
                    versions.append(version)
                    self.update(results, version, release, codename, total, src_pkg)
                    # Produce totals for all Ubuntu releases as the last row.
                    self.update(results, 'All versions', release, codename, total)
                versions.sort(key=cmp_to_key(apt.apt_pkg.version_compare))
                if vers:
                    versions.append('All versions')
                    oresults = OrderedDict()
                    for version in versions:
                        oresults[version] = results[version]
                    return list(oresults.values())
                else:
                    return {}

        return wrapped()


class CrashSignaturesForBug(ErrorsResource):
    signatures = fields.ListField(attribute='signatures', readonly=True)

    class Meta(ErrorsMeta):
        resource_name = 'crash-signatures-for-bug'
    def obj_get_list(self, bundle):
        bug = bundle.request.GET.get('bug', None)
        class wrapped(list):
            def __getslice__(self, start, finish):
                results = cassie.get_signatures_for_bug(bug)
                return [ResultObject({'signatures': results[start:finish]})]
        return wrapped()
