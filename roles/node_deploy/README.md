# acme.infra.node_deploy

Deploys a Node.js project's image to servers as a rootless Podman service that
starts at boot. No Ansible knowledge needed: after [node_setup](../node_setup/README.md)
and [node_image](../node_image/README.md), run one command from the project's
`ansible/` directory:

```sh
ansible-playbook deploy.yml        # add --ask-become-pass if sudo asks for a password
```

## Conventions

The deploy works as root (through sudo) and keeps every service apart:

| What | Where, on the server |
|---|---|
| The account the service runs as | `<service>` (from package.json: `@acme/orders-api` becomes `acme-orders-api`), lingering enabled |
| Image archives | `/opt/containers/images/<service>-<version>.tar`, loaded into the account's Podman |
| Quadlet file and environment file | `/etc/containers/systemd/users/<the account's UID>/<service>.container` and `.env` (root-owned; the `.env` readable by the account only) |
| The service's directory | `/opt/<service>/`: the app's working directory, owned by the account, at the same path in the container |
| The service's config files | `/opt/<service>/config/`, the project's `config/production/*.json`, read-only for the app |

On every server in the inventory it:

1. creates the account and lets it run services while nobody is logged in
   (`loginctl enable-linger`), so the service starts at boot;
2. copies the image archive of the version in package.json and loads it as the account;
3. creates the service's directory and `data/` in it when missing, copies the
   config files to its `config/` (and removes those the project no longer has),
   installs `container.env` and the Quadlet file;
4. reloads the account's systemd and restarts the service when the image, the
   settings, the config files or the Quadlet file changed, or starts it when it
   is not running;
5. waits until the service answers HTTP requests. If it does not within a
   minute, the deploy fails and shows the service's log;
6. removes the archives of other versions and the images the account no longer
   uses, so only the deployed version stays.

Running it again without changes changes nothing.

The account's Podman and systemd are driven with `runuser -u <service> -- env
XDG_RUNTIME_DIR=/run/user/<UID> ...` rather than `systemctl --user -M <service>@`:
`-M` needs a D-Bus session bus for the account, which minimal systems such as
Red Hat's UBI images lack.

## The service's directory

`/opt/<service>/` belongs to the app: it is its working directory, at the same
path inside the container, so relative paths end up there (`config/db.json`,
`prod.db`, `data/uploads/`). The deploy creates it, and `data/` in it, when
missing, and manages nothing in it but `config/`, which the app can read and not
change. If it belongs to another UID (a new account after a removal), the deploy
hands it, with everything in it, to the account.

The code stays in the image, read-only, at `/opt/app-root/src`. The container
runs as the image's user 1001, mapped to the account, so what the app writes
belongs to the account on the server. Its root filesystem is read-only, it has no
capabilities and cannot gain privileges. `/tmp` (`os.tmpdir()`) is in memory, at
most `node_deploy_tmp_size`, and emptied on every restart. Every service has its
own account, UID and range of subordinate UIDs, so two services never share
files or processes, even though both run as 1001 inside their containers.

After a crash, systemd starts the service again every 10 seconds.

## Settings

In the project's `ansible/group_vars/all/project.yml`:

| Variable | Default | What |
|---|---|---|
| `node_deploy_port` | `3000` | The service's port on the server |
| `node_deploy_bind_address` | `127.0.0.1` | `0.0.0.0` makes the port reachable from other machines |
| `node_deploy_dir` | `/opt/<service>` | The service's directory, the app's working directory |
| `node_deploy_user` | `<service>` | The account |
| `node_deploy_uid` | (any free UID) | Fix the account's UID, e.g. the same on every server |
| `node_deploy_container_port` | `3000` | The app's port inside the container (`node_image_port`) |
| `node_deploy_config_files` | `config/production/*.json` | The config files to copy, relative to the project's root |
| `node_deploy_tmp_size` | `512m` | Size limit of the app's `/tmp`, which is in memory |

All options: `ansible-doc -t role acme.infra.node_deploy`.

## The Quadlet file

The project's `ansible/templates/service.container.j2` (from
[node_setup](../node_setup/README.md)) is the template of the Quadlet file:
change it for anything the settings do not cover, such as a memory limit or a
network. It belongs to acme.infra: an update replaces it and keeps the project's
version as `service.container.j2.bak`, so a change every project could use belongs
in acme.infra. The deploy fills in `node_deploy_service`, `node_deploy_image` (with
the version from package.json), `node_deploy_user`, `node_deploy_dir` and the
settings above, and restarts the service when the result changes. Without that
file, the deploy uses its own copy, [templates/service.container.j2](templates/service.container.j2).

## What a server needs

- RHEL 9.2 or newer with Podman 4.4 or newer, which brings Quadlet: `sudo dnf install podman`.
- SSH access for Ansible as root or as an account that may use sudo
  (not needed when deploying to `localhost`).

No network access: the image comes from the project, not from a registry.

## Deploy a new version

Build the new version and run the deploy again, from the project's `ansible/`
directory: `ansible-playbook site.yml` does both. The deploy replaces the image,
restarts the service and removes the previous version.
To go back, check out the previous version of the project and deploy that.

## Remove a service

```sh
ansible-playbook remove.yml                                  # or: ansible-playbook acme.infra.node_remove
ansible-playbook remove.yml -e node_deploy_remove_data=true  # the app's data too
```

Takes away what the deploy created: the service, its account (home directory,
Podman storage and images included), the Quadlet and environment files, the
image archives and the config files. The service's directory, with everything
the app wrote, stays unless `node_deploy_remove_data` is true; a later deploy
uses it again. Running it again changes nothing. The shared directories
(`/opt/containers/images/`, `/etc/containers/systemd/users/`) stay, as other
services use them.

## Check a service

```sh
sudo systemctl --user -M <service>@ status <service>
sudo journalctl _SYSTEMD_USER_UNIT=<service>.service
```
