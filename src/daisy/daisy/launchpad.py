import apt
import httplib2
import json
import sys
import urllib
import urllib2

from lazr.restfulclient._browser import AtomicFileCache
from oauth import oauth
from daisy import config


if (not hasattr(config, 'lp_oauth_token') or
    not hasattr(config, 'lp_oauth_secret') or
    config.lp_oauth_token is None or
    config.lp_oauth_secret is None):
    raise ImportError('You must set lp_oauth_token and '
                      'lp_oauth_secret in local_config')

if config.lp_use_staging == 'True':
    _create_bug_url = 'https://api.qastaging.launchpad.net/devel/bugs'
    _ubuntu_target = 'https://api.qastaging.launchpad.net/devel/ubuntu'
    _oauth_realm = 'https://api.qastaging.launchpad.net'
    _launchpad_base = 'https://api.qastaging.launchpad.net/devel'
else:
    _create_bug_url = 'https://api.launchpad.net/devel/bugs'
    _ubuntu_target = 'https://api.launchpad.net/devel/ubuntu'
    _oauth_realm = 'https://api.launchpad.net'
    _launchpad_base = 'https://api.launchpad.net/devel'

# TODO: replace hardcoding of 'ubuntu' in all these urls e.g. so we can use
# ubuntu-rtm too
_get_published_binaries_url = (_launchpad_base + '/ubuntu/+archive/primary'
    '?ws.op=getPublishedBinaries&binary_name=%s'
    '&exact_match=true&ordered=true&status=Published')
_get_published_binary_version_url = (_launchpad_base + '/ubuntu/+archive/primary'
    '?ws.op=getPublishedBinaries&binary_name=%s&version=%s'
    '&exact_match=true&ordered=true&status=Published')
_get_published_source_version_url = (_launchpad_base + '/ubuntu/+archive/primary'
    '?ws.op=getPublishedSources&source_name=%s&version=%s'
    '&exact_match=true&ordered=true')
_get_bug_tasks_url = _launchpad_base + '/bugs/%s/bug_tasks'
_get_bug_dupof_url = _launchpad_base + '/bugs/%s/duplicate_of_link'

_get_published_binaries_for_release_url = (_launchpad_base +
    '/ubuntu/+archive/primary/?ws.op=getPublishedBinaries&binary_name=%s'
    '&exact_match=true&distro_arch_series=%s')
_get_packageset_url = (_launchpad_base +
    '/package-sets/ubuntu/%s/%s')

_person_url = _launchpad_base + '/~'
_source_target = _launchpad_base + '/ubuntu/+source/'
_distro_arch_series = _launchpad_base + '/ubuntu/%s/i386'

# Bug and package lookup.

_file_cache = AtomicFileCache(config.http_cache_dir)
_http = httplib2.Http(_file_cache)


def json_request_entries(url):
    try:
        return json_request(url)['entries']
    except (KeyError, TypeError, ValueError):
        return ''

def json_request(url):
    try:
        response, content = _http.request(url)
    except httplib2.ServerNotFoundError:
        return ''

    try:
        return json.loads(content)
    except ValueError:
        return ''


def get_all_codenames():
    url = _launchpad_base + '/ubuntu/series'
    return [entry['name'] for entry in json_request_entries(url)]


def get_codename_for_version(version):
    release_codenames = {'12.04': 'precise',
                         '12.10': 'quantal',
                         '13.04': 'raring',
                         '13.10': 'saucy',
                         '14.04': 'trusty',
                         '14.10': 'utopic',
                         '15.04': 'vivid',
                         '15.10': 'wily',
                         '16.04': 'xenial',
                         '16.10': 'yakkety',
                         '17.04': 'zesty',
                         '17.10': 'artful',
                         '18.04': 'bionic',
                         '18.10': 'cosmic',
                         '19.04': 'disco',
                         '19.10': 'eoan',
                         '20.04': 'focal',
                         '20.10': 'groovy',
                         '21.04': 'hirsute',
                         '21.10': 'impish',
                         '22.04': 'jammy',
                         '22.10': 'kinetic',
                         '23.04': 'lunar',
                         '23.10': 'mantic',
                         '24.04': 'noble',
                         '24.10': 'oracular',
                         '25.04': 'plucky',
                     }
    if not version:
        return None
    if version in release_codenames.values():
        return version
    elif version.startswith('Ubuntu '):
        version = version.replace('Ubuntu ', '')
    if version in release_codenames:
        return release_codenames[version]
    elif version == 'Ubuntu RTM 14.09':
        return '14.09'
    else:
        url = _launchpad_base + '/ubuntu/series'
        for entry in json_request_entries(url):
            if 'name' in entry and entry.get('version', None) == version:
                return entry['name']
    return None


