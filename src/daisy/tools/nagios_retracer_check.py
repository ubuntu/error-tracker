#!/usr/bin/python

'''Check whether the number of failed retraces exceeds the number of successful
ones, indicating a problem worth paging about.'''

import sys, json, urllib2
url = 'https://errors.ubuntu.com/api/1.0/retracers-results'
response = urllib2.urlopen(url)
d = json.loads (response.read())
precise = d["objects"][0]["value"]["Ubuntu 12.04"]
quantal = d["objects"][0]["value"]["Ubuntu 12.10"]

exit = 0
if precise.get("failed", -1) > precise.get("success", 0):
    print >>sys.stderr, 'Precise failure count exceeds success count:', precise
    exit = 1
if quantal.get("failed", -1) > quantal.get("success", 0):
    print >>sys.stderr, 'Quantal failure count exceeds success count:', quantal
    exit = 1

sys.exit(exit)
