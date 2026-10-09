# aslib.infra.node_deploy

Deploys a Node.js project's image to servers as a rootless Podman service that
starts at boot. No Ansible knowledge needed: after [node_setup](../node_setup/README.md)
and [node_image](../node_image/README.md), run one command from the project's
`ansible/` directory:

```sh
ansible-playbook deploy.yml        # add --ask-become-pass if sudo asks for a password
```

This role supplies the project's files; [podman_service](../podman_service/README.md)
does the work on the server, following its conventions. From the project's
`ansible/` directory it takes:

| What | From |
|---|---|
| The service's name | package.json: `@acme/orders-api` becomes `acme-orders-api`, also the name of its account and of `/opt/acme-orders-api/` |
| The image | `images/<service>-<version>.tar`, the version in package.json (from [node_image](../node_image/README.md)) |
| The container's environment variables and secrets | `container.env` |
| The app's config files | `../config/production/*.json` (`node_deploy_config_files`) |
| The Quadlet file | `templates/service.container.j2`, or podman_service's own without it |
| The service's settings | `group_vars/all/project.yml`: `podman_service_port` and more, below |

On every server in the inventory it creates the service's account and
directory, loads the image, installs `container.env`, the config files and the
Quadlet file, (re)starts the service and waits until it answers HTTP requests.
Only the deployed version stays. Running it again without changes changes
nothing. Step by step: [podman_service](../podman_service/README.md#conventions).

## Settings

In the project's `ansible/group_vars/all/project.yml`. The service's settings
(its port, bind address, directory, account, UID, `/tmp` and the shared zone)
are [podman_service's](../podman_service/README.md#settings);
`podman_service_container_port` is the app's port in the container
(`node_image_port`). This role's own:

| Variable | Default | What |
|---|---|---|
| `node_deploy_config_files` | `config/production/*.json` | The config files to copy, relative to the project's root |
| `node_deploy_health_check` | `true` | A [health check](../podman_service/README.md#the-quadlet-file) with the image's Node.js: healthy while the app answers HTTP on its port with anything but a server error (5xx) |

Before 0.1.0, the `podman_service_` settings were called `node_deploy_`; the
deploy stops, naming the new name, when the project still sets an old one.

All options: `ansible-doc -t role aslib.infra.node_deploy` and
`ansible-doc -t role aslib.infra.podman_service`.

## The app on the server

The service's directory, `/opt/<service>/`, is the app's working directory
([podman_service](../podman_service/README.md#the-services-directory)), so
relative paths end up there (`config/db.json`, `prod.db`, `data/uploads/`). The
code stays read-only in the image, at `/opt/app-root/src`. `os.tmpdir()` is the
container's `/tmp`, in memory and emptied on every restart.

## The Quadlet file

The project's `ansible/templates/service.container.j2` (from
[node_setup](../node_setup/README.md)) is the template of the Quadlet file
([what it sets](../podman_service/README.md#the-quadlet-file)): change it for
anything the settings do not cover, such as a memory limit or a network. It
belongs to aslib.infra: an update replaces it and keeps the project's version as
`service.container.j2.bak`, so a change every project could use belongs in
aslib.infra. The deploy restarts the service when the result changes.

## Deploy a new version

Build the new version and run the deploy again, from the project's `ansible/`
directory: `ansible-playbook build-and-deploy.yml` does both. The deploy replaces the image,
restarts the service and removes the previous version.
To go back, check out the previous version of the project and deploy that.

## Restart the service

```sh
ansible-playbook restart.yml                                       # or: ansible-playbook aslib.infra.node_restart
```

Restarts the service and waits until it answers, for a change the deploy does
not see. A deploy restarts it by itself when it changes something.

## Remove a service

```sh
ansible-playbook remove.yml                                        # or: ansible-playbook aslib.infra.node_remove
ansible-playbook remove.yml -e podman_service_remove_workdir=true  # the service's directory too
```

What it takes away and what stays: [podman_service](../podman_service/README.md#remove-a-service).
A later deploy uses the service's directory again.

## What a server needs

What [podman_service](../podman_service/README.md#what-a-server-needs) needs:
RHEL 9.6 or newer with its Podman, and SSH access for Ansible as root or with
sudo.

## Check a service

```sh
ansible-playbook aslib.infra.overview
```

Every service on the servers in the inventory, with the command that shows its
log; by hand: [podman_service](../podman_service/README.md#check-a-service).
