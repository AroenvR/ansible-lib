# Contributing

How to develop, test and release `acme.infra`. Using the collection is covered
in [README.md](README.md); AI coding agents also read [AGENTS.md](AGENTS.md).

## Setup (once)

Your machine needs `git`, `make`, Podman, Python 3.9 or 3.10 (the default
`python3` on RHEL 9 and Ubuntu 22.04) and Python 3.10+ for linting.

```sh
git clone https://git.example.com/platform/acme-infra.git ~/src/ansible_collections/acme/infra
cd ~/src/ansible_collections/acme/infra
make setup images   # on RHEL 9: dnf install python3.12 first; on Ubuntu 22.04: make setup PYTHON_LINT=python3
```

The clone path must end in `ansible_collections/acme/infra`. Ansible then loads
the collection straight from your checkout, so tests never run against a stale
installed copy. `make help` lists all targets.

## How testing works

| Toolchain | Mirrors | Checks |
|---|---|---|
| `lint` | (current ansible-lint) | Style, correctness, documented interfaces |
| `ubuntu2204` | Ubuntu 22.04's `ansible-core` 2.12, Jinja2 3.0.3 | Molecule tests on both OS containers |
| `rhel9` | RHEL 9.6's `ansible-core` 2.14.18, Jinja2 3.1.2 | Molecule tests on both OS containers |
| `native` | Ubuntu 22.04's own `ansible-core` package (2.12.0) | Each role's scenario, after installing the release tarball the way a consumer does |

Lint passing does **not** prove a role works on ansible-core 2.12; the Molecule
toolchains do. Versions are pinned in `dev/requirements-*.txt`. The `native`
test exists because the real OS package can differ from its PyPI twin; Ubuntu's
`ansible-galaxy` crash was found this way. It runs the scenario playbooks
without Molecule, so keep `prepare.yml`, `converge.yml` and `verify.yml` free of
Molecule-only variables.

Test containers (`dev/images/`) mimic default server installs. The RHEL one is
based on UBI, whose repositories hold a subset of RHEL. On a subscribed RHEL
host Podman gives it the full RHEL repositories.

## Workflow (test first)

1. Describe the desired server state in `roles/<role>/molecule/default/verify.yml`.
2. Watch it fail: `make test-ubuntu2204 ROLES=<role>`.
3. Implement in `roles/<role>/` until it passes.
4. Before pushing: `make build` (lint, both toolchains, native test).

For faster iterations keep the containers running:

```sh
cd roles/<role>
export ANSIBLE_COLLECTIONS_PATH=$(git rev-parse --show-toplevel)/.venv/collections
export PATH=$(git rev-parse --show-toplevel)/.venv/ubuntu2204/bin:$PATH
molecule converge   # create the containers once, apply the role
molecule verify     # run the checks
molecule destroy    # clean up when done
```

## Rules for library code

### Compatibility

- Only use `ansible.builtin`. Any other collection becomes a dependency for every
  consumer, including offline ones, so it needs team agreement, an entry in
  `galaxy.yml` and a mention in README.md.
- Look up modules in the oldest supported version, offline:
  `.venv/ubuntu2204/bin/ansible-doc ansible.builtin.<module>`.
- Write conditions that evaluate to a real boolean, and read facts as
  `ansible_facts['os_family']`, not `ansible_os_family`. Newer ansible-core
  versions require this.

### Offline servers and repositories

- Never assume internet access. Every repository, key or download URL is a role
  variable whose default points upstream, so sites can point it at a mirror or proxy.
- Install packages only when they are missing (see `roles/sudoers/tasks/main.yml`).
  The dnf module contacts every enabled repository even when the package is
  already installed, which fails on offline hosts.
- Each role README has a "Server requirements" section saying exactly what the
  server needs and when.

### Role design

| OOP idea | In this collection |
|---|---|
| Package | The collection, versioned and released as one tarball |
| Class | A role, doing one job |
| Constructor parameters | Variables in `defaults/main.yml`, documented and validated in `meta/argument_specs.yml` |
| Public methods | Extra entry points: `tasks/<name>.yml` plus an `argument_specs` entry, called with `include_role` and `tasks_from` |
| Private members (by convention) | Task files without an `argument_specs` entry, and variables prefixed `__<role>_` |
| Composition | Playbooks combine roles. No inheritance and no `meta/main.yml` dependencies. |

- Prefix every public variable with the role name, e.g. `sudoers_rules`.
- Document every public variable in `meta/argument_specs.yml`, with the same
  default as `defaults/main.yml`. `make lint` enforces both.
- Keep the interface small: add a variable only when someone needs it.

## CI

GitHub Actions (`.github/workflows/ci.yml`) and GitLab CI (`.gitlab-ci.yml`) run
the same make targets on every merge request, on the main branch, on version
tags and once a week (catches changes in base images and package repositories;
on GitLab, add the weekly schedule under Build > Pipeline schedules).

| Job | Make target | Needs |
|---|---|---|
| lint | `make lint` | Python 3.10+ |
| test (4 jobs: 2 toolchains x 2 OS containers) | `make test-<toolchain> PLATFORM=<os>` | Podman that can start containers |
| native | `make native-ubuntu2204` | Same |
| release (tags only) | `make check-tag dist` | All jobs above green |

GitHub-hosted runners have Podman, so everything runs there as is. On GitLab
the test jobs start containers inside the job container, which the runner has to
allow. The `runner-check` job reports what the runner offers (OS, user,
privileges, Podman) and the test jobs only start once it passes. If it fails,
its log says what the runner admin needs to change. Until then GitLab cannot
release, on purpose: nothing ships untested.

## Releasing

1. Bump `version` in `galaxy.yml` and add a `CHANGELOG.md` entry. A breaking
   interface change means a new major version.
2. Merge, then tag that commit `vX.Y.Z` and push the tag.
3. CI checks the tag matches `galaxy.yml`, builds the tarball (runtime files
   only, see `build_ignore` in `galaxy.yml`) and publishes it: as a GitHub
   release asset, or in GitLab's package registry with a release linking to it.
