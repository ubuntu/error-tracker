# Project Instructions — Error Tracker

This repository contains two distinct projects that work together:

1. **Error Tracker app (Python)** — The actual application code running https://errors.ubuntu.com. It collects, processes, and displays Ubuntu crash reports.
2. **Juju charm (Python)** — Deploys and manages the Error Tracker app on a machine using systemd.

---

## Workflow Requirements

**Before finishing any task**, always:

1. Run `ruff check --preview .` from the root of the repository to lint the code
2. If the sandboxed environment allows it, run the `pytest` test suite as described in the "Running locally" section.
3. Consider if the test coverage needs updating
4. Update `README.md` if the change adds/removes/renames configuration options, services, or user-facing features
5. Update `.github/copilot-instructions.md` if the change affects structure, conventions, workflow, etc.
6. Provide a **draft commit message** using Conventional Commits format

---

## Repository Layout

```
charm/                # Juju charm source
  charm.py            #   ErrorTrackerCharm — main operator class
  errortracker.py     #   ErrorTracker helper — installs deps, configures systemd services
  tests/              #   Charm tests (spread)

src/                  # Error Tracker application source
  daisy/              #   Crash submission receiver (Flask/gunicorn)
    app.py            #     Application factory
    gunicorn_config.py  #   Gunicorn configuration
    submit.py         #     Crash submission handler
    submit_core.py    #     Core submission logic
    metrics.py        #     Prometheus metrics
  errors/             #   Web frontend (Django)
    views.py          #     Django views
    urls.py           #     URL routing
    settings.py       #     Django settings
    templates/        #     HTML templates
    static/           #     CSS/JS assets
    api/              #     REST API endpoints
  errortracker/       #   Shared library
    cassandra.py      #     Cassandra database access
    cassandra_schema.py #   Schema definitions
    oopses.py         #     OOPS (crash report) handling
    launchpad.py      #     Launchpad API integration
    swift_utils.py    #     OpenStack Swift storage utilities
    amqp_utils.py     #     RabbitMQ/AMQP utilities
    config.py         #     Configuration handling
    utils.py          #     Shared utilities
  Makefile            #   Makefile with targets: run-daisy, run-errors, run-retracer, populate-test-data
  retracer/           #   Symbolic retracer (turns addresses into stack frames)
    config/           #     Per-release retracer configuration
  retracer.py         #   Retracer entry point
  tools/              #   Maintenance and housekeeping scripts
  tests/              #   Application tests

tests/                # Integration and functional tests
  errortracker/       #   Spread-based tests

charmcraft.yaml       # Charm build definition (machine charm, ubuntu@24.04)
pyproject.toml        # Python project config (dependencies, linting)
spread.yaml           # Spread test runner configuration
renovate.json         # Renovate dependency update configuration
```

---

## Error Tracker App (`src/`)

The application is composed of three main services managed via systemd:

| Service    | Description                                                                   |
| ---------- | ----------------------------------------------------------------------------- |
| `daisy`    | Receives crash reports from Ubuntu machines (via `whoopsie`) over HTTP        |
| `errors`   | Django web application — displays crash statistics and details to developers  |
| `retracer` | Processes coredumps to produce symbolic stack traces using `apport-retrace`   |

There are also **timers** (systemd timer units) for periodic housekeeping tasks:

| Timer                         | Schedule              | Purpose                                  |
| ----------------------------- | --------------------- | ---------------------------------------- |
| `et-unique-users-daily-update`| Daily at 00:30        | Updates unique user counts               |
| `et-import-bugs`              | Every 3 hours         | Imports bug data from Launchpad          |
| `et-import-team-packages`     | Daily at 02:30        | Imports team package data from Launchpad |
| `et-swift-corrupt-core-check` | Daily at 04:30        | Checks Swift for corrupt core files      |
| `et-swift-handle-old-cores`   | Every hour at :45     | Archives/removes old core files          |

### Storage dependencies

The application relies on:

- **Cassandra** — primary data store for crash reports and statistics
- **RabbitMQ** — message queue between `daisy` (receiver) and `retracer` (processor)
- **OpenStack Swift** — object storage for coredump files

### Test Architecture

There are multiple layers of testing:

