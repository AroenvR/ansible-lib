# aslib.infra

Tested building blocks (Ansible roles and ready-made playbooks) for RHEL 9.6 and
Ubuntu 24.04 (or newer) servers: rootless Podman services, building and deploying
Node.js backends as such services, and an always-on Claude Code agent for root.
Developing the collection itself? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Compatibility

| | Supported |
|---|---|
| Ansible control node | The `ansible-core` package of RHEL 9.6 (2.14) or Ubuntu 24.04 (2.16), or newer |
| Managed servers | RHEL 9.6, Ubuntu 24.04. `podman_service`, `podman_overview`, `node_deploy` and `claude_code`: RHEL 9.6 or newer with its Podman (5.4) |
| Image build machines | RHEL 9.6, Ubuntu 24.04, with their Podman (5.4, 4.9) |
| Other collections | None. Only `ansible.builtin` is used. |

## Get it

Each tarball holds only what runs: no tests, no dev tooling.

- **Releases** (`aslib-infra-X.Y.Z.tar.gz`): every change to main that passes
  CI is released with the next version, as a GitHub release (or in GitLab's
  package registry).
- **Branch builds** (`aslib-infra.<branch>.<commit>.<time>.tgz`), to try out
  work in progress: the newest build of each branch is an artifact of its CI
  run (GitHub: Actions > the run > Artifacts) for 7 days.
- **Your own build**, of any checkout of this repository, for example before CI
  has published one. From the repository root, with any ansible-core 2.14 or newer:

  ```sh
  ansible-playbook build.yml   # writes dist/aslib-infra.<branch>.<commit>.<time>.tgz
  ```

  A copy without git (an exported archive) builds too, as `dist/aslib-infra.<time>.tgz`.

  CI uses the same playbook for branch builds and releases; its header explains both.

Install it on the control node, the machine that runs Ansible. `--force`
replaces an installed copy, also one with the same version (branch builds carry
the version of their `galaxy.yml`):

```sh
ansible-galaxy collection install --force aslib-infra-0.5.0.tar.gz   # or the .tgz of a branch build
```

**Offline control node:** copy the tarball over; installing it needs no network.

## Node.js backends: from project to running service

For backend developers; no Ansible knowledge needed. One command prepares a
project, such as a NestJS backend. Run it from the project root:

```sh
ansible-playbook aslib.infra.node_setup
```

It writes an `ansible/` directory to commit with the project, laid out the way
Ansible users expect: `ansible.cfg`, `inventory.yml`, `group_vars/all/` for the
settings, the playbooks, and `templates/service.container.j2`, the Quadlet file.
The project's own files are written once; aslib.infra's are brought up to date by
`update-playbooks.yml`, which keeps a changed one as `<file>.bak`. The container's
environment comes from the project's `.env.production`, its config files from
`config/production/`. Everything after the setup runs from that directory, and
its `README.md` is the guide, from a laptop or from a pipeline. In the order a
project goes through them:

```sh
cd ansible
ansible-playbook prebuild.yml                   # node_modules for development, from a throwaway container
ansible-playbook build-and-deploy.yml           # build the image, then install and start it on the servers
ansible-playbook aslib.infra.overview           # what runs on the servers
ansible-playbook restart.yml                    # restart it, for a change the deploy does not see
ansible-playbook update-playbooks.yml           # after installing a newer aslib.infra
ansible-playbook remove.yml                     # remove it from the servers, keeping its directory
```

`image.yml` and `deploy.yml` run the two halves of `build-and-deploy.yml` on
their own. Every run writes its output to `logs/<playbook>-<UTC time>.log`.

On the servers the deploy follows fixed conventions: an account per service,
image archives in `/opt/containers/images/<service>/`, Quadlet files in
`/etc/containers/systemd/users/<UID>/`, the service's own directory, its working
directory, in `/opt/<service>/`, and the shared zone, `/opt/containers/shared/`,
which every service reads and writes. See [node_deploy](roles/node_deploy/README.md)
and [podman_service](roles/podman_service/README.md), which does the work on the
servers.

## Claude Code: an always-on agent for root

An always-on Claude Code agent on a server, in a rootless container on Red Hat's
UBI 9, which root reaches from a terminal. One command writes the project, a
repository of its own, into an empty directory:

```sh
ansible-playbook aslib.infra.claude_setup
cd ansible
ansible-playbook build-and-deploy.yml           # build the image with the newest Claude Code, deploy it
sudo -i                                         # then, on the server:
claude-code                                     # Claude, in the container; arguments go to claude
```

