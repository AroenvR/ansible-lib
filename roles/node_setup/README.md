# acme.infra.node_setup

Prepares a Node.js project, such as a NestJS backend, for building and deploying
with acme.infra. No Ansible knowledge needed: run one command from the project root.

```sh
ansible-playbook acme.infra.node_setup
```

It writes an `ansible/` directory into the project, to commit with it. Everything
after this runs from that directory: `cd ansible`.

| File | What it is |
|---|---|
| `README.md` | The guide: building the image, configuring and deploying it, also from a pipeline |
| `ansible.cfg` | Points Ansible at the inventory |
| `inventory.yml` | The servers to deploy to; this machine by default |
| `group_vars/all.yml` | The project's settings (download sources, port, directories, account), commented out at their defaults |
| `prebuild.yml` | Installs node_modules for development in a throwaway container, keeping the previous one as a backup |
| `image.yml`, `deploy.yml`, `site.yml`, `remove.yml` | The playbooks: build the image, deploy it, both in one go (also for updates), remove the service |
| `templates/service.container.j2` | The Quadlet file of the service, for the project to tune; the deploy renders it |
| `container.env` | The container's settings and secrets, kept out of git by `.gitignore`. Copied from the project's `.env.production` if it has one (without quotes around values, which Podman would keep) |

Run it again after updating acme.infra: it replaces `README.md` with the current
guide, adds files that are missing and never touches the others, which belong
to the project. Only the guide names the project: the other files take its name
and version from package.json whenever they run, so they fit any project.

## Requirements

A `package.json` with a `name` and a `version`. Any machine with ansible-core;
no network access. The service is named after the package: `@acme/orders-api`
becomes `acme-orders-api`.

## Options

`ansible-doc -t role acme.infra.node_setup`.