1. **Unit/functional tests** (`src/tests/`) — pytest-based tests that require Cassandra, RabbitMQ, and Swift running locally. These test individual components (submission, retracing, Cassandra operations, OOPS processing).

2. **Integration/spread tests** (`tests/errortracker/`) — run inside LXD VMs via the `spread` test framework. This is how CI runs all tests. There are two spread suites:
   - `tests/errortracker/functional/` — runs pytest inside a VM with all services
   - `tests/errortracker/integration/` — full end-to-end scenario (daisy + retracer + whoopsie)

3. **Charm tests** (`charm/tests/`) — integration tests for the Juju charm deployment using `jubilant`.


### Running locally

See `README.md` for full instructions. The short version:

```bash
# Start dependencies
podman run --name cassandra --network host --rm -d -e HEAP_NEWSIZE=10M -e MAX_HEAP_SIZE=200M docker.io/cassandra
podman run --name rabbitmq --network host --rm -d docker.io/rabbitmq
podman run --name swift --network host --rm -d docker.io/openstackswift/saio

# Run tests
cd src
python3 -m pytest -o log_cli=1 -vv --log-level=INFO tests/
```

### Adding a new Ubuntu series

When a new Ubuntu series is released, multiple places need updating:

1. Add a retracer config directory under `src/retracer/config/` (see existing entries for the format)
2. Search the repo for the previous series codename and version number to find hardcoded references in `daisy` and `errors` that need updating

---

## Charm (`charm/`)

The charm is a **machine charm** targeting `ubuntu@24.04`. It deploys the Error Tracker app directly onto a machine (not a container) and manages services via systemd.

### Charm configuration options

| Option                  | Default | Description                                               |
| ----------------------- | ------- | --------------------------------------------------------- |
| `enable_daisy`          | `true`  | Enable the daisy crash receiver service                   |
| `enable_retracer`       | `true`  | Enable the retracer service                               |
| `enable_timers`         | `true`  | Enable the housekeeping timer units                       |
| `enable_errors`         | `true`  | Enable the errors web frontend service                    |
| `configuration`         | `""`    | Full Python configuration file content for the app        |
| `retracer_failed_queue` | `false` | Whether the retracer listens on the failed retracing queue|

### Charm relations

| Relation     | Interface       | Description                                    |
| ------------ | --------------- | ---------------------------------------------- |
| `route_daisy`| `haproxy-route` | Exposes the daisy service through HAProxy       |

### Charm install flow

1. `install`/`upgrade-charm` event: copies the repo to `~ubuntu/error-tracker`, installs apt dependencies
2. `config-changed` event: writes `local_config.py`, sets up Cassandra schema, configures and restarts systemd units for enabled components

---

## Making Changes — Practical Guidance

### Charm Development

- The charm is built with `charmcraft pack -v`
- Charm dependencies are listed in `pyproject.toml` under `[dependency-groups] charm-deps`
- Binary Python packages for the charm are pinned in `charmcraft.yaml` under `charm-binary-python-packages`
- To update charm deps: run `uv sync --group charm-deps && uv pip freeze` and update the list in `charmcraft.yaml`

### Errors and Workarounds

- **Cassandra OperationTimedOut**: Cassandra can hang unexpectedly. Kill and restart the container.
- **Tests require external services**: Unit tests cannot run without Cassandra, RabbitMQ, and Swift. In constrained environments, rely on linting (`ruff check --preview .`) for validation and push to CI for full test runs.
- **Spread tests run in LXD VMs**: The spread test framework launches LXD virtual machines. This requires LXD and charmcraft snaps and will not work in containerized/sandboxed CI environments without nested virtualization.
- **Charm build requires disk space**: The `build-and-test-charm` CI job frees disk space before building because the charm pack process can be disk-intensive.
- **GDB workaround in integration tests**: The integration test (`tests/errortracker/integration/task.sh`) creates `/usr/lib/debug/.dwz` to work around a GDB bug (LP#1818918) that affects apport retracing.


### Validating Changes

1. **Always lint first**: `ruff check --preview .` — this is fast and catches most issues
2. **Check woke compliance**: Ensure no inclusive language violations (see `.woke.yaml`)
3. **Push to CI**: For test validation, push changes and let the CI spread tests run
4. **Review CI logs**: Use GitHub Actions workflow logs if tests fail — the spread tests provide detailed output including service logs on failure
