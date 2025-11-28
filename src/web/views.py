from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from errors import cassie, version
from daisy.launchpad import bug_get_master_id
from errors.metrics import measure_view
from pycassa.util import OrderedDict
from errors.auth import can_see_stacktraces
from urllib.parse import quote


def common_c():
    return {'code_revno': version.version_info.get('revno')}

@measure_view
def user(request, user_token):
    # oopses indicates whether any crashes have been reported
    c = {'oopses' : cassie.get_user_crashes(user_token, limit=1)}
    c['system_id'] = user_token
    c.update(common_c())
    return render(request, 'user.html', c)

@measure_view
@can_see_stacktraces
def bucket(request, bucketid=None, hashed=None):
    if bucketid:
        bucketid = bucketid.encode('UTF-8')
    if not bucketid:
        bucketid = request.GET.get('id', '').encode('UTF-8')
    if not bucketid:
        return HttpResponseRedirect('/')

    if not cassie.bucket_exists(bucketid):
        return HttpResponseRedirect('/?problem-not-found=' + quote(bucketid))

    traceback = cassie.get_traceback_for_bucket(bucketid)
    metadata = cassie.get_metadata_for_bucket(bucketid)
    failuredata = cassie.get_retrace_failure_for_bucket(bucketid)

    if not traceback:
        (stacktrace, thread_stacktrace) = cassie.get_stacktrace_for_bucket(bucketid)
    else:
        stacktrace = None
        thread_stacktrace = None

    source_package = cassie.get_source_package_for_bucket(bucketid)
    report = metadata.get('CreatedBug', '') or metadata.get('LaunchpadBug', '')

    if source_package == '':
        source_package = 'unknown package'
    if hashed:
        title = 'Problem %s in %s' % (hashed[0:6], source_package)
    else:
        title = 'Problem in %s' % source_package
    c = {'title' : title,
         'bucket' : bucketid.decode('utf-8'),
         'source_package' : source_package,
         'stacktrace' : stacktrace,
         'thread_stacktrace' : thread_stacktrace,
         'traceback' : traceback,
         'report' : report,
         'report_master': bug_get_master_id(report),
         'allow_bug_filing' : settings.ALLOW_BUG_FILING}
    if failuredata:
        c['retrace_failure_reason'] = failuredata.get('Reason', '')
        c['retrace_failure_oops'] = failuredata.get('oops', '')
        c['retrace_failure_missing_ddebs'] = \
            failuredata.get('MissingDebugSymbols', '')
    # hacks for request being empty with django 1.11.11 after passing to render
    c['authenticated'] = request.user.is_authenticated
    c['username'] = request.user.username
    c.update(common_c())
    return render(request, 'bucket.html', c)

@measure_view
@can_see_stacktraces
def oops(request, oopsid):
    c = {'title' : 'Problem instance %s' % oopsid,
         'oops' : cassie.get_crash(oopsid)}
    c.update(common_c())
    return render(request, 'oops.html', c)

@measure_view
def main(request):
    c = {'allow_bug_filing' : settings.ALLOW_BUG_FILING}
    # hacks for request being empty with django 1.11.11 after passing to render
    c['authenticated'] = request.user.is_authenticated
    c['username'] = request.user.username
    c['request_full_path'] = request.get_full_path
    c.update(common_c())
    return render(request, 'main.html', c)

@measure_view
def retracers_average_processing_time(request):
    c = { 'graph_type' : 'average-processing-time' }
    c.update(common_c())
    return render(request, 'retracers.html', c)

@measure_view
def retracers_results(request):
    c = { 'graph_type' : 'results' }
    c.update(common_c())
    return render(request, 'retracers.html', c)

@measure_view
def instances_count(request):
    c = { 'graph_type' : 'instances' }
    c.update(common_c())
    return render(request, 'retracers.html', c)

def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')

def login_failed(request):
    logout(request)
    return HttpResponseRedirect('/?login-failed=true')

def status(request):
    from . import status
    from types import FunctionType
    funcs = [getattr(status, x, None) for x in dir(status)
                if isinstance(getattr(status, x, None), FunctionType)
                    and x.startswith('check_')]
    failed_msg = ''
    for x in funcs:
        if not x():
            if not failed_msg:
                failed_msg = 'HELP ME!\n\nfailing:\n'
            failed_msg = '%s%s\n' % (failed_msg, str(x.__name__))
    if failed_msg:
        return HttpResponse(failed_msg, status=400, content_type='text/plain')
    return HttpResponse('OK')

def bug(request, bug):
    try:
        bug = int(bug)
    except:
        return HttpResponseRedirect('/')

    signatures = cassie.get_signatures_for_bug(bug)
    if signatures:
        return HttpResponseRedirect('/bucket?id=%s' % quote(signatures[0]))
    else:
        return HttpResponseRedirect('/?bug-not-found=true')

def problem(request, hashed):
    if len(hashed) != 0:
        bucketid = cassie.get_problem_for_hash(hashed)
    else:
        bucketid = None
    if not bucketid:
        return HttpResponseRedirect('/?problem-not-found=' + quote(hashed))
    return bucket(request, bucketid, hashed)
