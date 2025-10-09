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

## Running the tests locally for development


Start with the Python dependencies
```
sudo apt install  apport-retrace python3-amqp python3-bson python3-cassandra python3-flask python3-mock python3-pygit2 python3-pytest python3-pytest-cov python3-swiftclient ubuntu-dbgsym-keyring
```

Then by having a local Cassandra and RabbitMQ:
```
docker run --name cassandra --network host --rm -d docker.io/cassandra
docker run --name rabbitmq --network host --rm -d docker.io/rabbitmq
```
And then run the tests with `pytest`:
```
cd src
pytest -o log_cli=1 -vv --log-level=INFO tests/
```

## Documentation

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


### Archives and design

Here is some archive documentation for you. New and up-to-date one hasn't
started yet, but the old things are still pretty much accurate, except when it
comes to deployment and infrastructure.

* https://youtu.be/PPQ7k0jRUE4?t=1794
* https://wiki.ubuntu.com/ErrorTracker/
