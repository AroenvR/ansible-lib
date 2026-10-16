# aslib.infra

An Ansible collection of tested building blocks (roles and ready-made playbooks)
for RHEL 9.6 and Ubuntu 24.04 (or newer) servers: rootless Podman services,
building and deploying Node.js backends as such services, an always-on Claude
Code agent for root, and, as proofs of concept, a VM where Claude Code may have
root, for development, and a GitLab of your own. It uses only `ansible.builtin`, and its tarball holds only
what runs: no tests, no dev tooling.

## Who it is for

- **Backend developers without Ansible knowledge**: one command prepares a
  Node.js project, a few more build and deploy it. See the
  [quick start](#quick-start).
- **Root on a server**: every service runs rootless as an account of its own;
  [what runs on a server](docs/servers.md) shows how to see them all, and
  [Claude Code](docs/claude-code.md) is an agent root reaches from a terminal.
- **Ansible users who write their own playbooks**:
  [use the roles in your own playbooks](docs/own-playbooks.md), with the
  [reference](docs/reference.md) of every role, playbook and plugin.
- **Developers of aslib.infra**: [CONTRIBUTING.md](CONTRIBUTING.md).
- **AI coding agents**: [AGENTS.md](AGENTS.md).

## Quick start

With a release tarball on the machine that runs Ansible (where to get one:
[Get it](docs/install.md#get-it)), from the root of a Node.js project, such as a NestJS
backend:

```sh
ansible-galaxy collection install --force aslib-infra-<version>.tar.gz
ansible-playbook aslib.infra.node_setup         # writes ansible/, to commit with the project
cd ansible
ansible-playbook build-and-deploy.yml           # build the image, then install and start it on the servers
ansible-playbook aslib.infra.overview           # what runs on the servers
```

Before the first deploy, look at `ansible/inventory.yml`, the servers (this
machine by default), `ansible/group_vars/all/project.yml`, the settings, and
`ansible/container.env`, the app's environment. Add `--ask-become-pass` when
sudo asks for a password. What the machines need, and every step: [Deploy a
Node.js backend](docs/nodejs-backend.md#before-you-start).

## Install

Install aslib.infra on the control node, the machine that runs Ansible, from a
tarball: a release (`aslib-infra-<version>.tar.gz`, `<version>` being X.Y.Z, a GitHub
release or in GitLab's package registry), a
branch build or your own build of a checkout. Installing it needs no network,
so an offline control node only needs the file copied over.

```sh
ansible-galaxy collection install --force aslib-infra-<version>.tar.gz   # --force replaces an installed copy
```

It runs with the `ansible-core` package of RHEL 9.6 (2.14) or Ubuntu 24.04
(2.16), or newer, on servers with RHEL 9.6 or Ubuntu 24.04 (services: RHEL 9.6
or newer, with its Podman). Where to get a tarball, the full compatibility
table and versions: [Install aslib.infra](docs/install.md).

## Guides

- [Deploy a Node.js backend](docs/nodejs-backend.md): from project to running
  service.
- [Run Claude Code on a server](docs/claude-code.md): an always-on agent for
  root.
- [A VM for Claude Code, for development](docs/claude-vm.md): where Claude may
  have root, away from the host and the local network (a proof of concept).
- [Run a GitLab of your own](docs/gitlab.md): GitLab CE as a rootless Podman
  service (a proof of concept).
- [What runs on a server](docs/servers.md): see every service, the conventions
  they follow, and what a managed server needs.
- [Use the roles in your own playbooks](docs/own-playbooks.md): pin aslib.infra
  in a project and call its roles.

## Documentation

- [docs/](docs/README.md): every guide and the reference; they ship with the
  collection.
- [Reference](docs/reference.md): roles, ready-made playbooks, plugins and
  where each role's options are. Each role's README is that role's reference.
- [Status](docs/status.md): what the tests cover, what they do not yet, and
  known limits.
- [CHANGELOG.md](CHANGELOG.md): every notable change, and how to upgrade.
- [CONTRIBUTING.md](CONTRIBUTING.md), for developing aslib.infra, and
  [AGENTS.md](AGENTS.md), for AI coding agents, are in the repository only, not
  in the tarball.

Versions follow [Semantic Versioning](https://semver.org): a breaking change to
any role's variables means a new major version (before 1.0.0, a new minor
version).
