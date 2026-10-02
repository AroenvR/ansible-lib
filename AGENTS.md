# AGENTS.md

Instructions for AI coding agents working on this repository. Humans: see
[README.md](README.md) (using the collection) and [CONTRIBUTING.md](CONTRIBUTING.md)
(developing it). This file only adds what an agent needs on top of those.

## What this is

`acme.infra` is an Ansible collection: a library of small, tested roles for
RHEL 9 and Ubuntu 22.04 servers. Consumers install a release tarball that holds
only runtime files; tests and tooling never ship (`build_ignore` in `galaxy.yml`).

## Non-negotiable constraints

- **Runtime compatibility.** Roles must run on the `ansible-core` that the OS
  ships: 2.12.0 (Ubuntu 22.04, apt) and 2.14.18 (RHEL 9.6, AppStream). Read module
  docs for the oldest version offline: `.venv/ubuntu2204/bin/ansible-doc ansible.builtin.<module>`.
- **Only `ansible.builtin`.** Any other collection is a dependency for every
  consumer; ask the maintainer first.
- **Offline servers.** Never assume internet access. Every repository, key or
  download URL is a role variable with an upstream default. Install packages only
  when missing (the dnf module contacts every enabled repository even for
  installed packages). Each role README states exactly what the server needs.
- **Podman, never Docker.**
- **Dependencies.** Development tools may be current but are pinned in
  `dev/requirements-*.txt`. Anything downloaded must be genuinely needed and
  enterprise-proven; prefer the OS repositories.
- **KISS over edge cases.** Clarity and readability come first; do not add
  complexity for a 1% case. SOLID applies at role level (see CONTRIBUTING.md).
- **Documentation and linting are mandatory.** Every public role variable is
  documented in `meta/argument_specs.yml` with the same default as
  `defaults/main.yml`; `make lint` enforces it.

## Commands

The repository must sit at `<dir>/ansible_collections/acme/infra` (the Makefile
refuses otherwise) and be a git checkout (Molecule finds `.config/molecule/` via
the git root).

```sh
make setup images            # once: venvs, test-only collections, test containers
make lint                    # ansible-lint (production profile) + interface check
make test-ubuntu2204 ROLES=<role> PLATFORM=ubuntu2204   # fastest TDD loop (server roles)
make test-local-ubuntu2204 ROLES=<role>                 # roles that run on the build machine
make build                   # everything CI runs: lint, both toolchains, native test
make dist                    # release tarball in dist/
```

Write the failing test first (`roles/<role>/molecule/default/verify.yml`), then
the role. Keep scenario playbooks free of Molecule-only variables: the native
test runs them with plain `ansible-playbook`.

## Repository map

| Path | Purpose |
|---|---|
| `roles/<role>/` | The library. `defaults/` + `meta/argument_specs.yml` are the public interface |
| `roles/<role>/molecule/default/` | Tests of a server role, run in the OS test containers |
| `roles/<role>/molecule/local/` | Tests of a build-machine role (e.g. `node_image`), run on the test machine itself |
| `playbooks/` | Ready-made playbooks for people who don't write Ansible: `ansible-playbook acme.infra.<name>` |
| `dev/` | Toolchain pins, test images, native test, CI helper scripts. Never shipped |
| `.config/molecule/config.yml` | Molecule settings shared by all roles |
| `.github/workflows/ci.yml`, `.gitlab-ci.yml` | CI; both only call make targets |

## Working with the maintainer

The maintainer and the agent work in **separate environments**. The
maintainer's repositories (GitHub `AroenvR/ansible-lib`, later GitLab) are the
source of truth.

- **Never lose the maintainer's edits.** Before changing a file, use the latest
  version the maintainer provided. Files they have edited so far:
  `.gitignore` and the `on:` block of `.github/workflows/ci.yml` (including its
  TODO comments). Only change their lines when they ask; suggest changes in chat instead.
  They also keep private directories that are not in the zip and restore them
  after overwriting; ignore them unless told otherwise.
