# aslib.infra.podman_service

Runs an image archive (made with `podman save`) as a rootless Podman service
that starts at boot, on RHEL 9 servers. [node_deploy](../node_deploy/README.md)
uses it for Node.js projects: their settings for the server are this role's.
All options: `ansible-doc -t role aslib.infra.podman_service`.

```yaml
- name: Deploy orders-api
  hosts: all
  become: true
  gather_facts: false
  force_handlers: true  # a failed deploy still restarts the service for what it changed
  tasks:
    - name: Deploy the service
      ansible.builtin.import_role:
        name: aslib.infra.podman_service
      vars:
        podman_service_name: orders-api
        podman_service_image: localhost/orders-api:1.4.0
        podman_service_archive: "{{ playbook_dir }}/images/orders-api-1.4.0.tar"
        podman_service_env_file: "{{ playbook_dir }}/container.env"
        podman_service_port: 8080
```

## Conventions

The deploy works as root (through sudo) and keeps every service apart:

| What | Where, on the server |
|---|---|
| The account the service runs as | `<service>` (`podman_service_user`), lingering enabled, so its services start at boot |
| Image archives | `/opt/containers/images/<service>/`, loaded into the account's Podman |
| Quadlet file and environment file | `/etc/containers/systemd/users/<the account's UID>/<service>.container` and `.env` (root-owned; the `.env` readable by the account only) |
| The service's directory | `/opt/<service>/`: the app's working directory, owned by the account, at the same path in the container |
| The service's config files | `/opt/<service>/config/`, read-only for the app |

On every server it:

1. creates the account and lets it run services while nobody is logged in
   (`loginctl enable-linger`);
2. copies the image archive and loads it as the account (also when the archive
   is there but the image is not);
3. creates the service's directory and `data/` in it when missing, copies the
   config files to its `config/` (and removes those no longer listed), installs
   the environment file and the Quadlet file;
4. reloads the account's systemd and restarts the service when the image, the
   environment file, the config files or the Quadlet file changed, or starts it
   when it is not running;
5. waits until the service answers HTTP requests on its port. If it does not
   within a minute, the deploy fails and shows the service's log;
6. removes the archives of other versions and the account's other images, so
   only the deployed version stays.

Running it again without changes changes nothing.

The account's Podman and systemd are driven with `runuser -u <account> -- env
XDG_RUNTIME_DIR=/run/user/<UID> ...` rather than `systemctl --user -M <account>@`:
`-M` needs a D-Bus session bus for the account, which minimal systems such as
Red Hat's UBI images lack.

## The service's directory

`/opt/<service>/` belongs to the app: it is its working directory, at the same
path inside the container, so relative paths end up there (`config/db.json`,
`prod.db`, `data/uploads/`). The deploy creates it, and `data/` in it, when
missing, and manages nothing in it but `config/`, which the app can read and not
change. If it belongs to another UID (a new account after a removal), the deploy
hands it, with everything in it, to the account.

## The Quadlet file

[templates/service.container.j2](templates/service.container.j2) runs the
container as the user of Red Hat's UBI images, 1001, mapped to the account, so
what the app writes belongs to the account on the server. Its root filesystem is
read-only, it has no capabilities and cannot gain privileges, and `/tmp` is in
memory (`podman_service_tmp_size`) and emptied on every restart. Every service
has its own account, UID and range of subordinate UIDs, so two services never
share files or processes, even though both run as 1001 inside their containers.
After a crash, systemd starts the service again every 10 seconds.

For anything the settings do not cover, such as a memory limit or a network,
pass a template of your own as `podman_service_quadlet_template`; start from a
copy of this one, which lists the variables it can use.

## Settings

| Variable | Default | What |
|---|---|---|
| `podman_service_port` | `3000` | The service's port on the server |
| `podman_service_bind_address` | `127.0.0.1` | `0.0.0.0` makes the port reachable from other machines |
| `podman_service_container_port` | `3000` | The app's port inside the container |
| `podman_service_dir` | `/opt/<service>` | The service's directory, the app's working directory |
| `podman_service_user` | `<service>` | The account |
| `podman_service_uid` | (any free UID) | Fix the account's UID, e.g. the same on every server |
| `podman_service_tmp_size` | `512m` | Size limit of the app's `/tmp`, which is in memory |
| `podman_service_config_files` | `[]` | Config files on the Ansible machine, for `config/` |
| `podman_service_quadlet_template` | the role's | A Quadlet template of your own |

## Remove a service

```yaml
    - name: Remove the service, keeping its data
      ansible.builtin.import_role:
        name: aslib.infra.podman_service
        tasks_from: remove
      vars:
        podman_service_name: orders-api
```

Takes away what the deploy created: the service, its account (home directory,
Podman storage and images included), the Quadlet and environment files, the
image archives and the config files. The service's directory, with everything
the app wrote, stays unless `podman_service_remove_data` is true; a later deploy
uses it again. Running it again changes nothing. The shared directories
(`/opt/containers/images/`, `/etc/containers/systemd/users/`) stay.

## What a server needs

- RHEL 9.2 or newer with Podman 4.4 or newer, which brings Quadlet: `sudo dnf install podman`.
- SSH access for Ansible as root or as an account that may use sudo
  (not needed when deploying to `localhost`).

No network access: the image comes from the archive, not from a registry.

## Limitations

- The service must answer HTTP on its port: that is how the deploy knows it started.
- Not tested yet: a deploy over SSH with sudo to a remote server (tests deploy
  to a RHEL 9 test container), and SELinux in enforcing mode.
- Tested through [node_deploy](../node_deploy/README.md)'s scenario, which
  deploys, updates, removes and redeploys a service.

## Check a service

Every service on the servers in the inventory, with the log of those that do
not run ([podman_overview](../podman_overview/README.md)):

```sh
ansible-playbook aslib.infra.podman_overview
```

One service, on its server:

```sh
sudo systemctl --user -M <account>@ status <service>
sudo journalctl _SYSTEMD_USER_UNIT=<service>.service
```
