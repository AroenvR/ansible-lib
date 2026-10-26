# Contributing

For developers of `aslib.infra`: from an empty machine to a passing test, then
how the repository and its tests are laid out, how to work, the rules for
library code, and how CI and releases work. Using the collection is covered in
[README.md](README.md) and [docs/](docs/README.md); AI coding agents also read
[AGENTS.md](AGENTS.md), which builds on this file.

## Setup

Your machine needs `git`, `make`, Podman, Python 3.11 (for ansible-core 2.14,
as on RHEL 9.6) and Python 3.12 (for 2.16 and linting, as on Ubuntu 24.04).

```sh
git clone <repository> aslib
cd aslib
make setup images   # on RHEL 9.6: dnf install python3.11 python3.12 first; on Ubuntu 24.04: install Python 3.11 too
```

`<repository>` is the URL of aslib.infra's git repository, wherever it is
hosted. Clone it anywhere, under any name (`aslib/` by convention); it only has
to be a git checkout, as Molecule finds `.config/molecule/` via the git root.
Lint and tests always run on your checkout itself, never on a copy of
aslib.infra installed elsewhere: make sees to that. `make setup` creates the
venvs and installs the test-only collections, `make images` builds the test
server containers ([Make targets](#make-targets) says what each target
runs); `make help` lists all targets.

`PYTHON_2.14=`, `PYTHON_2.16=` and `PYTHON_LINT=` point make at another Python
(by default `python3.11`, `python3.12` and `python3.12`). claude_code_vm's VM
already has Python 3.11 (from deadsnakes); adding the deadsnakes PPA a second
time there breaks `apt-get update`.

Then check the setup with a first run: lint, and sudoers' tests on both test
servers. The tests run as root, as in CI, with root's own test images
([Make targets](#make-targets) says why):

```sh
make lint
sudo make images test-servers-2.14 ROLES=sudoers
```

**A machine for development:** claude_code_vm's VM, on a host with KVM, has Podman,
git, make and both Pythons, and runs the tests as CI does; Claude Code may have
root there, away from the host and the local network. See
[A VM for Claude Code, for development](docs/claude-code-vm.md).

## Repository layout

| Path | What it holds |
|---|---|
| `roles/<role>/` | The library. `defaults/` + `meta/argument_specs.yml` are the public interface; `README.md` is the role's reference |
| `roles/<role>/molecule/server/` | Tests of a role that runs on servers, in the test server containers |
| `roles/<role>/molecule/build_machine/` | Tests of a role that runs where Ansible runs (e.g. `node_image`), on the test machine itself |
| `roles/node_deploy/molecule/server/` | Also the tests of `podman_service`, `podman_overview` and claude_code_podman's deploy, side by side with the Node.js service |
| `roles/claude_code_podman/molecule/mock/` | A stand-in for Claude Code with the image's contract, for tests that cannot reach Anthropic's repository |
| `roles/claude_code_vm/molecule/vm/` | Creates the VM on the test machine, which needs KVM; not part of `make test` (`sudo make test-vm-2.16`; CI runs it on GitHub) |
| `roles/gitlab/molecule/gitlab/` | Deploys and uses GitLab on the RHEL 9 test server; not part of `make test` (`make test-gitlab-<ansible-core>`). `mock/` is a stand-in for GitLab's image (`gitlab_test_real: false`) |
| `playbooks/` | Ready-made playbooks for people who don't write Ansible: `ansible-playbook aslib.infra.<name>` |
| `plugins/callback/` | Callback plugins (`run_log`). ansible-lint skips them; `make lint` loads their documentation with ansible-doc |
| `meta/runtime.yml` | The oldest ansible-core the collection supports (2.14) |
| `galaxy.yml` | The collection's name, version and `build_ignore`: what the tarball leaves out. It names no repository, on purpose |
| `README.md`, `docs/` | The users' documentation: the landing page; the guides, the reference and the status. Both ship with the collection |
| `CHANGELOG.md` | Every change users notice, with how to upgrade |
| `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md` | This file; the instructions for AI coding agents; Claude Code's: AGENTS.md plus what applies to Claude Code only. Never shipped |
| `Makefile` | Every developer and CI entry point, see [Make targets](#make-targets). Never shipped |
| `build.yml` | Builds the collection tarball: try-out builds and, with `-e release=true`, releases. Never shipped |
| `dev/` | ansible-core pins per version, test images, the checks `make lint` adds, native test, CI helper scripts. Never shipped |
| `dev/requirements-*.txt`, `dev/collections.yml` | The pinned venvs (`ansible-2.14`, `ansible-2.16`, `lint`) and the test-only collections |
| `dev/images/` | The test containers: `rhel9` and `ubuntu2404`, and `ubuntu2404-native` for the native test |
| `dev/molecule/` | Plays shared by several scenarios: SSH access to the test servers, the preparation of the test server for podman_service |
| `dev/ci/` | CI helper scripts: the next release version, the check that a branch raises the version, the GitLab runner check, pruning older GitHub branch builds |
| `.config/molecule/config.yml` | Molecule settings shared by all roles |
| `.ansible-lint` | ansible-lint's settings: production profile, offline |
| `.github/workflows/ci.yml`, `.gitlab-ci.yml` | CI; both only call make targets |
| `.venv/`, `dist/` | Made by make, git-ignored: the venvs, the test-only collections and the link to the checkout; tarballs |
| `.tools/`, `libs/`, `.env.example` | The maintainer's own tooling (`libs/` is their Bash library, a git subtree). Not linted, never shipped; leave them as they are |

## Make targets

The Makefile holds every entry point. Both CI pipelines only call its targets,
so a local run does exactly what a pipeline does. `make help` lists them:

| Target | What it runs |
|---|---|
| `make setup` | The venvs `.venv/ansible-2.14` and `.venv/ansible-2.16` (ansible-core and Molecule, pinned in `dev/requirements-ansible-<ansible-core>.txt`) and `.venv/lint` (current ansible-lint and ShellCheck, `dev/requirements-lint.txt`), each rebuilt when its pins change; the test-only collections of `dev/collections.yml` in `.venv/collections`; the link `.venv/self/ansible_collections/aslib/infra` |
| `make images` | Builds the test server containers `localhost/aslib-test/ubuntu2404` and `localhost/aslib-test/rhel9` from `dev/images/` |
| `make image-<name>` | Builds one test container, e.g. `make image-rhel9`; `ubuntu2404-native` is the native test's |
| `make lint` | ansible-lint (production profile), `dev/check_role_docs.py`, `dev/check_conditions.py`, `dev/check_shell.py`, and ansible-doc on every plugin ([what each checks](#how-the-tests-are-organized)) |
| `make test-servers-<ansible-core>` | Molecule scenario `server` of every role that has one, e.g. `make test-servers-2.14 ROLES=sudoers` |
| `make test-build-machine-<ansible-core>` | Molecule scenario `build_machine`, on this machine |
| `make test-dist-<ansible-core>` | `dev/test-build.yml`: build.yml in a git checkout and without git |
| `make test` | The three above, with ansible-core 2.14 and 2.16 |
| `make test-native` | `make dist`, the images `ubuntu2404` and `ubuntu2404-native`, then `dev/native-test.sh` with the roles in `UBUNTU_ROLES` |
| `make test-gitlab-<ansible-core>` | Molecule scenario `gitlab`, on the RHEL 9 test server; not part of `make test` |
| `make test-vm-<ansible-core>` | Molecule scenario `vm`, on this machine, which needs KVM; with 2.16 only, as claude_code_vm needs it; not part of `make test` |
| `make build` | `lint`, `test` and `test-native`: what CI runs before a release, except GitLab's test |
| `make dist` | `build.yml`: a tarball to try out, `dist/aslib-infra.<branch>.<commit>.<UTC time>.tgz` |
| `make dist-release` | `build.yml -e release=true`: a release, as CI makes one from main, `dist/aslib-infra-<next version>.tar.gz`. It writes the version into `galaxy.yml` first, so only CI should run it |
| `make version` | Prints the collection's version, from `galaxy.yml` |
| `make version-raised` | Checks that `galaxy.yml`'s version is higher than `accept`'s (`origin/accept`, or `BASE=<ref>`) and that `CHANGELOG.md` has its section |
| `make clean` | Removes the venvs and build output (`.venv/`, `dist/`) |
| `make help` | Lists the targets |

`<ansible-core>` is `2.14` (what RHEL 9.6 ships) or `2.16` (what Ubuntu 24.04
ships). `ROLES=` picks roles (by default every role in `roles/`). `BRANCH=`
names `make dist`'s tarball after a branch; CI passes it, as its checkout may
not be on one.

Root: CI runs every test target as root (`sudo make ...`), with rootful
Podman, which has images of its own, so run `sudo make images` before them.
Run the tests that way too, the server tests above all: CI proves only that
way, and a rootless run has failed where a rootful one passed (the causes found
so far are in [AGENTS.md, Known pitfalls](AGENTS.md#known-pitfalls)).
`make test-vm-<ansible-core>` needs root in any case
(`sudo make test-vm-2.16`). `setup`, `lint`, `dist` and `version` run as
yourself.

## Tests

### How the tests are organized

Every role but podman_service and podman_overview has one Molecule scenario,
named after where the role runs. Those two are tested through node_deploy's,
which deploys a service with them, next to Claude Code (claude_code_podman's deploy,
with the stand-in for Claude Code in `roles/claude_code_podman/molecule/mock/`) on the
same test server: every service the library provides must run side by side
without taking another's account, UID or files.

| Scenario | For roles that run on | Runs in | Make target |
|---|---|---|---|
| `roles/<role>/molecule/server/` | Servers (`sudoers`, `node_deploy`) | Test server containers that mimic default installs (`dev/images/`) | `make test-servers-<ansible-core>` |
| `roles/<role>/molecule/build_machine/` | The machine Ansible runs on (`node_setup`, `node_image`, `claude_code_podman`'s setup and image, `claude_code_settings`, `claude_code_skills`, which also runs the unit tests of its hook program) | The machine running the tests | `make test-build-machine-<ansible-core>` |
| `roles/claude_code_vm/molecule/vm/` | A host with KVM (`claude_code_vm`, its settings file and the real Claude Code in the VM) | The machine running the tests, which needs KVM; not part of `make test`; with 2.16 only. It deletes `/etc/claude-vm/settings.yml` first and removes the VM at the end | `sudo make test-vm-2.16` |
| `roles/gitlab/molecule/gitlab/` | A server running GitLab (`gitlab`) | The RHEL 9 test server; needs Docker Hub, about 4 GB of memory, 15 GB of disk and half an hour, so not part of `make test` (with `gitlab_test_real: false` in its `vars/test.yml`, a stand-in takes minutes, offline) | `make test-gitlab-<ansible-core>` |

Each target runs every role that has that scenario (`ROLES=` picks some) with
one ansible-core version: `2.14` (what RHEL 9.6 ships) or `2.16` (what
Ubuntu 24.04 ships), pinned with Molecule in
`dev/requirements-ansible-<ansible-core>.txt`.
The log has a banner per role (`##### node_image: build_machine tests,
ansible-core 2.14 #####`); task names end with the test case they belong to,
and every check ends with a `PASSED <role>: ...` line saying what it proved.

Three more checks complete the picture:

- `make lint`: current ansible-lint (production profile), a check that every
  role documents its interface, a check that every condition is text (YAML turns
  an unquoted `- x is search('a: b')` into a mapping, which an assert accepts
  without checking anything), ShellCheck on every shell script
  (`dev/check_shell.py`, which renders `*.sh.j2` templates first; the
  maintainer's `.tools/` and `libs/` are left to them), and ansible-doc loading
  every plugin and its documentation. Lint runs on a modern ansible-core, so it
  does **not** prove a role works on 2.14; the Molecule tests do.
- `make test-dist-<ansible-core>`: `build.yml` (`dev/test-build.yml`), on
  copies of the checkout: in a git repository of its own, outside one, inside
  another repository, and without git installed. Each must build a tarball,
  named after the branch, commit and time in a checkout and after the time only
  elsewhere, with a matching checksum.
- `make test-native`: the roles that support Ubuntu (`UBUNTU_ROLES` in the
  Makefile), run with Ubuntu 24.04's own `ansible-core` (2.16.3) and Podman
  (4.9) packages, after installing the release tarball the way a consumer does
  (`ansible-galaxy collection install`). The real OS packages can differ from
  their PyPI twins: Ubuntu 22.04's `ansible-galaxy` crash was found this way.
  It runs the scenario playbooks without Molecule, so keep `prepare.yml`,
  `converge.yml` and `verify.yml` free of Molecule-only variables.

### Writing a test

Test first: write the check, see it fail, then build the role
([Workflow](#workflow)).

- A scenario is a directory `roles/<role>/molecule/<scenario>/` with
  `molecule.yml` (its own settings; the shared ones, such as the test servers,
  are in `.config/molecule/config.yml`), `prepare.yml`, `converge.yml`, which
  runs the role by its collection name (`aslib.infra.<role>`), and
  `verify.yml`. Plays several scenarios share live in `dev/molecule/`.
- Write the failing check first, in `verify.yml`. Name test tasks after what
  they check and end them with the test case they belong to (node_image's end
  with the name of the test app); end each check with a
  `success_msg: PASSED <role> ...` line saying what it proved.
- What a role promises is a list of checks in its `verify` entry point
  (podman_service has the first): its Molecule test runs it, and so does every
  deploy.
- converge.yml runs twice, in Molecule (its idempotence step) and in the native
  test: the second run must change nothing.
- `prepare.yml` gives the test server only what a default install has, the way
  an administrator would ([Test data](#test-data)); what a role needs beyond
  that, the role installs itself when it is missing.
- A server scenario's `prepare.yml` first imports
  `dev/molecule/test-server-ssh.yml`, which lets the test machine in over SSH
  as root and checks Ansible gets there that way. A test that restarts its test
  server resets the connection and waits for it (`meta: reset_connection`,
  `wait_for_connection`): an `until` loop does not retry an unreachable host.
- Keep `prepare.yml`, `converge.yml` and `verify.yml` free of Molecule-only
  variables: the native test runs them with plain `ansible-playbook`.
- A new role that supports Ubuntu goes into `UBUNTU_ROLES` in the Makefile, so
  the native test covers it.

### Test data

Versions to support are test data, not code. `node_image` builds, runs and
queries every app listed in
`roles/node_image/molecule/build_machine/vars/apps.yml`
(today NestJS 10, 11, 12 and NestJS's default branch, on Node.js 22 and 24, and
an app with a native (C) module). To cover another version, add an entry there.
Cover each version once rather than every combination: the list grows by one
line per case instead of multiplying.

Test containers (`dev/images/`) mimic default server installs. The RHEL one is
based on UBI, whose repositories hold a subset of RHEL. On a subscribed RHEL
host Podman gives it the full RHEL repositories. Both run OpenSSH's server, and
the tests reach them over SSH as root, as Ansible reaches a real server
(`.config/molecule/config.yml`): on 127.0.0.1, port 52201 (Ubuntu) and 52202
(RHEL). Root's key goes in with `podman exec`, as a cloud image's would through
cloud-init. What a container needs for SSH logins that a real server does not
(a capability, the mode of `/etc/shadow`) is explained where it is set. A test that needs more than a
default install (`node_deploy` needs Podman) installs it in its `prepare.yml`,
the way an administrator would, and only what a default RHEL install has: what a
role needs beyond it (acl), the role installs when missing.

Stand-ins replace what a machine may not reach: claude_code_podman's build-machine
test builds the real Claude Code image, which needs Red Hat's registry and
Anthropic's repository, unless `claude_code_podman_test_real: false` in its
`vars/project.yml` builds the stand-in in `roles/claude_code_podman/molecule/mock/`
instead; node_deploy's test always deploys that stand-in. gitlab's test uses
GitLab's own image unless `gitlab_test_real: false` in its `vars/test.yml`.

### Faster iterations

Keep the test containers running:

```sh
cd roles/<role>
top=$(git rev-parse --show-toplevel)   # after make setup, which links .venv/self
export ANSIBLE_COLLECTIONS_PATH=$top/.venv/self:$top/.venv/collections
export PATH=$top/.venv/ansible-2.14/bin:$PATH
export PYTHONDONTWRITEBYTECODE=1      # no __pycache__ next to the plugins, as make does
molecule converge -s server   # create the containers once, apply the role
molecule verify -s server     # run the checks
molecule destroy -s server    # clean up when done
```

This runs rootless: when a server scenario fails here, check it as root with the
make target of step 3 of the [Workflow](#workflow) before debugging the role.

## Workflow

Test first:

1. Start a branch of your own from `develop`
   ([Branches and pull requests](#branches-and-pull-requests)).
2. Describe the desired state in `roles/<role>/molecule/<scenario>/verify.yml`.
3. Watch it fail: `sudo make images test-servers-2.14 ROLES=<role>` (or
   `make test-build-machine-2.14 ROLES=<role>`). CI runs the tests as root, with
   rootful Podman, which has images of its own, and proves only that way (see
   [Make targets](#make-targets)).
4. Implement in `roles/<role>/` until it passes.
5. Document it where it belongs ([Documentation](#documentation)), with a
   `CHANGELOG.md` entry for anything users notice, under the coming version.

Before pushing, run what `make build` runs (lint, both ansible-core versions,
native test), with the tests as root as in step 3: `make lint`, then
`sudo make images test test-native`. CI also runs GitLab's test
(`make image-rhel9 test-gitlab-<ansible-core>`), which `make build` leaves out.
Then push; open a pull request into `develop` once the gates in
[Branches and pull requests](#branches-and-pull-requests) pass.

## Rules for library code

### Compatibility

- Roles run on the `ansible-core` the oldest supported systems ship: 2.14.18
  (RHEL 9.6, on Python 3.11) and 2.16.3 (Ubuntu 24.04, on Python 3.12), with
  RHEL 9.6's Podman 5.4 on servers and Ubuntu 24.04's Podman 4.9 on build
  machines. Only the Molecule tests and the native test prove it; lint does not.
- Only use `ansible.builtin`. Any other collection becomes a dependency for every
  consumer, including offline ones, so it needs team agreement, an entry in
  `galaxy.yml` and a mention in README.md and in the compatibility table of
  [docs/install.md](docs/install.md#compatibility).
- Look up modules in the oldest supported version, offline:
  `.venv/ansible-2.14/bin/ansible-doc ansible.builtin.<module>`.
- Write conditions that evaluate to a real boolean, and read facts as
  `ansible_facts['os_family']`, not `ansible_os_family`. Newer ansible-core
  versions require this.
- Development tools may be current, but are pinned: `dev/requirements-*.txt`
  and `dev/collections.yml`.

### Offline servers and repositories

- Never assume internet access. Everything a build or a deploy downloads can
  come from a mirror (a Nexus, say), through each tool's own configuration and
  in its own order, defaulting to what the developer or the machine already
  provides:
  - npm: the project's `.npmrc` and, below it, the build machine's `~/.npmrc`;
  - images: a role variable for the name, and the build machine's
    `registries.conf` for where it comes from;
  - RPMs in image builds: a directory of `.repo` files (`node_image_rpm_repos`,
    `claude_code_podman_rpm_repos`), which replaces the images' own repositories for
    the build instead of adding to them;
  - anything else (a repository, a key, a script): a role variable whose
    default points upstream, checked by fingerprint or checksum.

  aslib.infra adds a setting only where a build cuts a tool off from its own
  configuration, carries files into the build step only and never into an
  image, and merges nothing. The sources are listed in node_image's
  [Download sources](roles/node_image/README.md#download-sources) and in the
  tables of the same name in the project guides (`templates/README.md.j2` of
  node_setup and claude_code_podman).
- Download only what is genuinely needed and enterprise-proven; prefer the OS
  repositories.
- Install packages only when they are missing (see `roles/sudoers/tasks/main.yml`).
  The dnf module contacts every enabled repository even when the package is
  already installed, which fails on offline hosts.
- Each role README says exactly what the machines it runs on need, and when, in
  a section of its own ("What a server needs", "What the build machine needs",
  "Requirements", or claude_code_vm's "The host").

### Role design

The design rests on SOLID and KISS, with some domain-driven and test-driven
design: roles are grouped by domain into families, each role does one job,
roles meet through their documented interfaces, and the checks come first.

| OOP idea | In this collection |
|---|---|
| Package | The collection, versioned and released as one tarball |
| Module | A family of roles of one domain, named `<domain>_<what>`: `podman_`, `node_`, `claude_code_` |
| Index | The family's bare name, where it is a role (`claude_code`): its README maps the family, and it runs nothing itself |
| Class | A role, doing one job |
| Interface | A role's `meta/argument_specs.yml`, and the facts its README says it hands over (`claude_code_settings_policy`) |
| Utility | A role that others include for what they share, and that changes nothing itself (claude_code_settings, claude_code_skills) |
| Constructor parameters | Variables in `defaults/main.yml`, documented and validated in `meta/argument_specs.yml` |
| Public methods | Extra entry points: `tasks/<name>.yml` plus an `argument_specs` entry, called with `include_role` and `tasks_from` |
| Private members (by convention) | Task files without an `argument_specs` entry, and variables prefixed `__<role>_` |
| Composition | Playbooks combine roles, and a role may build on another with `import_role` (node_deploy on podman_service). No `meta/main.yml` dependencies. |

- Prefix every public variable with the role name, e.g. `sudoers_rules`.
- Document every public variable in `meta/argument_specs.yml`, with the same
  default as `defaults/main.yml`. `make lint` enforces both.
- Keep the interface small: add a variable only when someone needs it.
- Keep it simple: clarity and readability come first; no complexity for a 1%
  case.
- Defaults must not read files or run lookups that can fail: role argument
  validation evaluates every default before the first task runs. Read files in tasks.
- When a role is meant for people who don't write Ansible, also ship a playbook in
  `playbooks/`, so it runs as `ansible-playbook aslib.infra.<name>`.
- Name roles by domain, in the domain's own words: `podman_` for any container
  image, `node_` for what Node.js projects add on top, `claude_code_` for
  Claude Code wherever it runs. A role that implements one domain with another
  carries both names, its domain first: claude_code_podman is a Claude Code
  role built on podman_service.
- What two roles share lives in a role of its own that both include
  (claude_code_settings and claude_code_skills for claude_code_podman and
  claude_code_vm). A role
  does not take what another role owns from that role's folder: it includes
  that role and uses what its interface hands over. For now, the setups of
  node_setup and claude_code_podman still share their templates of a project's
  inventory and Quadlet file that way, until a shared setup role exists.
- A role that renames or drops a setting stops a run that still sets the old
  name, naming the new one, rather than ignoring it.
- Containers run with Podman, never Docker. Build every container-based role on
  podman_service, which implements the server conventions (an account per
  service, image archives, Quadlet files, the service's directory, see
  [podman_service](roles/podman_service/README.md#conventions)), as node_deploy,
  claude_code_podman and gitlab do.

### Plugins

- Plugins (`plugins/<type>/`) run on the Ansible machine, with the Python of the
  oldest supported ansible-core (3.9 for 2.14): no newer syntax.
- Document them in `DOCUMENTATION`; `make lint` loads it with ansible-doc.
- Callbacks support both result APIs: `result`, `task` and `host` (ansible-core
  2.19 and newer) and `_result`, `_task` and `_host` (older); see
  `plugins/callback/run_log.py`.
- Test them through a role's scenario: run_log is tested in node_setup's.

### Documentation

Each kind of documentation has one place:

| What | Where |
|---|---|
| What aslib.infra is, who it is for, a quick start, how to install, links onwards | `README.md`, a short landing page |
| A guide per job, in order, from nothing to working; installing; the reference of roles, playbooks and plugins; what the tests cover | `docs/`, indexed in [docs/README.md](docs/README.md) |
| A role: what it does, how, what the machines it runs on need, its options | The role's `README.md`, and `meta/argument_specs.yml` for its options (`ansible-doc -t role aslib.infra.<role>` shows them offline) |
| A project's steps, from its `ansible/` directory | The guides node_setup and claude_code_podman write into a project as `ansible/README.md`, from their `templates/README.md.j2` (claude_code_podman's `templates/project-README.md.j2` becomes the project's `README.md`) |
| Every change users notice, with how to upgrade | `CHANGELOG.md`, under the version it ships in |
| Developing aslib.infra | This file |
| Rules, pitfalls, decisions and status, for AI coding agents | `AGENTS.md`, which links here rather than repeating it |

- README.md and `docs/` ship with the collection, so their links are relative
  and work in an installed copy too. CONTRIBUTING.md and AGENTS.md never ship.
- Each option and mechanism is described once, by the role that owns it
  (podman_service for every service's settings); other READMEs and the guides
  link to that section and name the option only where a reader uses it. A new
  option then changes its own role, not every README.
- Every public variable is in `meta/argument_specs.yml` with the same default
  as `defaults/main.yml`; `make lint` enforces it (`dev/check_role_docs.py`).
- A new role or ready-made playbook also gets its row in
  [docs/reference.md](docs/reference.md).
- The repository has moved between names and hosts and will move again, so the
  documentation names no location: it says `<repository>` for its URL, and
  `<version>` for a release (X.Y.Z) in examples. `galaxy.yml` names none
  either: a checkout's git remote is its source.

## Branches and pull requests

Every change takes the same way to `main`, through two long-lived branches:
`develop` gathers finished changes, and `accept` takes them from it as a new
version, which the maintainer reviews before a release.

1. Start a branch of your own from the current `develop` (not main or accept,
   and not another branch of yours: one branch per pull request), named
   `<kind>/<YYYY-MM-DD>-<at most three words>`, the words joined with
   underscores, the kind such as `feature` or `hotfix`
   (`feature/2026-10-16-gitlab_container`).
2. Push it: CI runs on every push to every branch. A commit with `[skip ci]` in
   its message starts no pipeline, for work in progress you only want to keep
   safe: push such commits to a backup branch of your own, never to the branch
   you open the request from. GitHub's suggested squash message lists every
   commit message of that branch, and a marker in it skips the pipeline of the
   branch it is merged into. On GitLab, `git push -o ci.skip` skips a pipeline
   without a marker. Delete the backup branch once its work is on the request's
   branch.
3. Add the change's entry to `CHANGELOG.md`, under the coming version. If
   `develop` still has `accept`'s version, raise `version` in `galaxy.yml` and
   start that version's section ([Releases](#releases)): CI's `version raised`
   job fails until the branch's version is higher than `accept`'s.
4. Open a pull request (GitHub) or merge request (GitLab) into `develop`. It is
   accepted only with a green CI, at the very least: every CI job green, the
   relevant tests proven to pass, lint clean. Its description stands on its
   own, for any reviewer now or later: what changed and why, compatibility, how
   it was tested, and open points; never a continuation of another discussion.
5. It is squash-merged into `develop`. Delete its branch, on the remote and
   locally, with any backup branch, and start the next one from the updated
   `develop`: `git fetch --prune origin`, then `git branch -D <branch>`.
6. A pull request from `develop` into `accept` brings what `develop` gathered,
   as its version. The maintainer reviews it and merges it with a merge
   commit, not a squash: `develop`'s commits stay the same in `accept`, so
   `develop` goes on from there without conflicts.
7. The maintainer merges `accept` into `main` with a merge commit too, never a
   squash, so `main` stays part of `accept`'s history; CI then releases it
   ([Releases](#releases)).

Work that needs a change still in review waits for its merge, or continues on
that change's branch: a branch started from another unmerged branch is left
behind when that one is squash-merged and deleted.

`main` and `accept` are the maintainer's: nobody else pushes to them. `develop`
changes through pull requests only, and neither it nor `accept` is ever
deleted.

## CI

GitHub Actions (`.github/workflows/ci.yml`) and GitLab CI (`.gitlab-ci.yml`) run
the same make targets on every push to every branch and once a week (catches
changes in base images and package repositories; on GitLab, add the weekly
schedule under Build > Pipeline schedules). GitHub also runs them for pull
requests. main and accept get pipelines of their own later.

| Job | Make target | Needs |
|---|---|---|
| lint | `make lint` | Python 3.10+ |
| version raised (every branch but main and accept; pull requests but those into main) | `make version-raised` | `accept` fetched |
| server roles · ansible-core 2.14 / 2.16 | `make images test-servers-<ansible-core>` | Podman that can start privileged containers |
| build-machine roles · ansible-core 2.14 / 2.16 | `make test-build-machine-<ansible-core>`, `make test-dist-<ansible-core>` | Same, plus access to Red Hat's registry, Anthropic's repository, npm and GitHub |
| Ubuntu 24.04's own ansible-core and Podman | `make test-native` | Same |
| GitLab · ansible-core 2.14 / 2.16 | `make image-rhel9 test-gitlab-<ansible-core>` | As server roles, plus Docker Hub, about 4 GB of memory and 15 GB of disk |
| claude_code_vm · ansible-core 2.16 (GitHub only) | `make test-vm-2.16` | KVM (`/dev/kvm`), which GitHub's Linux runners have; Ubuntu's archive, its cloud image, the deadsnakes and Anthropic's repositories |
| branch build (every branch but main) | `make dist BRANCH=<branch>` | All jobs above green |
| release (main) | `make dist-release` | All jobs above green |

GitHub-hosted runners have Podman, so everything runs there as is; the test
jobs run make with sudo (rootful Podman runs the systemd test containers
reliably there). On GitLab the test jobs start containers inside the job
container, which the runner has to allow. The `runner-check` job reports what
the runner offers (OS, user, privileges, Podman) and the test jobs only start
once it passes. If it fails, its log says what the runner admin needs to
change. Until then GitLab publishes nothing, on purpose: nothing ships untested.
GitLab has no claude_code_vm job: its runner would need KVM too.

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
- **main: a release**, with the version in `galaxy.yml`. Every merge into
  `accept` raises it, so `accept` never carries the number of a release with
  other contents: a patch version for fixes and refactors, a minor one for new
  features, a major one for a breaking interface change (before 1.0.0, a minor
  one). The first change on `develop` after a merge into `accept` raises it and
  starts its section in `CHANGELOG.md`; a later change raises it further when
  it needs to. Each change adds its `CHANGELOG.md` entry there, for anything
  users notice. CI creates the `vX.Y.Z` tag and publishes
  `aslib-infra-<version>.tar.gz`: as a GitHub release, or in GitLab's package
  registry with a GitLab release linking to it. It never reuses a tag: should
  `galaxy.yml` lag behind the latest one, the release is one patch above it
  (`dev/ci/next-version.sh`). A version that reached `accept` but not `main`
  on its own is released as part of the next one.

Either tarball holds runtime files only (see `build_ignore` in `galaxy.yml`)
and installs with `ansible-galaxy collection install --force <file>`.

To try your work elsewhere before CI has published it, for example with a
backend project, build it yourself: `ansible-playbook build.yml` (or `make dist`)
writes the same kind of tarball as a branch build into `dist/`. Outside a git
checkout, such as an exported copy, it is named after the time only:
`aslib-infra.<UTC time>.tgz`.
