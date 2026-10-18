# Deploy a Node.js backend

From a Node.js project, such as a NestJS backend, to a rootless Podman service
on your servers that starts at boot. For backend developers; no Ansible
knowledge needed. One command prepares the project; a few more, run from the
directory it writes, build and deploy it, from a laptop or from a pipeline.

## Before you start

- **The project**: a `package.json` with a `name` and a `version`, and a
  `build` script that makes `dist/main.js`, as every NestJS project has. The
  rest of what it needs, such as a server listening on port 3000 on all
  interfaces: [What your project
  needs](../roles/node_image/README.md#what-your-project-needs).
- **The machine that runs Ansible**, such as your laptop: ansible-core and
  aslib.infra ([Install aslib.infra](install.md)). It builds the image, so it
  needs Podman 4.9 or newer (RHEL 9.6 or Ubuntu 24.04) and access to Red Hat's
  registry and to everything npm downloads, or to mirrors of them
  ([download sources](../roles/node_image/README.md#download-sources)).
- **The servers**: RHEL 9.6 or newer with its Podman (`sudo dnf install
  podman`), and SSH access for Ansible as root or as an account that may use
  sudo ([node_deploy](../roles/node_deploy/README.md#what-a-server-needs)).
  Nothing is downloaded there but the `acl` package, when missing: the image
  comes from the project.

## Set up the project

From the project's root:

```sh
ansible-playbook aslib.infra.node_setup   # writes ansible/, to commit with the project
```

It writes an `ansible/` directory, laid out the way Ansible users expect:
`ansible.cfg`, `inventory.yml`, `group_vars/all/` for the settings, the
playbooks, and `templates/service.container.j2`, the Quadlet file. Its
`README.md` is the project's own guide: it names the project and goes through
every step below in detail ([its
template](../roles/node_setup/templates/README.md.j2)). The service is named
after the package: `@acme/orders-api` becomes `acme-orders-api`.

The project's own files are written once and never touched again; aslib.infra's
are brought up to date by `update-playbooks.yml` ([which is
which](../roles/node_setup/README.md)). Before the first deploy, look at the
project's:

- `inventory.yml`: the servers. It lists this machine by default; replace it
  with your servers unless this machine is one.
- `group_vars/all/project.yml`: the settings, written with every default, such
  as the port on the server (`podman_service_port`).
- `container.env`: the container's environment and secrets, copied from the
  project's `.env.production` if it has one. It stays out of git.
- `../config/production/*.json`: the app's config files, which every deploy
  copies to the server.

## Build and deploy

Everything from here on runs from `ansible/`:

```sh
cd ansible
ansible-playbook prebuild.yml           # node_modules for development, from a throwaway container
ansible-playbook build-and-deploy.yml   # build the image, then install and start it on the servers
```

Add `--ask-become-pass` when sudo asks for a password. `prebuild.yml` is for
development: npm runs the packages' install scripts in a container instead of
on your machine
([node_image](../roles/node_image/README.md#node_modules-for-development)); the
image build does not need it.

`build-and-deploy.yml` runs `image.yml`, then `deploy.yml`; each also runs on
its own. The image lands in `images/<service>-<version>.tar`, with the version
from package.json ([node_image](../roles/node_image/README.md#build)). The
deploy installs it on every server in the inventory and waits until the service
answers on its port, `127.0.0.1:3000` by default; if it does not, the deploy
shows the service's log and stops
([node_deploy](../roles/node_deploy/README.md)). On the server, `curl
http://127.0.0.1:3000/` then reaches the app. Every run writes its output to
`logs/<playbook>-<UTC time>.log`.

On the servers the deploy follows fixed conventions: an account per service,
and the service's own directory, its working directory, in `/opt/<service>/`.
Where everything goes: [What runs on a server](servers.md#conventions).

## Day to day

From `ansible/`:

```sh
ansible-playbook aslib.infra.overview    # what runs on the servers, with the command that shows each log
ansible-playbook build-and-deploy.yml    # a new version: raise the version in package.json first
ansible-playbook deploy.yml              # a change to container.env, config files, settings or Quadlet template only
ansible-playbook restart.yml             # restart it, for a change the deploy does not see
ansible-playbook update-playbooks.yml    # after installing a newer aslib.infra
ansible-playbook remove.yml              # remove it from the servers, keeping its directory
```

- A new version replaces the old one: only the deployed version stays. To go
  back, check out the previous version of the project and deploy that
  ([node_deploy](../roles/node_deploy/README.md#deploy-a-new-version)).
- `update-playbooks.yml` brings aslib.infra's files up to date, keeping a
  changed one as `<file>.bak`; new settings appear in
  `group_vars/all/defaults.yml`. Review the changes before committing them.
- `remove.yml` keeps `/opt/<service>/`, with everything the app wrote, unless
  you ask ([node_deploy](../roles/node_deploy/README.md#remove-a-service)).

## Next

- The project's guide, `ansible/README.md`: every step in detail, an offline
  checklist for a build machine, and the same commands in a pipeline.
- [node_image](../roles/node_image/README.md): what goes into the image, and
  its options.
- [node_deploy](../roles/node_deploy/README.md) and
  [podman_service](../roles/podman_service/README.md): the app on the server,
  the Quadlet file and every setting of the service.
- [What runs on a server](servers.md), for root on the servers.
- [Run Claude Code on a server](claude-code.md), next to the service.
