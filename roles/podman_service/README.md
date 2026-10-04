# aslib.infra.podman_service

Runs an image archive (made with `podman save`) as a rootless Podman service
that starts at boot, on RHEL 9 servers. [node_deploy](../node_deploy/README.md)
(Node.js projects) and [claude_code](../claude_code/README.md) use it: their
settings for the server are this role's.
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
| The shared zone | `/opt/containers/shared/`, the same for every service, at the same path in the container |

On every server it:

1. creates the account and lets it run services while nobody is logged in
   (`loginctl enable-linger`); adds it to the group of the shared zone, and
   creates the zone when missing;
2. copies the image archive and loads it as the account (also when the archive
   is there but the image is not);
3. creates the service's directory and `data/` in it when missing, copies the
   config files to its `config/` (and removes those no longer listed), installs
   the environment file and the Quadlet file;
4. reloads the account's systemd and restarts the service when the image, the
   environment file, the config files or the Quadlet file changed, or starts it
   when it is not running;
5. waits until the service answers HTTP requests on its port, or, for a service
   without a port, until it runs. If it does not within a minute, the deploy
   fails and shows the service's log;
6. removes the archives of other versions and the account's other images, so
   only the deployed version stays.

Running it again without changes changes nothing.

Fix the UIDs of all services on a server, or of none: a service without one takes
the next free UID, which may be the one another service is to get later.

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

## The shared zone

`/opt/containers/shared/` is where services hand data to one another: every
service with `podman_service_shared` (the default) reads and writes it, at the
same path in its container. Its accounts are members of the group
`containers-shared`, which owns the directory (mode 2770), and a default ACL makes
everything created in it writable by the group, whichever service created it.
The zone's [README.md](files/shared-README.md), root's and rewritten by every
deploy, tells humans and agents how to work there. A service joins with its next
deploy; one that leaves (`podman_service_shared: false`) keeps the group but no
longer sees the directory. With SELinux, the directory is labelled for
containers. The default ACL needs `setfacl`: the deploy installs the `acl`
package when a server lacks it, as a minimal RHEL install does.

## The Quadlet file

[templates/service.container.j2](templates/service.container.j2) runs the
container as the user of Red Hat's UBI images, 1001, mapped to the account, so
what the app writes belongs to the account on the server. Its root filesystem is
read-only, it has no capabilities and cannot gain privileges, and `/tmp` is in
memory (`podman_service_tmp_size`) and emptied on every restart. Every service
has its own account, UID and range of subordinate UIDs, so two services never
share files or processes, even though both run as 1001 inside their containers.
After a crash, systemd starts the service again every 10 seconds.

The app's output goes to the journal (`--log-driver=journald`), where root reads
it. Without that, Podman writes it to a file in the account's storage whenever
the account cannot read the journal, which is RHEL's default; `podman logs` as
the account cannot read the journal there either.

For anything the settings do not cover, such as a memory limit or a network,
pass a template of your own as `podman_service_quadlet_template`; start from a
copy of this one, which lists the variables it can use.

## Settings

| Variable | Default | What |
|---|---|---|
| `podman_service_port` | `3000` | The service's port on the server; `0` for a service without one |
| `podman_service_bind_address` | `127.0.0.1` | `0.0.0.0` makes the port reachable from other machines |
| `podman_service_container_port` | `3000` | The app's port inside the container |
| `podman_service_dir` | `/opt/<service>` | The service's directory, the app's working directory |
| `podman_service_user` | `<service>` | The account |
| `podman_service_uid` | (any free UID) | Fix the account's UID, e.g. the same on every server |
| `podman_service_tmp_size` | `512m` | Size limit of the app's `/tmp`, which is in memory |
| `podman_service_shared` | `true` | Give the service the shared zone, `/opt/containers/shared/` |
| `podman_service_config_files` | `[]` | Config files on the Ansible machine, for `config/`; or `{name: ..., content: ...}` for one made from a variable |
| `podman_service_quadlet_template` | the role's | A Quadlet template of your own |

## Restart a service

```yaml
    - name: Restart the service and wait until it is ready
      ansible.builtin.import_role:
        name: aslib.infra.podman_service
        tasks_from: restart
      vars:
        podman_service_name: orders-api
        podman_service_port: 8080
```

Restarts the service as its account and waits until it is ready, as the deploy
does: it answers on its port, or, without one, runs. For a restart the deploy
would not do; the deploy restarts the service itself when the image, the
environment file, the config files or the Quadlet file changed.

## Remove a service

```yaml
    - name: Remove the service, keeping its directory
      ansible.builtin.import_role:
        name: aslib.infra.podman_service
        tasks_from: remove
      vars:
        podman_service_name: orders-api
```

Takes away what the deploy created: the service, its account (home directory,
Podman storage and images included), the Quadlet and environment files and the
image archives. The service's directory, with everything the app wrote and its
config files, stays as it is unless `podman_service_remove_workdir` is true; a
later deploy uses it again. Running it again changes nothing. The shared directories
(`/opt/containers/images/`, `/etc/containers/systemd/users/`, the shared zone with
what the service wrote there) stay.

## What a server needs

- RHEL 9.2 or newer with Podman 4.4 or newer, which brings Quadlet: `sudo dnf install podman`.
- SSH access for Ansible as root or as an account that may use sudo
  (not needed when deploying to `localhost`).

No network access: the image comes from the archive, not from a registry. The
one exception is the `acl` package for the shared zone, installed from the
server's repositories (RHEL's BaseOS) when it is missing.

## Limitations

- A service with a port must answer HTTP on it: that is how the deploy knows it
  started. One without a port counts as started once systemd runs it.
- Not tested yet: a deploy over SSH with sudo to a remote server (tests deploy
  to a RHEL 9 test container), and SELinux in enforcing mode.
- Tested through [node_deploy](../node_deploy/README.md)'s scenario, which
  deploys, updates, removes and redeploys a service, next to Claude Code (a
  service without a port) on the same server, sharing the shared zone.

## Check a service

Every service on the servers in the inventory, with the command that shows its
log, and the latest log lines of those that do not run
([podman_overview](../podman_overview/README.md)):

```sh
ansible-playbook aslib.infra.overview
```

One service, on its server:

```sh
sudo systemctl --user -M <account>@ status <service>
sudo journalctl _SYSTEMD_USER_UNIT=<service>.service            # its output; -f to follow
```
