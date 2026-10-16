# What runs on a server

For root on a server that aslib.infra deploys to: how to see what runs there,
where its files are, and what the server needs.

## See what runs

Every service runs rootless as an account of its own, so root's `systemctl` and
`podman` do not list it. `aslib.infra.overview` shows root everything
aslib.infra runs: every such service
([podman_overview](../roles/podman_overview/README.md)), with its account,
state, image, ports and the command that shows its log, and the latest log
lines of each one that does not run. On a server itself, without an inventory,
it shows that server; from a directory with an inventory, every server in it:

```sh
ansible-playbook aslib.infra.overview
```

It changes nothing. podman_overview's README shows its output, the options
(one server, a password for sudo), and how to look by hand as root ([Why root
needs this](../roles/podman_overview/README.md#why-root-needs-this)). One
service's status and log: [Check a
service](../roles/podman_service/README.md#check-a-service).

## Conventions

On the servers every deploy follows the same fixed conventions:

- an account per service, named after it, whose services start at boot;
- image archives in `/opt/containers/images/<service>/`;
- Quadlet files in `/etc/containers/systemd/users/<UID>/`, the account's UID;
- the service's own directory, its working directory, in `/opt/<service>/`;
- the shared zone, `/opt/containers/shared/`, which every service reads and
  writes, unless it is left out of it (GitLab is).

[podman_service](../roles/podman_service/README.md#conventions) does the work
on the servers and describes each step;
[node_deploy](../roles/node_deploy/README.md),
[claude_code](../roles/claude_code/README.md) and
[gitlab](../roles/gitlab/README.md) deploy through it.

## What a managed server needs

Every role assumes a default server install. Nothing else is required unless a
role's README says so.

- Python 3, plus `python3-apt` on Ubuntu. Both are part of a default install.
- SSH access for Ansible, as root or as an account that may use sudo; none
  when Ansible runs on the server itself.
- No internet access. A role that needs package repositories says so in its
  README, and names the step that needs them. Repository and download URLs are
  always role variables, so they can point at your mirror or proxy.

Which systems, and which need Podman: [Compatibility](install.md#compatibility).
