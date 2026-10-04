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

In the project's `ansible/group_vars/all/project.yml`:

| Variable | Default | What |
|---|---|---|
| `podman_service_port` | `3000` | The service's port on the server |
| `podman_service_bind_address` | `127.0.0.1` | `0.0.0.0` makes the port reachable from other machines |
| `podman_service_container_port` | `3000` | The app's port inside the container (`node_image_port`) |
| `podman_service_dir` | `/opt/<service>` | The service's directory, the app's working directory |
| `podman_service_user` | `<service>` | The account |
| `podman_service_uid` | (any free UID) | Fix the account's UID, e.g. the same on every server |
| `podman_service_tmp_size` | `512m` | Size limit of the app's `/tmp`, which is in memory |
| `node_deploy_config_files` | `config/production/*.json` | The config files to copy, relative to the project's root |

Before 0.1.0, the `podman_service_` settings were called `node_deploy_`; the
deploy stops, naming the new name, when the project still sets an old one.

All options: `ansible-doc -t role aslib.infra.node_deploy` and
`ansible-doc -t role aslib.infra.podman_service`.

## The app on the server

`/opt/<service>/` is the app's working directory, at the same path inside the
container, so relative paths end up there (`config/db.json`, `prod.db`,
`data/uploads/`). The deploy creates it and `data/` in it, and manages nothing
in it but `config/`, which the app can read and not change. The code stays
read-only in the image, at `/opt/app-root/src`. `/tmp` (`os.tmpdir()`) is in
memory, at most `podman_service_tmp_size`, and emptied on every restart.

## The Quadlet file

The project's `ansible/templates/service.container.j2` (from
[node_setup](../node_setup/README.md)) is the template of the Quadlet file:
change it for anything the settings do not cover, such as a memory limit or a
network. It belongs to aslib.infra: an update replaces it and keeps the project's
version as `service.container.j2.bak`, so a change every project could use belongs
in aslib.infra. Its header lists the variables it can use. The deploy restarts
the service when the result changes.

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

Takes away what the deploy created: the service, its account (home directory,
Podman storage and images included), the Quadlet and environment files and the
image archives. The service's directory, with everything the app wrote and its
config files, stays as it is unless `podman_service_remove_workdir` is true; a
later deploy uses it again. Running it again changes nothing.

## What a server needs

RHEL 9.2 or newer with Podman 4.4 or newer (`sudo dnf install podman`), and SSH
access for Ansible as root or with sudo. No network access.

## Check a service

Every service on the servers in the inventory, with the log of those that do
not run ([podman_overview](../podman_overview/README.md)):

```sh
ansible-playbook aslib.infra.podman_overview
```

One service, on its server:

```sh
sudo systemctl --user -M <account>@ status <service>   # the account: <service> by default
sudo journalctl _SYSTEMD_USER_UNIT=<service>.service            # its output; -f to follow
```
