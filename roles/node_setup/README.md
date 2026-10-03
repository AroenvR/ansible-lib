# acme.infra.node_setup

Prepares a Node.js project, such as a NestJS backend, for building and deploying
with acme.infra. No Ansible knowledge needed: run one command from the project root.

```sh
ansible-playbook acme.infra.node_setup
```

It writes an `ansible/` directory into the project, to commit with it. Everything
after this runs from that directory: `cd ansible`. The files are either the
project's or acme.infra's:

| File | What it is | Whose |
|---|---|---|
| `inventory.yml` | The servers to deploy to; this machine by default | The project's |
| `group_vars/all/project.yml` | The project's settings, written with every default | The project's |
| `container.env` | The container's settings and secrets, kept out of git. Copied from the project's `.env.production` if it has one (without quotes around values, which Podman would keep) | The project's |
| `group_vars/all/defaults.yml` | Every setting at its default; `project.yml` wins | acme.infra's |
| `prebuild.yml` | Installs node_modules for development in a throwaway container, keeping the previous one as a backup | acme.infra's |
| `image.yml`, `deploy.yml`, `site.yml`, `remove.yml` | Build the image, deploy it, both in one go (also for updates), remove the service | acme.infra's |
| `templates/service.container.j2` | The Quadlet file of the service; the deploy renders it | acme.infra's |
| `update-playbooks.yml` | Brings acme.infra's files up to date | acme.infra's |
| `ansible.cfg`, `.gitignore`, `README.md` | Ansible's settings (with a log, `ansible.log`), what stays out of git, the guide | acme.infra's |

The project's files are written once and never touched again. acme.infra's are
brought up to date by every run, whether `ansible-playbook acme.infra.node_setup`
from the project root or `ansible-playbook update-playbooks.yml` from `ansible/`:
a file that changes is kept as `<file>.bak` first (one copy, git-ignored), so a
reviewer sees what a local change was. Changes every project could use belong in
acme.infra. An `ansible/` of an older setup, with a single `group_vars/all.yml`,
gets it moved to `group_vars/all/project.yml`.

Only the guide names the project: the other files take its name and version
from package.json whenever they run, so they fit any project.

## Requirements

A `package.json` with a `name` and a `version`. Any machine with ansible-core;
no network access. The service is named after the package: `@acme/orders-api`
becomes `acme-orders-api`.

## Options

`ansible-doc -t role acme.infra.node_setup`.
