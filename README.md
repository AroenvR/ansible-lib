# acme.infra

Tested building blocks (Ansible roles and ready-made playbooks) for RHEL 9 and
Ubuntu 22.04 servers, and for building and deploying Node.js backends.
Developing the collection itself? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Compatibility

| | Supported |
|---|---|
| Ansible controller | The `ansible-core` package of Ubuntu 22.04 (2.12) or RHEL 9.6 (2.14), or newer |
| Managed servers | Ubuntu 22.04, RHEL 9. `node_deploy`: RHEL 9.2 or newer with Podman |
| Image build machines | Ubuntu 22.04, RHEL 9, with Podman 3.4 or newer |
| Other collections | None. Only `ansible.builtin` is used. |

## Get it

Each tarball holds only what runs: no tests, no dev tooling.

- **Releases** (`acme-infra-X.Y.Z.tar.gz`): every change to main that passes
  CI is released with the next version, as a GitHub release (or in GitLab's
  package registry).
- **Branch builds** (`acme-infra.<branch>.<commit>.<time>.tgz`), to try out
  work in progress: the newest build of each branch is an artifact of its CI
  run (GitHub: Actions > the run > Artifacts) for 7 days.
- **Your own build**, of any checkout of this repository, for example before CI
  has published one. From the repository root, with any ansible-core 2.12 or newer:

  ```sh
  ansible-playbook build.yml   # writes dist/acme-infra.<branch>.<commit>.<time>.tgz
  ```

  CI uses the same playbook for branch builds and releases; its header explains both.

Install it on the machine that runs Ansible. `--force` replaces an installed
copy, also one with the same version (branch builds carry the version of their
`galaxy.yml`):

```sh
ansible-galaxy collection install --force acme-infra-0.1.0.tar.gz   # or the .tgz of a branch build
```

**Ubuntu 22.04's own ansible-core (2.12.0):** `ansible-galaxy collection install`
crashes there, because Ubuntu ships resolvelib 0.8.1 while 2.12 needs < 0.6.
Running playbooks is not affected. Install by extracting the tarball instead:

```sh
mkdir -p ~/.ansible/collections/ansible_collections/acme/infra
tar -xzf acme-infra-0.1.0.tar.gz -C ~/.ansible/collections/ansible_collections/acme/infra
```

**Offline control node:** copy the tarball over; installing it needs no network.

## Node.js backends: from project to running service

For backend developers; no Ansible knowledge needed. One command prepares a
project, such as a NestJS backend. Run it from the project root:

```sh
ansible-playbook acme.infra.node_setup
```

It writes a `deploy/` directory to commit with the project. Its `README.md` is
the guide for everything after that: building the production image, configuring
it, and deploying it as a rootless Podman service (a Quadlet file, also in
`deploy/`) that starts at boot, from a laptop or from a pipeline. In short:

```sh
ansible-playbook acme.infra.node_image                            # build .image/<name>-<version>.tar
ansible-playbook acme.infra.node_deploy -i deploy/inventory.yml   # install and start it on the servers
```

## Use roles in your own playbooks

A project that writes its own playbooks pins acme.infra in a `requirements.yml`:

```yaml
collections:
  # A release on GitHub. From GitLab's package registry it is:
  # https://<gitlab>/api/v4/projects/<id>/packages/generic/acme-infra/0.1.0/acme-infra-0.1.0.tar.gz
  - name: https://github.com/acme/acme-infra/releases/download/v0.1.0/acme-infra-0.1.0.tar.gz
    type: url
```

`ansible-galaxy collection install -r requirements.yml` installs it. To use a
tarball file instead, such as a branch build or your own build, or a release
downloaded from a private repository (`gh release download v0.1.0 --repo
acme/acme-infra`, or `curl --header "PRIVATE-TOKEN: ..."` on GitLab):

```yaml
collections:
  - name: ./acme-infra-0.1.0.tar.gz
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
| [node_setup](roles/node_setup/README.md) | Prepares a Node.js project: guide, Quadlet file, inventory | The project's machine | No |
| [node_image](roles/node_image/README.md) | Production container image of a Node.js project | The build machine | Yes, during the build |
| [node_deploy](roles/node_deploy/README.md) | Runs that image as a rootless Podman service that starts at boot | Servers (RHEL 9.2+) | No |

Every role documents its variables; read them offline with
`ansible-doc -t role acme.infra.<role>`.

## Ready-made playbooks

For people who don't write Ansible: run these by name from a project's root, no
playbook of your own needed.

| Playbook | What it does |
|---|---|
| `ansible-playbook acme.infra.node_setup` | Writes `deploy/` into the Node.js project, see [node_setup](roles/node_setup/README.md) |
| `ansible-playbook acme.infra.node_image` | Builds the project into an image archive, see [node_image](roles/node_image/README.md) |
| `ansible-playbook acme.infra.node_deploy -i deploy/inventory.yml` | Deploys that image to the servers, see [node_deploy](roles/node_deploy/README.md) |

## Versioning

[Semantic Versioning](https://semver.org): a breaking change to any role's
variables means a new major version. See [CHANGELOG.md](CHANGELOG.md).