The project holds the Containerfile, `config/` (the policy and Claude's
instructions, `CLAUDE.md`) and, in `ansible/`, the same kind of playbooks and
guide as a Node.js project. Claude works in its home, `/opt/claude-code/`, and the
shared zone. Every build is also the update to Claude Code's newest version;
`-e claude_code_bypass_permissions=true` deploys it without permission prompts.
See [claude_code](roles/claude_code/README.md).

**For development**, where Claude needs root (aslib.infra's own tests, for one), a
VM of its own on a host with KVM, such as a spare laptop, keeps that root away
from the host and the local network (a proof of concept):

```sh
ansible-playbook aslib.infra.claude_vm --ask-become-pass   # on the host; ends with how to log in
```

See [claude_vm](roles/claude_vm/README.md).

## What runs on a server

Every service runs rootless as an account of its own, so root's `systemctl` and
`podman` do not list it. `aslib.infra.overview` shows root everything
aslib.infra runs: every such service ([podman_overview](roles/podman_overview/README.md)),
with its account, state, image, ports and the command that shows its log, and
the latest log lines of each one that does not run. On a server itself, without
an inventory, it shows that server; from a directory with an inventory, every
server in it:

```sh
ansible-playbook aslib.infra.overview
```

## Use roles in your own playbooks

A project that writes its own playbooks pins aslib.infra in a `requirements.yml`:

```yaml
collections:
  # A release on GitHub. From GitLab's package registry it is:
  # https://<gitlab>/api/v4/projects/<id>/packages/generic/aslib-infra/0.5.0/aslib-infra-0.5.0.tar.gz
  - name: /releases/download/v0.5.0/aslib-infra-0.5.0.tar.gz
    type: url
```

`ansible-galaxy collection install -r requirements.yml` installs it. To use a
tarball file instead, such as a branch build or your own build, or a release
downloaded from a private repository (`gh release download v0.5.0 --repo
REPO_URL`, or `curl --header "PRIVATE-TOKEN: ..."` on GitLab):

```yaml
collections:
  - name: ./aslib-infra-0.5.0.tar.gz
    type: file
```

## What a managed server needs

Every role assumes a default server install. Nothing else is required unless a
role's README says so.

- Python 3, plus `python3-apt` on Ubuntu. Both are part of a default install.
- No internet access. A role that needs package repositories says so in its
  README, and names the step that needs them. Repository and download URLs are
  always role variables, so they can point at your mirror or proxy.

## Roles

| Role | Purpose | Runs on | Needs network access |
|---|---|---|---|
| [sudoers](roles/sudoers/README.md) | sudo rules as validated drop-in files | Servers | Only if sudo is missing |
| [node_setup](roles/node_setup/README.md) | Prepares a Node.js project: its `ansible/` directory with settings, inventory, playbooks and guide | The project's machine | No |
| [node_image](roles/node_image/README.md) | Production container image of a Node.js project, and its node_modules for development, built in containers | The build machine | Yes, from sources you choose |
| [node_deploy](roles/node_deploy/README.md) | Runs that image as a rootless Podman service that starts at boot, with podman_service | Servers (RHEL 9.6+) | No |
| [podman_service](roles/podman_service/README.md) | Runs any image archive as a rootless Podman service that starts at boot | Servers (RHEL 9.6+) | Only if the `acl` package is missing |
| [podman_overview](roles/podman_overview/README.md) | Shows root the rootless Podman services on a server, with how to read their logs | Servers (RHEL 9.6+) | No |
| [claude_code](roles/claude_code/README.md) | Writes a Claude Code project, builds its image, deploys it as an always-on service with podman_service, and the `claude-code` command for root | The project's machine, the build machine, servers (RHEL 9.6+) | To build: Red Hat's registry, Anthropic's repository and GitHub (nvm). To deploy: only if acl is missing |
| [claude_vm](roles/claude_vm/README.md) | A VM for Claude Code with sudo, on a host with KVM, kept away from the local network (proof of concept) | Hosts with KVM (RHEL 9.6+, Ubuntu 24.04+) | Yes: packages, Ubuntu's cloud image, Anthropic's and the deadsnakes repositories |

Every role documents its variables; read them offline with
`ansible-doc -t role aslib.infra.<role>`.

## Ready-made playbooks

For people who don't write Ansible: run these by name, no playbook of your own
needed. The playbooks node_setup writes import them.

| Playbook | Run it from | What it does |
|---|---|---|
| `ansible-playbook aslib.infra.node_setup` | The project's root | Writes `ansible/` into the Node.js project, see [node_setup](roles/node_setup/README.md) |
| `ansible-playbook aslib.infra.node_update` | `ansible/` | Brings aslib.infra's files in `ansible/` up to date, the same as node_setup |
| `ansible-playbook aslib.infra.node_prebuild` | `ansible/` | Prepares the project for development: node_modules from a throwaway container, see [node_image](roles/node_image/README.md#node_modules-for-development) |
| `ansible-playbook aslib.infra.node_image` | `ansible/` | Builds the project into an image archive, see [node_image](roles/node_image/README.md) |
| `ansible-playbook aslib.infra.node_deploy` | `ansible/` | Deploys that image to the servers, or a newer version over the old one, see [node_deploy](roles/node_deploy/README.md) |
| `ansible-playbook aslib.infra.node_restart` | `ansible/` | Restarts the service on the servers and waits until it answers, see [node_deploy](roles/node_deploy/README.md) |
| `ansible-playbook aslib.infra.node_remove` | `ansible/` | Removes the service from the servers, keeping its directory unless asked, see [node_deploy](roles/node_deploy/README.md#remove-a-service) |
| `ansible-playbook aslib.infra.overview` | A server itself, or any directory with an inventory, such as `ansible/` | Shows what aslib.infra runs on that server, or on the inventory's servers, each with the command that shows its log |
| `ansible-playbook aslib.infra.podman_overview` | The same | Shows only the rootless Podman services, see [podman_overview](roles/podman_overview/README.md) |
| `ansible-playbook aslib.infra.claude_setup` | An empty directory, or the root of an earlier setup | Writes a Claude Code project; its `ansible/` holds every other playbook it needs, see [claude_code](roles/claude_code/README.md) |
| `ansible-playbook aslib.infra.claude_vm` | A host with KVM, or a directory with it in an inventory | Creates `claude-dev`, a VM where Claude Code has sudo, away from the local network, see [claude_vm](roles/claude_vm/README.md) |
| `ansible-playbook aslib.infra.claude_vm_remove` | The same | Removes that VM, for a fresh one |

## Plugins

| Plugin | What it does |
|---|---|
| `aslib.infra.run_log` (callback) | Writes each playbook run to a file of its own, `logs/<playbook>-<UTC time>.log`. The `ansible.cfg` that node_setup and claude_setup write enables it: `callbacks_enabled = aslib.infra.run_log`. Options: `ansible-doc -t callback aslib.infra.run_log` |

## Status

Tested on every change, in CI:

- every role with ansible-core 2.14 and 2.16, on test containers that mimic
  default RHEL 9.6 and Ubuntu 24.04 installs, and with the ansible-core 2.16.3
  and Podman 4.9 packages of Ubuntu 24.04 itself;
- node_image with NestJS 10, 11 and 12 and NestJS's default branch;
- a service's deploy, update, overview, removal and redeploy as another
  account, on a RHEL 9.6 test container, next to Claude Code (with a stand-in for
  it) on the same server: separate accounts and UIDs, the shared zone both ways,
  root running Claude Code, its read-only policy, and its removal; podman_service's
  checks after every deploy and restart, and the Node.js service's health check
  getting an app that answers with server errors restarted; a private file in the
  shared zone staying private, a replaced README caught by its checksum and put
  back by the next deploy, and Claude Code's 4 GiB memory limit;
- the Claude Code project's setup, update and real image build, with every
  package up to date.

Not tested yet:

- a deploy over SSH with sudo to another machine: the tests reach their test
  containers through Podman;
- SELinux in enforcing mode: the test containers run without it, and only a RHEL
  server with SELinux enforcing proves the relabelling (`:Z`) of the service's
  directory;
- GitLab CI: `.gitlab-ci.yml` is written but has not run.

Known limits and open work:

- A service with a port must answer HTTP on it: that is how the deploy knows it
  started. One without a port (Claude Code) counts as started once it runs.
- The shared zone lets every service change what any other wrote there; who
  writes what is up to the apps.
- To review for security: how a pipeline gets `container.env` to the deploy (a
  secret variable written to a file, see the guide), and the project's `.npmrc`,
  which the build stage copies in: it stays in the layers of the build stage's
  image (`<name>:build`, the build machine's cache), though not in the image
  that is deployed.

## Versioning

[Semantic Versioning](https://semver.org): a breaking change to any role's
variables means a new major version. See [CHANGELOG.md](CHANGELOG.md).