def get_devel_series_codename():
    import distro_info
    from datetime import datetime
    di = distro_info.UbuntuDistroInfo()
    today = datetime.today().date()
    try:
        codename = di.devel(today)
    # this can happen on release and before
    # distro-info-data is SRU'ed
    except distro_info.DistroDataOutdated:
        codename = di.stable()
    return codename


def get_version_for_codename(codename):
    url = _launchpad_base + '/ubuntu/series'
    for entry in json_request_entries(url):
        if entry['name'] == codename:
            return entry['version']
    return None


def get_versions_for_binary(binary_package, ubuntu_version):
    if not ubuntu_version:
        codename = get_devel_series_codename()
    else:
        codename = get_codename_for_version(ubuntu_version)
    if not codename:
        return []
    if is_source_package(binary_package):
        package_name = urllib.quote_plus(binary_package)
        ma_url = _launchpad_base + '/ubuntu/' + codename + '/main_archive'
        ma = json_request(ma_url)
        if ma:
            ma_link = ma['self_link']
        else:
            return ''
        series_url = _launchpad_base + '/ubuntu/' + codename
        ps_url = ma_link + ('/?ws.op=getPublishedSources&exact_match=true&status=Published&source_name=%s&distro_series=%s' %
            (package_name, series_url))
        # use the first one, since they are unordered
        try:
            ps = json_request_entries(ps_url)[0]['self_link']
        except IndexError:
            return ''
        pb_url = ps + '/?ws.op=getPublishedBinaries'
        pbs = []
        json_data = urllib2_request_json(pb_url, config.lp_oauth_token,
            config.lp_oauth_secret)
        entries = json.loads(json_data)['entries']
        for entry in entries:
            # use the first binary package since all versions should be the
            # same
            binary_package = entry['binary_package_name']
            break
    # i386 and amd64 versions should be the same, hopefully.
    results = set()
    dist_arch = urllib.quote(_distro_arch_series % codename)
    url = _get_published_binaries_for_release_url % (binary_package, dist_arch)
    results |= set([x['binary_package_version'] for x in json_request_entries(url) if 'binary_package_version' in x])
    return sorted(results, cmp=apt.apt_pkg.version_compare)


def get_release_for_binary(binary_package, version):
    results = set()
    url = _get_published_binary_version_url % \
        (urllib.quote_plus(binary_package), urllib.quote_plus(version))
    results |= set([get_version_for_codename(x['display_name'].split(' ')[3]) for x in json_request_entries(url)])
    return results


def binaries_are_most_recent(specific_packages, release=None):
    '''For each (package, version) tuple supplied, determine if that is the
    most recent version of the binary package.

    This method lets us cache repeated lookups of the most recent version of
    the same binary package.'''

    _cache = {}
    result = []
    for package, version in specific_packages:
        if not package or not version:
            result.append(True)
            continue

        if package in _cache:
            latest_version = _cache[package]
        else:
            latest_version = _get_most_recent_binary_version(package, release)
            # We cache this even if _get_most_recent_binary_version returns
            # None, as packages like Skype will always return None and we
            # shouldn't keep asking.
            _cache[package] = latest_version

        if latest_version:
            r = apt.apt_pkg.version_compare(version, latest_version) != -1
            result.append(r)
        else:
            result.append(True)
    return result


def _get_most_recent_binary_version(package, release):
    url = _get_published_binaries_url % urllib.quote(package)
    if release:
        # TODO cache this by pushing it into the above function and instead
        # passing the distro_arch_series url.
        version = get_codename_for_version(release.split()[1])
        distro_arch_series = _distro_arch_series % version
        url += '&distro_arch_series=' + urllib.quote(distro_arch_series)
    try:
        return json_request_entries(url)[0]['binary_package_version']
    except (KeyError, IndexError):
        return ''


