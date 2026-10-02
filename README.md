# acme.infra

Tested building blocks (Ansible roles and ready-made playbooks) for RHEL 9 and
Ubuntu 22.04 servers and for building container images.
Developing the collection itself? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Compatibility

| | Supported |
|---|---|
| Ansible controller | The `ansible-core` package of Ubuntu 22.04 (2.12) or RHEL 9.6 (2.14), or newer |
| Managed servers | Ubuntu 22.04, RHEL 9 |
| Other collections | None. Only `ansible.builtin` is used. |

## What a managed server needs

Every role assumes a default server install. Nothing else is required unless a
role's README says so.

- Python 3, plus `python3-apt` on Ubuntu. Both are part of a default install.
- No internet access. A role that needs package repositories says so in its
  README, and names the step that needs them. Repository and download URLs are
  always role variables, so they can point at your mirror or proxy.

## Use it in your project

Each release is a tarball holding only what runs: no tests, no dev tooling.
A project (a backend app, for example) depends on it the way it would on an
npm package:

```text
deploy/
├── ansible.cfg        # collections_path = ./collections
├── requirements.yml   # the pinned dependency, see below
├── site.yml           # the project's own playbook
└── .gitignore         # collections/ (installed, like node_modules)
```

```yaml
# requirements.yml
collections:
  # Release asset on GitHub. From GitLab's package registry it is:
  # https://<gitlab>/api/v4/projects/<id>/packages/generic/acme-infra/0.1.0/acme-infra-0.1.0.tar.gz
  - name: https://github.com/acme/acme-infra/releases/download/v0.1.0/acme-infra-0.1.0.tar.gz
    type: url
```

Install it, then run your playbook:

```sh
ansible-galaxy collection install -r requirements.yml
```

**Private repository:** the URL then needs a token, which `requirements.yml`
cannot hold. Download the tarball first (`gh release download v0.1.0 --repo acme/acme-infra`,
or `curl --header "PRIVATE-TOKEN: ..."` on GitLab) and point at the file instead:
`name: ./acme-infra-0.1.0.tar.gz` with `type: file`.

**Offline control node:** on a connected machine run
`ansible-galaxy collection download -r requirements.yml -p vendor`, copy
`vendor/` over, then `cd vendor && ansible-galaxy collection install -r requirements.yml -p ../collections --offline`.

**Ubuntu 22.04's own ansible-core (2.12.0):** `ansible-galaxy collection install`
crashes there, because Ubuntu ships resolvelib 0.8.1 while 2.12 needs < 0.6.
Running playbooks is not affected. Install by extracting the tarball instead:

```sh
mkdir -p collections/ansible_collections/acme/infra
tar -xzf acme-infra-0.1.0.tar.gz -C collections/ansible_collections/acme/infra
```

## Roles

| Role | Purpose | Runs on | Needs network access |
|---|---|---|---|
| [sudoers](roles/sudoers/README.md) | sudo rules as validated drop-in files | Servers | Only if sudo is missing |
| [node_image](roles/node_image/README.md) | Production container image of a Node.js project | The build machine | Yes, during the build |

Every role documents its variables; read them offline with
`ansible-doc -t role acme.infra.<role>`.

## Ready-made playbooks

For people who don't write Ansible: run these by name, no playbook of your own needed.

| Playbook | What it does |
|---|---|
| `ansible-playbook acme.infra.node_image` | Builds the Node.js project in the current directory into an image archive, see [node_image](roles/node_image/README.md) |

## Versioning

[Semantic Versioning](https://semver.org): a breaking change to any role's
variables means a new major version. See [CHANGELOG.md](CHANGELOG.md).
