#!/usr/bin/bash

set -e

# start daisy
pushd "$SPREAD_PATH"/src
PYTHONPATH=$(pwd) python3 ./daisy/app.py >/tmp/daisy.log 2>&1 &
daisy_pid=$!
timeout 60 bash -c 'while ! echo "Hello there, still waiting for daisy" >/dev/tcp/localhost/5000; do sleep 5; done'
popd

# start the retracer
python3 "$SPREAD_PATH"/src/retracer.py -a amd64 --sandbox-dir /tmp/sandbox -v --config-dir ./data/config >/tmp/retracer.log 2>&1 &
retracer_pid=$!

sleep 2  # Make sure everything is started

# upload a retraceable crash
cd ./data
# XXX workaround some weirdness of LXD/spread machinery where whoopsie hits a
# "Bad file descriptor" when trying to set its lock
cp ./crash /tmp -r
pushd /tmp/crash
CRASH_DB_URL=http://127.0.0.1:5000 APPORT_REPORT_DIR=$(pwd) CRASH_DB_IDENTIFIER=i_am_a_machine whoopsie --no-polling -f 2>&1 >/tmp/whoopsie.log
popd

# timeout for 10min waiting for a successful retrace
if timeout 600 bash -c "tail -n0 -f /tmp/retracer.log | sed '/Successfully retraced/ q'"; then
    echo "Success"
    ret=0
else
    echo "Failure"
    echo "============== daisy logs =============="
    cat /tmp/daisy.log
    echo "============ retracer logs ============="
    cat /tmp/retracer.log
    echo "============ whoopsie logs ============="
    cat /tmp/whoopsie.log
    ret=1
fi
kill $daisy_pid $retracer_pid
exit $ret
