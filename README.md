# error-tracker

Code behind https://errors.ubuntu.com


## Running the tests locally with spread

This avoids having to install all the Python dependencies and runs everything
isolated in a LXD VM, but is a bit slower for development.
This is also how the CI runs the tests, so if it breaks, that's likely to be the
first step to reproduce locally.
```
sudo snap install lxd --classic
sudo snap install charmcraft --classic
charmcraft.spread -v -reuse -resend
```

## Setting up local development


Start with the Python dependencies
```
# For 'daisy' only
sudo apt install apport-retrace python3-amqp python3-bson python3-cassandra python3-flask python3-mock python3-pygit2 python3-pytest python3-pytest-cov python3-swiftclient ubuntu-dbgsym-keyring
# Add this for 'errors'
sudo apt install python3-django-tastypie python3-numpy
```

Then start a local Cassandra, RabbitMQ and swift (`docker` should work fine too):
```
podman run --name cassandra --network host --rm -d -e HEAP_NEWSIZE=10M -e MAX_HEAP_SIZE=200M docker.io/cassandra
podman run --name rabbitmq --network host --rm -d docker.io/rabbitmq
podman run --name swift --network host --rm -d docker.io/openstackswift/saio
```

> Note:
> * Cassandra can take some time (a minute or two?) to fully start.
> * Also, sometimes, Cassandra can hang and you get some `OperationTimedOut`
>   issues out of nowhere. Just `podman kill cassandra` and restart it.

You can then then run the tests with `pytest`:
```
cd src
python3 -m pytest -o log_cli=1 -vv --log-level=INFO tests/
```

Or start each individual process (from the `./src` folder):

daisy:
```
./run-daisy.sh
```

retracer:
```
./run-retracer.sh
```

errors:
```
./run-errors.sh
```

From there, you can manually upload a crash with the following, from any folder
containing a `.crash` file with its corresponding `.upload` file:
```
CRASH_DB_URL=http://127.0.0.1:5000 APPORT_REPORT_DIR=$(pwd) CRASH_DB_IDENTIFIER=my_custom_machine_id whoopsie --no-polling -f
```
This will create a corresponding `.uploaded` file containing the OOPS ID, that
you need to delete if you want to upload the crash again.

If you don't know where to find crashes, have a look here:
https://code.launchpad.net/~daisy-pluckers/+recipe/apport-test-crashes
A sample is also available in `./tests/errortracker/integration/data/crash/`.

## More documentation

### Opening a new series

Many components of the Error Tracker need to be made aware of the new release.

#### Retracers

The retracers need to have a configuration in `./src/retracer/config`. See
7fdd31c97e6eae524352ddd5dd5a3b3bdf8ddb6a for an example commit.

#### Daisy and Web frontend

There are still many places where the series are hardcoded. While an effort is
ongoing to change that, the best that can be done for now, is to search the repo
for both previous series `codename` (like `questing`) as well as version number
(like `25.10`).

#### Deployment

In addition to changes to this repo, all the deployment machines need to be
updated with the SRU'd `distro-info-data`. This should in principle be automatic
if some sort of unattended upgrades are configured, but better double check as
all is currently under change, and still has a lot of legacy.


#### Refreshing the `CHARMCRAFT_TOKEN`

The `CHARMCRAFT_TOKEN` is what allows the CI to push the charm to charmhub. If it expires, you can refresh it with the following:
```
charmcraft login --export=secrets.auth --charm=error-tracker  --permission=package-manage --permission=package-view --ttl=$((3600*24*365))
cat secrets.auth
```


### Archives and design

Here is some archive documentation for you. New and up-to-date one hasn't
started yet, but the old things are still pretty much accurate, except when it
comes to deployment and infrastructure.

* https://youtu.be/PPQ7k0jRUE4?t=1794
* https://wiki.ubuntu.com/ErrorTracker/
