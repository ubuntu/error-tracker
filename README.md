# error-tracker
Code behind https://errors.ubuntu.com

## Dependencies

```
sudo apt install python3-amqp python3-cassandra apport-retrace ubuntu-dbgsym-keyring
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