def pocket_for_binaries(specific_packages):
    '''For each (package, version, release) tuple supplied, determine the
    pocket in which the package version appears.

    This method lets us cache repeated lookups of the pocket for the same
    binary package.'''

    _cache = {}
    result = []
    for package, version, release in specific_packages:
        if not package or not version or not release:
            result.append('Not Found')
            continue

        if (package, version, release) in _cache:
            pocket = _cache[package, version, release]
        else:
            pocket = _get_pocket_for_binary_version(package, version, release)
            # We cache this even if _get_pocket_for_binary_version returns
            # None, as packages like Skype will always return None and we
            # shouldn't keep asking.
            _cache[package, version, release] = '%s' % (pocket)
	result.append(pocket)
    return result

def _get_pocket_for_binary_version(package, version, release):
    if release == 'Ubuntu RTM 14.09':
        url = _get_published_binaries_url.replace('/ubuntu/', '/ubuntu-rtm/') % \
            urllib.quote(package)
    else:
        url = _get_published_binaries_url % urllib.quote(package)
    # the package version may be Superseded or Obsolete
    url = url.replace('&status=Published', '')
    url += '&version=' + urllib.quote_plus(version)
    # TODO cache this by pushing it into the above function and instead
    # passing the distro_arch_series url.
    version = get_codename_for_version(release.split()[-1])
    distro_arch_series = _distro_arch_series % version
    url += '&distro_arch_series=' + urllib.quote(distro_arch_series)
    try:
        pocket = json_request_entries(url)[0]['pocket']
        return ('%s' % pocket)
    except (KeyError, IndexError):
        return ''

def binary_is_most_recent(package, version):
    # FIXME we need to factor in the release, otherwise this is often going to
    # look like the issue has disappeared when filtering the most common
    # problems view to a since-passed release.
    latest_version = _get_most_recent_binary_version(package)
    if not latest_version:
        return True
    # If the version we've been provided is older than the latest version,
    # return False; it's not the newest. We will then assume that because
    # we haven't seen it in the new version it may be fixed.
    return apt.apt_pkg.version_compare(version, latest_version) != -1


def bug_is_fixed(bug, release=None):
    url = _get_bug_tasks_url % urllib.quote(bug)
    if release:
        release = release.split()[1]
    codename = get_codename_for_version(release)
    if codename:
        codename_task = ' (ubuntu %s)' % codename
    else:
        codename_task = ''

    try:
        entries = json_request_entries(url)
        if len(entries) == 0:
            # We will presume that this is a private bug.
            return None

        for entry in entries:
            name = entry['bug_target_name']
            if release and codename and name.lower().endswith(codename_task):
                if not entry['is_complete']:
                    return False
                elif entry['is_complete']:
                    return True

        # Lets iterate again and see if we can find the Ubuntu task.
        for entry in entries:
            name = entry['bug_target_name']
            # Do not look at upstream bug tasks.
            if name.endswith(' (Ubuntu)'):
                # We also consider bugs that are Invalid as complete. I am not
                # entirely sure that is correct in this context.
                if not entry['is_complete']:
                    # As the bug itself may be in a library package bug task,
                    # it is not sufficient to return True at the first complete
                    # bug task.
                    return False
        return True
    except (ValueError, KeyError):
        return False


def bug_get_master_id(bug):
    '''Return master bug (of which given bug is a duplicate)

    Return None if bug is not a duplicate.
    '''
    url = _get_bug_dupof_url % urllib.quote(bug)
    try:
        res = json_request(url)
        if res:
            return res.split('/')[-1]
    except (ValueError, KeyError, AttributeError):
        pass
    return None


def is_source_package(package_name):
    dev_series = get_devel_series_codename()
    url = _launchpad_base + '/ubuntu/' + dev_series + \
        ('/?ws.op=getSourcePackage&name=%s' % package_name)
    request = json_request(url)
    if request:
        return True
    else:
        return False


