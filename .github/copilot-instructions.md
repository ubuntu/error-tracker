# Copilot Coding Agent Instructions for error-tracker

## Project Overview

The Ubuntu Error Tracker is the infrastructure behind https://errors.ubuntu.com. It collects, processes, and visualizes crash reports (OOPS reports) for Ubuntu systems. The codebase is Python (AGPLv3 license) deployed as a Juju charm on Ubuntu 24.04.

### Key Components

| Component | Location | Description |
|-----------|----------|-------------|
| **Daisy** | `src/daisy/` | Flask app that receives crash reports via HTTP (whoopsie) |
| **Retracer** | `src/retracer.py`, `src/retracer/` | Daemon that processes coredumps into symbolic stacktraces |
| **Errors (Web)** | `src/errors/` | Django web application (UI + REST API) |
| **Core library** | `src/errortracker/` | Shared code (Cassandra, AMQP, Swift, config) |
| **Tools** | `src/tools/` | Maintenance and import scripts |
| **Charm** | `charm/` | Juju charm for deployment (`charm.py`, `errortracker.py`) |

### External Services

The error tracker depends on three external services:

- **Apache Cassandra** — primary database for crash data storage
- **RabbitMQ** — message queue for async task processing between components
- **OpenStack Swift** — object storage for binary coredump files

## Project Structure

```
├── src/                          # Main Python source code
│   ├── errortracker/            # Core library (AMQP, Cassandra, config, Swift, utils)
│   ├── daisy/                   # Crash report submission service (Flask)
│   ├── retracer.py              # Retracer daemon entry point
│   ├── retracer/config/         # Per-release retracer configs
│   ├── errors/                  # Django web frontend (UI, API, templates, static)
│   ├── tools/                   # Maintenance/import scripts
│   ├── tests/                   # Unit/functional tests (pytest)
│   ├── run-daisy.sh             # Start daisy service
│   ├── run-retracer.sh          # Start retracer daemon
│   └── run-errors.sh            # Start web frontend (Django)
├── charm/                        # Juju charm
│   ├── charm.py                 # Main charm logic
│   ├── errortracker.py          # Charm configuration handler
│   └── tests/                   # Charm integration tests (jubilant)
├── tests/                        # Top-level spread test suites
│   └── errortracker/
│       ├── functional/          # Spread functional tests (run pytest in LXD VM)
│       └── integration/         # Spread integration tests (end-to-end with whoopsie)
├── pyproject.toml               # Project metadata, dependencies, tool config
├── charmcraft.yaml              # Charm build configuration
├── spread.yaml                  # Spread test framework config (LXD backend)
└── .github/workflows/           # CI/CD pipelines
```

## Linting

The project uses **Ruff** for Python linting and formatting. The configuration is in `pyproject.toml`:

- Line length: 99
- Selected rules: E, F, W, Q, I (with E501 ignored)
- Excluded: `__pycache__`, `*.egg_info`

```bash
# Lint the whole project (same as CI)
ruff check --preview .

# Lint only the charm directory
ruff check --preview charm/
```

Ruff can be installed via snap (`sudo snap install ruff`) or pip.

The project also uses **woke** for inclusive language checks (configured in `.woke.yaml`). The `src/errors/static/js/nvd3/**` directory is excluded from woke scanning.

## Testing

### Test Architecture

There are two layers of testing:

1. **Unit/functional tests** (`src/tests/`) — pytest-based tests that require Cassandra, RabbitMQ, and Swift running locally. These test individual components (submission, retracing, Cassandra operations, OOPS processing).

2. **Integration/spread tests** (`tests/errortracker/`) — run inside LXD VMs via the `spread` test framework. This is how CI runs all tests. There are two spread suites:
   - `tests/errortracker/functional/` — runs pytest inside a VM with all services
   - `tests/errortracker/integration/` — full end-to-end scenario (daisy + retracer + whoopsie)

3. **Charm tests** (`charm/tests/`) — integration tests for the Juju charm deployment using `jubilant`.

### Running Tests

**Important:** The unit tests in `src/tests/` require Cassandra, RabbitMQ, and Swift to be running. You cannot run them without these services. In the sandboxed coding agent environment, you will not be able to run these tests directly.

#### Running tests locally (requires services)

```bash
# Start required services first (see "Local Development Setup" below)
cd src
python3 -m pytest -o log_cli=1 -vv --log-level=INFO tests/
```

#### Running tests via spread (recommended, matches CI)

```bash
sudo snap install lxd --classic
sudo snap install charmcraft --classic
# Run all error tracker tests
charmcraft.spread -v -reuse -resend
# Run only error tracker tests
charmcraft.spread -v tests/errortracker/
# Run only charm tests
charmcraft.spread -v charm/tests/
```

#### pytest Configuration

From `pyproject.toml`, the Python path for pytest is `["./src", "./local_config"]`. Tests are in `src/tests/` and use fixtures from `src/tests/conftest.py` which set up temporary Cassandra keyspaces and mock retracers.

### CI Pipelines

The repository has four GitHub Actions workflows:

| Workflow | File | Triggers | What it does |
|----------|------|----------|-------------|
| CI | `ci.yaml` | push/PR to main | Ruff lint, spread tests (LXD), woke checks |
| Build and test charm | `build-and-test-charm.yaml` | push/PR to main | Ruff lint (charm/), lib check, charm pack + test, upload to Charmhub (main only) |
| Release | `release.yaml` | manual dispatch | Promote charm between Charmhub channels |
| Zizmor | `zizmor.yaml` | push/PR | Security scanning of GitHub Actions workflows |

## Local Development Setup

**Note for coding agents:** The full local development setup requires Docker/Podman and system-level packages that may not be available in a sandboxed environment. Focus on code changes and linting; rely on CI for test validation.

### Dependencies

```bash
# Core Python dependencies (system packages)
sudo apt install apport-retrace python3-amqp python3-bson python3-cassandra \
  python3-flask python3-mock python3-pygit2 python3-pytest python3-pytest-cov \
  python3-swiftclient ubuntu-dbgsym-keyring
# Additional for web frontend
sudo apt install python3-django-tastypie python3-numpy
```

### Starting Services

```bash
podman run --name cassandra --network host --rm -d -e HEAP_NEWSIZE=10M -e MAX_HEAP_SIZE=200M docker.io/cassandra
podman run --name rabbitmq --network host --rm -d docker.io/rabbitmq
podman run --name swift --network host --rm -d docker.io/openstackswift/saio
```

Cassandra can take 1–2 minutes to fully start and may occasionally hang with `OperationTimedOut` errors. Restart it if that happens.

## Making Changes — Practical Guidance

### Code Style

- Follow existing code conventions; the codebase does not use type hints extensively
- Ruff enforces import ordering (isort-compatible via the `I` rule)
- Line length limit is 99 characters (E501 is ignored, so long lines won't fail lint)
- License header (AGPLv3) appears in some files but is not universally applied

### Adding a New Ubuntu Series

Many parts of the codebase have hardcoded Ubuntu series names and version numbers. When adding a new series:

1. Add a retracer config in `src/retracer/config/`
2. Search the entire repo for both the previous series codename (e.g., `questing`) and version number (e.g., `25.10`) and update all references

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
