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

It writes an `ansible/` directory to commit with the project, laid out the way
Ansible users expect: `ansible.cfg`, `inventory.yml`, `group_vars/all/` for the
settings, the playbooks, and `templates/service.container.j2`, the Quadlet file.
The project's own files are written once; acme.infra's are brought up to date by
`update-playbooks.yml`, which keeps a changed one as `<file>.bak`. The container's
environment comes from the project's
`.env.production`, its config files from `config/production/`. Everything after
the setup runs from that directory, and its `README.md` is the guide: building
the production image, configuring it, and deploying it as a rootless Podman
service that starts at boot, from a laptop or from a pipeline. In short:

```sh
cd ansible
ansible-playbook prebuild.yml # node_modules for development, installed in a throwaway container
ansible-playbook image.yml    # build images/<name>-<version>.tar
ansible-playbook deploy.yml   # install and start it on the servers in inventory.yml
ansible-playbook site.yml     # both in one go, also for a new version
ansible-playbook remove.yml   # remove it from the servers again, keeping its data
ansible-playbook update-playbooks.yml   # after installing a newer acme.infra
```

On the servers the deploy follows fixed conventions: an account per service,
images in `/opt/containers/images/`, Quadlet files in
`/etc/containers/systemd/users/<UID>/`, the service's own directory, its working
directory, in `/opt/<service>/`. See [node_deploy](roles/node_deploy/README.md).

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
| [node_setup](roles/node_setup/README.md) | Prepares a Node.js project: its `ansible/` directory with settings, inventory, playbooks and guide | The project's machine | No |
| [node_image](roles/node_image/README.md) | Production container image of a Node.js project, and its node_modules for development, built in containers | The build machine | Yes, from sources you choose |
| [node_deploy](roles/node_deploy/README.md) | Runs that image as a rootless Podman service that starts at boot | Servers (RHEL 9.2+) | No |

Every role documents its variables; read them offline with
`ansible-doc -t role acme.infra.<role>`.

## Ready-made playbooks

For people who don't write Ansible: run these by name, no playbook of your own
needed. The playbooks node_setup writes import them.

| Playbook | Run it from | What it does |
|---|---|---|
| `ansible-playbook acme.infra.node_setup` | The project's root | Writes `ansible/` into the Node.js project, see [node_setup](roles/node_setup/README.md) |
| `ansible-playbook acme.infra.node_update` | `ansible/` | Brings acme.infra's files in `ansible/` up to date, the same as node_setup |
| `ansible-playbook acme.infra.node_prebuild` | `ansible/` | Prepares the project for development: node_modules from a throwaway container, see [node_image](roles/node_image/README.md#node_modules-for-development) |
| `ansible-playbook acme.infra.node_image` | `ansible/` | Builds the project into an image archive, see [node_image](roles/node_image/README.md) |
| `ansible-playbook acme.infra.node_deploy` | `ansible/` | Deploys that image to the servers, or a newer version over the old one, see [node_deploy](roles/node_deploy/README.md) |
| `ansible-playbook acme.infra.node_remove` | `ansible/` | Removes the service from the servers, keeping its data unless asked, see [node_deploy](roles/node_deploy/README.md#remove-a-service) |

## Versioning

[Semantic Versioning](https://semver.org): a breaking change to any role's
variables means a new major version. See [CHANGELOG.md](CHANGELOG.md).