def get_binaries_in_source_package(package_name, release=None):
    # FIXME: in the event that a package does not exist in the devel release
    # an empty set will be returned and binary packages from previous releases
    # will be missed e.g. synaptiks in trusty
    if not release:
        dev_series = get_devel_series_codename()
    else:
        dev_series = get_codename_for_version(release)
    package_name = urllib.quote_plus(package_name)
    ma_url = _launchpad_base + '/ubuntu/' + dev_series + '/main_archive'
    ma = json_request(ma_url)
    if ma:
        ma_link = ma['self_link']
    else:
        return ''
    dev_series_url = _launchpad_base + '/ubuntu/' + dev_series
    ps_url = ma_link + ('/?ws.op=getPublishedSources&exact_match=true&status=Published&source_name=%s&distro_series=%s' %
        (package_name, dev_series_url))
    # just use the first one, since they are unordered
    try:
        ps = json_request_entries(ps_url)[0]['self_link']
    except IndexError:
        return ''
    pb_url = ps + '/?ws.op=getPublishedBinaries'
    pbs = []
    json_data = urllib2_request_json(pb_url, config.lp_oauth_token,
        config.lp_oauth_secret)
    try:
        tsl = json.loads(json_data)['total_size_link']
        total_size = int(urllib2_request_json(tsl, config.lp_oauth_token,
            config.lp_oauth_secret))
        while len(pbs) < total_size:
            entries = json.loads(json_data)['entries']
            for entry in entries:
                pbs.append(entry['binary_package_name'])
            try:
                ncl = json.loads(json_data)['next_collection_link']
            except KeyError:
                break
            json_data = urllib2_request_json(ncl, config.lp_oauth_token,
                config.lp_oauth_secret)
    except KeyError:
        entries = json.loads(json_data)['entries']
        for entry in entries:
            pbs.append(entry['binary_package_name'])
    return set(pbs)

def urllib2_request_json(url, token, secret):
    headers = _generate_headers(token, secret)
    request = urllib2.Request(url, None, headers)
    response = urllib2.urlopen(request)
    content = response.read()
    return content

def get_subscribed_packages(user):
    '''return binary packages to which a user is subscribed'''
    src_pkgs = []
    bin_pkgs = []
    url = _person_url + user + '?ws.op=getBugSubscriberPackages'
    json_data = urllib2_request_json(url, config.lp_oauth_token,
        config.lp_oauth_secret)
    try:
        tsl = json.loads(json_data)['total_size_link']
        total_size = int(urllib2_request_json(tsl, config.lp_oauth_token,
            config.lp_oauth_secret))
        while len(src_pkgs) < total_size:
            entries = json.loads(json_data)['entries']
            for entry in entries:
                src_pkgs.append(entry['name'])
            try:
                ncl = json.loads(json_data)['next_collection_link']
            except KeyError:
                break
            json_data = urllib2_request_json(ncl, config.lp_oauth_token,
                config.lp_oauth_secret)
    except KeyError:
        entries = json.loads(json_data)['entries']
        for entry in entries:
            src_pkgs.append(entry['name'])
    for src_pkg in src_pkgs:
        bin_pkgs.extend(list(get_binaries_in_source_package(src_pkg)))
    return bin_pkgs

def get_packages_in_packageset_name(release, name):
    if not release:
        series = get_devel_series_codename()
    else:
        series = get_codename_for_version(release)
    url = _get_packageset_url % (series, name) + \
        "?ws.op=getSourcesIncluded"
    pkg_set = json_request(url)
    return pkg_set

def is_valid_source_version(src_package, version):
    url = _get_published_source_version_url % \
        (urllib.quote_plus(src_package), urllib.quote_plus(version))
    json_data = json_request(url)
    if 'total_size' not in json_data.keys():
        return False
    if json_data['total_size'] == 0:
        return False
    elif json_data['total_size'] >= 1:
        return True

def get_pocket_for_source_version(src_package, version, release):
    # hack for packages from RTM
    if release == 'Ubuntu RTM 14.09':
        url = _get_published_source_version_url.replace('/ubuntu/', '/ubuntu-rtm/') % \
            (urllib.quote_plus(src_package), urllib.quote_plus(version))
    else:
        url = _get_published_source_version_url % \
            (urllib.quote_plus(src_package), urllib.quote_plus(version))
    series = get_codename_for_version(release.split()[-1])
    distro_arch_series = _distro_arch_series % series
    url += '&distro_arch_series=' + urllib.quote(distro_arch_series)
    try:
        pocket = json_request_entries(url)[0]['pocket']
        return ('%s' % pocket)
    except (KeyError, IndexError):
        return '?'

# Bug creation.