- **Deliver every change as a complete zip** of the repository root (the zip
  root is the repository root), excluding `.git/`, `.venv/`, `dist/` and tool
  caches. The maintainer overwrites their checkout with it, so every file in the
  zip replaces theirs. With each zip, list the changed files and any files to
  delete (overwriting never deletes).
- **Verify from a clean state** before delivering: fresh venvs, empty pip and
  Molecule caches, a git checkout. A cached pip wheel once hid a CI failure.
- **Communication.** Be concise and end replies with a `TL;DR:` section. The
  maintainer may use speech-to-text: interpret intent, not literal typos.
  Research version-sensitive facts in credible, current sources instead of
  relying on memory, and cite them.

## Known pitfalls (all verified)

- Ubuntu 22.04's own `ansible-galaxy collection install` crashes (Ubuntu ships
  resolvelib 0.8.1, ansible-core 2.12 needs < 0.6). Consumers there extract the
  tarball instead; README.md documents it.
- Molecule 6.0.3 searches `~/.ansible/collections` before `ANSIBLE_COLLECTIONS_PATH`,
  so a stale installed copy can shadow the code under test. Hence the
  `ansible_collections/acme/infra` layout, `prerun: false` and `offline: true` in `.ansible-lint`.
- Python 3.9/3.10's bundled pip installs ansible-core 2.12 (source only on PyPI)
  with broken `#!python` launchers; venvs are created with `--upgrade-deps`.
- Lint runs on a modern ansible-core, so lint passing does not prove 2.12
  compatibility. Only the Molecule toolchains and the native test do.
- ansible-lint cannot parse GitLab's `!reference` tag; use YAML anchors.
- `meta-runtime[unsupported-version]` is skipped on purpose (2.12 is supported).
- Role argument validation evaluates every default before the first task, so a
  default with a failing lookup (e.g. reading package.json) breaks the role with
  an unreadable error. Read files in tasks instead.
- The agent's sandbox cannot reach Red Hat's registry, nodejs.org or GitHub
  tarballs. `node_image` was verified there with stand-in images and locally
  served samples; only CI exercises real UBI and GitHub.
- A role called from a loop shares the caller's `item`. Loops inside roles use
  their own `loop_var` (`__<role>_<name>`), and so do loops calling a role.
- NestJS's default branch is `master`, not `main`. Its samples have no lockfile
  and conflicting peer dependencies; NestJS installs them with
  `--legacy-peer-deps`, so the tests write that into the sample's `.npmrc`.
- Podman inside Podman (the native test) needs its own subnet: both default to
  10.88.0.0/16, which makes the inner containers unreachable. The native image
  changes the inner one.

## Status

Last updated 2026-10-02.

- GitHub Actions: all jobs green (run #8). `node_image`, its `test-local` jobs
  and the NestJS test matrix are new and have not run in CI yet.
- GitLab CI: not run yet. The `runner-check` job will report whether the runner
  can start containers.
- Node.js backends, decided with the maintainer:
  - Images are built on RHEL 9 or Ubuntu 22.04 build machines (Podman 3.4+) and
    delivered as archive files (`podman save`). The image itself is always RHEL
    (UBI); which RHEL major is still open (UBI 9 for now).
  - Projects follow the NestJS convention: `package.json` with `build` and
    `start:prod`. `.nvmrc` is optional (default: current LTS, 24);
    `package-lock.json` is optional (`npm ci` with it, `npm install` without).
  - Supported versions are test data, not code: one case per version in
    `roles/node_image/molecule/local/vars/apps.yml` (NestJS 10, 11, 12 pinned,
    plus `master`). Cover each version once; no cartesian products.
  - Images run on RHEL 9 hosts only, rootless, through Quadlet, on ports
    3000-3999. Environment variables (an untracked env file) and a data mount are
    runtime settings, never baked into the image. Next: a role that runs such an
    image as a rootless Quadlet service.
- Open: the maintainer's TODOs in `ci.yml` (`on:` filters cannot use expressions;
  schedules always run on the default branch); placeholders (`acme` namespace,
  `LICENSE`, URLs in `galaxy.yml`, CONTRIBUTING.md, README.md).

Update this section whenever the status changes.
