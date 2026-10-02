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
| `group_vars/all.yml` | The project's settings (port, directories, account), commented out at their defaults |
| `image.yml`, `deploy.yml` | The playbooks: `ansible-playbook image.yml`, `ansible-playbook deploy.yml` |
| `container.env` | The container's settings and secrets, kept out of git by `.gitignore` |

Run it again after updating acme.infra: it replaces `README.md` with the current
guide and never touches the other files, which belong to the project.

## Requirements

A `package.json` with a `name` and a `version`. Any machine with ansible-core;
no network access. The service is named after the package: `@acme/orders-api`
becomes `acme-orders-api`.

## Options

`ansible-doc -t role acme.infra.node_setup`.