def _generate_operation(title, description, target=_ubuntu_target, tags=['']):
    # tags need to be a list with each tag double quoted because LP checks for
    # invalid characters like single quotes in tags
    tags = str(tags).replace("'", '"')
    operation = { 'ws.op' : 'createBug',
                  'description' : description,
                  'target' : target,
                  'title' : title,
                  'tags' : tags}
    return urllib.urlencode(operation)


def _generate_headers(oauth_token, oauth_secret):
    a = (('OAuth realm="%s", '
          'oauth_consumer_key="testing", '
          'oauth_token="%s", '
          'oauth_signature_method="PLAINTEXT", '
          'oauth_signature="%%26%s", '
          'oauth_timestamp="%d", '
          'oauth_nonce="%s", '
          'oauth_version="1.0"') %
          (_oauth_realm, oauth_token, oauth_secret,
           int(oauth.time.time()), oauth.generate_nonce()))

    headers = {'Authorization': a,
               'Content-Type': 'application/x-www-form-urlencoded'}
    return headers


def create_bug(signature, source='', releases=[], hashed=None, lastseen=''):
    '''Returns a tuple of (bug number, url)'''

    # temporary solution to LP: #1322325 by creating short titles
    if signature.startswith('Traceback (most recent call last'):
        lines = signature.splitlines()
        title = '%s crashed with %s' % (source, lines[-1])
    else:
        title = '%s' % signature
    details = ("details, including versions of packages affected, "
               "stacktrace or traceback, and individual crash reports")

    if not hashed:
        href = 'https://errors.ubuntu.com/bucket/?id=%s' % \
               urllib.quote(signature)
    else:
        href = 'https://errors.ubuntu.com/problem/%s' % hashed

    if source and lastseen:
        description = ("The Ubuntu Error Tracker has been receiving reports "
                       "about a problem regarding %s.  This problem was "
                       "most recently seen with package version %s, the "
                       "problem page at %s contains more %s." %
                       (source, lastseen, href, details))
    else:
        description = ("The Ubuntu Error Tracker has been receiving reports "
                       "about a problem regarding %s.  The problem page at "
                       "%s contains more %s." % (source, href, details))
    description += ("\nIf you do not have access to the Ubuntu Error Tracker "
                   "and are a software developer, you can request it at "
                   "http://forms.canonical.com/reports/.")

    release_codenames = []
    for release in releases:
        # release_codenames need to be strings not unicode
        codename = get_codename_for_version(release)
        if codename:
            release_codenames.append('%s' % str(codename))
        else:
            # can't use capital letters or spaces in a tag e.g. 'RTM 14.09'
            release = release.lower()
            release_codenames.append('%s' % str(release).replace(' ', '-'))
    # print >>sys.stderr, 'code names:', release_codenames
    tags = release_codenames
    if source:
        target = _source_target + source
        operation = _generate_operation(title, description, target, tags)
    else:
        operation = _generate_operation(title, description, tags)
    headers = _generate_headers(config.lp_oauth_token,
                                config.lp_oauth_secret)

    # TODO Record the source packages and Ubuntu releases this crash has been
    # seen in, so we can add tasks for each relevant release.
    request = urllib2.Request(_create_bug_url, operation, headers)
    # print >>sys.stderr, 'operation:', str(operation)
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        print >>sys.stderr, 'Could not create bug:', str(e)
        return (None, None)

    response.read()
    try:
        number = response.headers['Location'].rsplit('/', 1)[1]
        if config.lp_use_staging == 'True':
            return (number, 'https://qastaging.launchpad.net/bugs/' + number)
        else:
            return (number, 'https://bugs.launchpad.net/bugs/' + number)
    except KeyError:
        return (None, None)


def _generate_subscription(user):
    operation = {'ws.op': 'subscribe',
                 'level': 'Discussion',
                 'person': _person_url + user}
    return urllib.urlencode(operation)


def subscribe_user(bug, user):
    operation = _generate_subscription(user)
    headers = _generate_headers(config.lp_oauth_token,
                                config.lp_oauth_secret)
    url = '%s/%s' % (_create_bug_url, bug)
    request = urllib2.Request(url, operation, headers)
    try:
        urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        msg = 'Could not subscribe %s to bug %s:' % (user, bug)
        print >>sys.stderr, msg, str(e), e.read()
