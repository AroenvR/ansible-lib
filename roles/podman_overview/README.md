# aslib.infra.podman_overview

Shows root what runs on a server: every rootless Podman service in
`/etc/containers/systemd/users/<UID>/` (the convention of
[podman_service](../podman_service/README.md)), with its account, state, image
and ports, and the latest log lines of each service that does not run. It
changes nothing.

```sh
ansible-playbook aslib.infra.podman_overview                  # every server in the inventory
ansible-playbook aslib.infra.podman_overview --limit web1     # one of them
```

Run it from a directory with an inventory, such as a project's `ansible/`
directory; add `--ask-become-pass` if sudo asks for a password. The output, per
server:

```text
ok: [web1] => {
    "msg": [
        "orders-api | active (running) since Sat 2026-10-03 08:15:02 UTC, 0 restarts | localhost/orders-api:1.4.0 | ports 127.0.0.1:3000:3000 | account orders-api (UID 3001)",
        "invoices | activating (auto-restart) since Sat 2026-10-03 09:01:44 UTC, 7 restarts | localhost/invoices:2.0.1 | ports 127.0.0.1:3001:3000 | account invoices (UID 3002)",
        "    Oct 03 09:01:43 web1 invoices[2817]: Error: Cannot find module 'fs-extra'",
        "    ..."
    ]
}
```

A service that is not `active` gets its latest log lines (`podman_overview_log_lines`,
20 by default), indented below it. A service stopped by hand shows as `inactive`
or `failed`, depending on how the app ends when it is told to stop.

## Why root needs this

Each service runs as an account of its own, so `systemctl --user` and `podman ps`
show it to that account only: root's own `systemctl` and `podman` do not list it.
The overview asks each account's systemd, the way the deploy does, and reads the
Quadlet files. By hand, as root:

```sh
ls /etc/containers/systemd/users/*/                          # the services, by UID
ls /var/lib/systemd/linger/                                  # the accounts whose services start at boot
sudo systemctl --user -M <account>@ status <service>         # one service
sudo journalctl _SYSTEMD_USER_UNIT=<service>.service         # its log
```

## In a playbook

The role sets `podman_overview_services`, one dictionary per service, for
playbooks that check on services:

```yaml
- name: Check every service runs
  hosts: all
  become: true
  gather_facts: false
  tasks:
    - name: Look at the services
      ansible.builtin.import_role:
        name: aslib.infra.podman_overview

    - name: Stop when one does not run
      ansible.builtin.assert:
        that: podman_overview_services | rejectattr('state', 'equalto', 'active') | list == []
```

Each dictionary has `name`, `account`, `uid`, `state` and `substate` (systemd's
ActiveState and SubState; `unknown` and `-` when the account or its systemd is gone),
`since`, `restarts`, `image`, `ports` (a list) and `log` (a list of lines; empty
for a service that runs). All options: `ansible-doc -t role aslib.infra.podman_overview`.

## What a server needs

Nothing beyond what [podman_service](../podman_service/README.md) needs. Tested
through [node_deploy](../node_deploy/README.md)'s scenario, with a running and a
stopped service.
