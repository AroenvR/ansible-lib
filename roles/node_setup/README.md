# acme.infra.node_setup

Prepares a Node.js project, such as a NestJS backend, for building and deploying
with acme.infra. No Ansible knowledge needed: run one command from the project root.

```sh
ansible-playbook acme.infra.node_setup
```

It writes `deploy/` into the project, to commit to the project's repository:

| File | What it is |
|---|---|
| `README.md` | The guide: how to build the image, configure and deploy it, also from a pipeline |
| `<name>.container` | The Quadlet file that runs the image as a rootless Podman service on a server |
| `inventory.yml` | The servers to deploy to; this machine by default |
| `container.env` | The container's settings and secrets, kept out of git by `deploy/.gitignore` |

`<name>` comes from package.json: `@acme/orders-api` becomes `acme-orders-api`.

Run it again after updating acme.infra: it replaces `README.md` with the current
guide and never touches the other files, which belong to the project.

## Requirements

A `package.json` with a `name` and a `version`. Any machine with ansible-core;
no network access.

## Options

`ansible-doc -t role acme.infra.node_setup`.
