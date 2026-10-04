# Contributing

How to develop, test and release `aslib.infra`. Using the collection is covered
in [README.md](README.md); AI coding agents also read [AGENTS.md](AGENTS.md).

## Setup (once)

Your machine needs `git`, `make`, Podman, Python 3.9 or 3.10 (the default
`python3` on RHEL 9 and Ubuntu 22.04) and Python 3.10+ for linting.

```sh
git clone https://github.com/AroenvR/ansible-lib.git ~/src/ansible_collections/aslib/infra
cd ~/src/ansible_collections/aslib/infra
make setup images   # on RHEL 9: dnf install python3.12 first; on Ubuntu 22.04: make setup PYTHON_LINT=python3
```

The clone path must end in `ansible_collections/aslib/infra`. Ansible then loads
the collection straight from your checkout, so tests never run against a stale
installed copy. `make help` lists all targets.

## How the tests are organized

Every role has one Molecule scenario, named after where the role runs.
podman_service and podman_overview are tested through node_deploy's, which
deploys a service with them, next to Claude Code (claude_code's deploy, with
the stand-in for Claude Code in `roles/claude_code/molecule/mock/`) on the same
test server: every service the library provides must run side by side without
taking another's account, UID or files.

| Scenario | For roles that run on | Runs in | Make target |
|---|---|---|---|
| `roles/<role>/molecule/server/` | Servers (`sudoers`, `node_deploy`) | Test server containers that mimic default installs (`dev/images/`) | `make test-servers-<ansible-core>` |
| `roles/<role>/molecule/build_machine/` | The machine Ansible runs on (`node_setup`, `node_image`, `claude_code`'s setup and image) | The machine running the tests | `make test-build-machine-<ansible-core>` |

Each target runs every role that has that scenario (`ROLES=` picks some) with
one ansible-core version: `2.12` (what Ubuntu 22.04 ships) or `2.14` (what
RHEL 9.6 ships), pinned with Molecule in `dev/requirements-ansible-<version>.txt`.
The log has a banner per role (`##### node_image: build_machine tests,
ansible-core 2.12 #####`); task names end with the test case they belong to,
and every check ends with a `PASSED <role>: ...` line saying what it proved.

Two more checks complete the picture:

- `make lint`: current ansible-lint (production profile), a check that every
  role documents its interface, a check that every condition is text (YAML turns
  an unquoted `- x is search('a: b')` into a mapping, which an assert accepts
  without checking anything), and ansible-doc loading every plugin and its
  documentation. Lint runs on a modern ansible-core, so it does **not** prove a
  role works on 2.12; the Molecule tests do.
- `make test-native`: the roles that support Ubuntu 22.04 (`UBUNTU_ROLES` in the
  Makefile), run with Ubuntu's own `ansible-core` (2.12.0) and Podman (3.4)
  packages, after installing the release tarball the way a consumer does. The
  real OS packages can differ from their PyPI twins; Ubuntu's `ansible-galaxy`
  crash was found this way. It runs the scenario playbooks without Molecule, so
  keep `prepare.yml`, `converge.yml` and `verify.yml` free of Molecule-only variables.

Versions to support are test data, not code. `node_image` builds, runs and
queries every app listed in `roles/node_image/molecule/build_machine/vars/apps.yml`
(today NestJS 10, 11, 12 and NestJS's default branch, on Node.js 22 and 24). To
cover another version, add an entry there. Cover each version once rather than
every combination: the list grows by one line per case instead of multiplying.

Test containers (`dev/images/`) mimic default server installs. The RHEL one is
based on UBI, whose repositories hold a subset of RHEL. On a subscribed RHEL
host Podman gives it the full RHEL repositories. A test that needs more than a
default install (`node_deploy` needs Podman) installs it in its `prepare.yml`,
the way an administrator would, and only what a default RHEL install has: what a
role needs beyond it (acl), the role installs when missing.

## Workflow (test first)

1. Describe the desired state in `roles/<role>/molecule/<scenario>/verify.yml`.
2. Watch it fail: `make test-servers-2.12 ROLES=<role>` (or `test-build-machine-2.12`).
3. Implement in `roles/<role>/` until it passes.
4. Before pushing: `make build` (lint, both ansible-core versions, native test).

For faster iterations keep the test containers running:

```sh
cd roles/<role>
export ANSIBLE_COLLECTIONS_PATH=$(git rev-parse --show-toplevel)/.venv/collections
export PATH=$(git rev-parse --show-toplevel)/.venv/ansible-2.12/bin:$PATH
molecule converge -s server   # create the containers once, apply the role
molecule verify -s server     # run the checks
molecule destroy -s server    # clean up when done
```

## Rules for library code

### Compatibility

- Only use `ansible.builtin`. Any other collection becomes a dependency for every
  consumer, including offline ones, so it needs team agreement, an entry in
  `galaxy.yml` and a mention in README.md.
- Look up modules in the oldest supported version, offline:
  `.venv/ansible-2.12/bin/ansible-doc ansible.builtin.<module>`.
- Write conditions that evaluate to a real boolean, and read facts as
  `ansible_facts['os_family']`, not `ansible_os_family`. Newer ansible-core
  versions require this.

### Offline servers and repositories

- Never assume internet access. Every repository, key or download URL is a role
  variable whose default points upstream, so sites can point it at a mirror or proxy.
- Install packages only when they are missing (see `roles/sudoers/tasks/main.yml`).
  The dnf module contacts every enabled repository even when the package is
  already installed, which fails on offline hosts.
- Each role README has a "What a server needs" (or "What the build machine
  needs") section saying exactly what it needs and when.

### Role design

| OOP idea | In this collection |
|---|---|
| Package | The collection, versioned and released as one tarball |
| Class | A role, doing one job |
| Constructor parameters | Variables in `defaults/main.yml`, documented and validated in `meta/argument_specs.yml` |
| Public methods | Extra entry points: `tasks/<name>.yml` plus an `argument_specs` entry, called with `include_role` and `tasks_from` |
| Private members (by convention) | Task files without an `argument_specs` entry, and variables prefixed `__<role>_` |
| Composition | Playbooks combine roles, and a role may build on another with `import_role` (node_deploy on podman_service). No `meta/main.yml` dependencies. |

- Prefix every public variable with the role name, e.g. `sudoers_rules`.
- Document every public variable in `meta/argument_specs.yml`, with the same
  default as `defaults/main.yml`. `make lint` enforces both.
- Keep the interface small: add a variable only when someone needs it.
- Defaults must not read files or run lookups that can fail: role argument
  validation evaluates every default before the first task runs. Read files in tasks.
- When a role is meant for people who don't write Ansible, also ship a playbook in
  `playbooks/`, so it runs as `ansible-playbook aslib.infra.<name>`.
- Name roles by area: `podman_` for any container image, `node_` for what
  Node.js projects add on top.

### Plugins

- Plugins (`plugins/<type>/`) run on the Ansible machine, with the Python of the
  oldest supported ansible-core (3.8 for 2.12): no newer syntax.
- Document them in `DOCUMENTATION`; `make lint` loads it with ansible-doc.
- Callbacks support both result APIs: `result`, `task` and `host` (ansible-core
  2.19 and newer) and `_result`, `_task` and `_host` (older); see
  `plugins/callback/run_log.py`.
- Test them through a role's scenario: run_log is tested in node_setup's.

## CI

GitHub Actions (`.github/workflows/ci.yml`) and GitLab CI (`.gitlab-ci.yml`) run
the same make targets on every push to every branch and once a week (catches
changes in base images and package repositories; on GitLab, add the weekly
schedule under Build > Pipeline schedules). GitHub also runs them for pull requests.

| Job | Make target | Needs |
|---|---|---|
| lint | `make lint` | Python 3.10+ |
| server roles · ansible-core 2.12 / 2.14 | `make images test-servers-<version>` | Podman that can start privileged containers |
| build-machine roles · ansible-core 2.12 / 2.14 | `make test-build-machine-<version>` | Same, plus access to Red Hat's registry, npm and GitHub |
| Ubuntu 22.04's own ansible-core and Podman | `make test-native` | Same |
| branch build (every branch but main) | `make dist BRANCH=<branch>` | All jobs above green |
| release (main) | `make dist-release` | All jobs above green |

GitHub-hosted runners have Podman, so everything runs there as is. On GitLab
the test jobs start containers inside the job container, which the runner has to
allow. The `runner-check` job reports what the runner offers (OS, user,
privileges, Podman) and the test jobs only start once it passes. If it fails,
its log says what the runner admin needs to change. Until then GitLab publishes
nothing, on purpose: nothing ships untested.

## Releases

`build.yml` builds the tarballs, for CI and for you; `make dist` and
`make dist-release` run it. Every push whose pipeline passes publishes one,
never anything untested:

- **Any branch but main: a branch build**, for trying out work in progress:
  `aslib-infra.<branch>.<commit>.<UTC time>.tgz`, e.g.
  `aslib-infra.claude.node_backend_utils.535120ce57bfa574c73e03ea2f06adccd0656298.202610021438.tgz`
  (`/` in the branch name becomes `.`). It is the same tarball as a release,
  with the version from `galaxy.yml` inside. On GitHub it is an artifact of the
  workflow run (Actions > the run > Artifacts), kept 7 days, and a newer build
  of the branch deletes the older one. On GitLab it is the `branch-build` job's
  artifact, kept 7 days.
- **main: a release.** CI gives it the next patch version after the latest
  `vX.Y.Z` tag (`dev/ci/next-version.sh`), creates that tag and publishes
  `aslib-infra-X.Y.Z.tar.gz`: as a GitHub release, or in GitLab's package
  registry with a GitLab release linking to it. To release a new minor or major
  version, raise `version` in `galaxy.yml`: CI uses it when it is higher than
  the next patch version. A breaking interface change means a new major version;
  add a `CHANGELOG.md` entry for anything users notice.

Either tarball holds runtime files only (see `build_ignore` in `galaxy.yml`)
and installs with `ansible-galaxy collection install --force <file>`.

To try your work elsewhere before CI has published it, for example with a
backend project, build it yourself: `ansible-playbook build.yml` (or `make dist`)
writes the same kind of tarball as a branch build into `dist/`.
