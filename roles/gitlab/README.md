# aslib.infra.gitlab

GitLab Community Edition on a server of your own, as a rootless Podman service:
repositories, merge requests, forks and CI configuration for a few people and
agents, such as Claude in [claude_vm](../claude_vm/README.md)'s VM. A proof of
concept: plain HTTP, no email, no backups or runner yet.

```sh
cd ~/infra                                              # where gitlab.env is (and your inventory, if any)
ansible-playbook aslib.infra.gitlab --ask-become-pass   # then http://gitlab.home.arpa:8929, as root
```

Without an inventory it deploys to the machine it runs on; with one, to the
hosts in its group `gitlab`. It downloads GitLab's image to `images/` there
first (about 1.5 GB), unless it is there: the server itself needs no access to
Docker Hub.

## Before the first deploy

1. **Root's first password**, in `gitlab.env`, readable by you only and never in
   git: `GITLAB_ROOT_PASSWORD=<password>`. GitLab rejects one that is short (under
   8 characters), common, or contains gitlab, devops, root, admin or example (parts
   of root's name and email), and then fails to start at all; the deploy checks
   all but "common" first. GitLab uses it only when it creates its database; after
   the first sign-in, change root's password in GitLab and remove the line (the
   file stays, it may be empty).
2. **The name.** Every machine that uses GitLab must find `gitlab.home.arpa`
   (`gitlab_hostname`) at the server: a line in its `/etc/hosts`, or your
   router's DNS. In claude_vm's VM, `claude_vm_host_names` does it (below).
   `.home.arpa` is the domain meant for home networks.
3. **A fixed UID** for the account, e.g. `podman_service_uid: 3200` in your
   inventory's `group_vars`. GitLab's files belong to the account's UID and its
   subordinate UIDs (GitLab's own users inside the container). A deploy refuses
   an `/opt/gitlab` that belongs to another UID rather than take it over, and a
   deploy after a removal works on the data left behind only with the same UID and
   the same subordinate UIDs, which a server with no other new accounts in between
   gives again.
4. **Room**: about 4 GB of memory for GitLab (`gitlab_memory`), next to the VM's,
   and 15 GB of disk for the image (its archive on the Ansible machine, a copy on
   the server, the loaded image), plus GitLab's data.

## What runs where

| What | Where |
|---|---|
| The service | `gitlab`, of the account `gitlab`, rootless; its log: `sudo journalctl _SYSTEMD_USER_UNIT=gitlab.service` |
| Web and API | `http://gitlab.home.arpa:8929` (`gitlab_http_port`), on every address of the server (`gitlab_bind_address`) |
| git over SSH | port 2224 (`gitlab_ssh_port`): `ssh://git@gitlab.home.arpa:2224/<group>/<project>.git` |
| aslib.infra's settings | `/opt/gitlab/config/`: `gitlab.rb` and the settings script, read-only in the container |
| GitLab's configuration and secrets | `/opt/gitlab/etc/` (`/etc/gitlab` in the container): `gitlab-secrets.json`, the SSH host keys |
| Its data and logs | `/opt/gitlab/data/` (`/var/opt/gitlab`: database, repositories, uploads), `/opt/gitlab/logs/` |
| The image | `/opt/containers/images/gitlab/`, and `images/` on the Ansible machine |

GitLab's image runs as root inside its container, its services as users of
their own, so it gets a Quadlet file of its own
([templates/gitlab.container.j2](templates/gitlab.container.j2)) rather than
podman_service's hardened one. On the server that root is the account `gitlab`,
and GitLab's service users are its subordinate UIDs: nothing runs as the
server's root. The first start takes minutes (GitLab creates its database);
systemd counts the service as started once GitLab's own health check passes, and
restarts it after five failed checks in a row. The check waits until GitLab's
setup at the start has finished: GitLab's own check passes before that, since 19.1.

## Its settings

GitLab keeps settings in two places, and the role sets both with every deploy.

**gitlab.rb** ([templates/gitlab.rb.j2](templates/gitlab.rb.j2)), read through
`GITLAB_OMNIBUS_CONFIG` before GitLab's own `/etc/gitlab/gitlab.rb`, which stays
GitLab's template: the URL and SSH port; no email (there is no mail server);
no Service Ping or product usage data; no container registry, Pages, KAS or
monitoring; Puma in
single mode and fewer Sidekiq threads, as GitLab's guide for small servers has
it. More lines: `gitlab_config_extra`.

**Application settings**, which GitLab keeps in its database and shows in its
Admin area. The role sets these ([vars/main.yml](vars/main.yml)) once GitLab is
healthy, with `gitlab-rails runner`, so it needs no administrator's token; it
changes only what differs, and an unknown name stops the deploy. Yours, or other
values: `gitlab_application_settings`, named as in GitLab's
[settings API](https://docs.gitlab.com/api/settings/).

| Setting | The role's | Why |
|---|---|---|
| Sign-ups (`signup_enabled`) | Off | GitLab lets anyone who reaches it ask for an account; here an administrator creates them |
| Email confirmation | Off | There is no email to confirm with |
| Visibility of projects, groups, snippets | Private; only administrators may make anything public | Nothing leaks by a wrong click |
| Version check, Gravatar | Off | They call version.gitlab.com and gravatar.com |
| Product usage data | Off (also in gitlab.rb, from the first start) | GitLab sends events to events.gitlab.net, apart from Service Ping |
| Auto DevOps | Off | No pipelines for projects without a `.gitlab-ci.yml` of their own |
| Attachments, CI artifacts | 100 MB each | GitLab's own limits, written down |
| A push, an import | 1 GB each | GitLab sets no limit |

Changes in the Admin area last until the next deploy sets the role's value again;
make lasting ones with `gitlab_application_settings`.

## Accounts, without email

- **root**, the administrator: signs in with the first password, then changes it.
- **Others**: Admin area, Users, New user; then Edit to give a password, as no
  email can. The person changes it at the first sign-in.
- **Claude** (in claude_vm's VM) gets an account of its own, not an
  administrator's, with a personal access token (Edit profile, Access tokens;
  scopes `api` to work with projects and merge requests, or `read_repository` and
  `write_repository` for git only). GitLab CE lets a token live 365 days at most.
  In the VM: `git config --global credential.helper store`, then a push asks for
  the token once.
- **A forgotten password**, reset by root on the server:
  `cd / && sudo runuser -u gitlab -- env XDG_RUNTIME_DIR=/run/user/<the account's UID> podman exec -it gitlab gitlab-rake "gitlab:password:reset[<user>]"`

## From claude_vm's VM

The VM may not reach the host's services, unless they are named. With GitLab on
the host, set for the host in your inventory (or with `-e`):

```yaml
claude_vm_host_ports: [8929, 2224]
claude_vm_host_names: [gitlab.home.arpa]
```

and run `aslib.infra.claude_vm` again: the host's firewall lets the VM through to
those two ports only, and in the VM `gitlab.home.arpa` leads to the host.

## Upgrading

`gitlab_version` pins the image. To upgrade, raise it to the next of GitLab's
required stops (x.2, x.5, x.8, x.11; see
[GitLab's upgrade path tool](https://gitlab-com.gitlab.io/support/toolbox/upgrade-path/)),
one at a time, and wait until **Admin area, Monitoring, Background migrations**
shows none running before the next one. GitLab migrates its database at the
first start of a new version, which may take minutes (the service allows 30).

## Backups

Not part of the role yet. Until they are, a copy of `/opt/gitlab` holds
everything, if GitLab is stopped while it is made. It works only for the same
GitLab version, under the same UID and subordinate UIDs, so in practice on the
same server:

```sh
U=$(id -u gitlab)
cd / && sudo runuser -u gitlab -- env XDG_RUNTIME_DIR=/run/user/$U systemctl --user stop gitlab.service
sudo rsync -aHAX --numeric-ids /opt/gitlab/ <your backup>/gitlab/
cd / && sudo runuser -u gitlab -- env XDG_RUNTIME_DIR=/run/user/$U systemctl --user start gitlab.service
```

`etc/gitlab-secrets.json` is the one file nothing else replaces: without it,
GitLab cannot read the secrets in its database (CI variables, two-factor
settings). Keep it with the backup, away from anyone who should not have it.

## Requirements

- The server: what podman_service needs (RHEL 9.6 or newer with its Podman),
  x86_64 or arm64, with the memory and disk above.
- The Ansible machine: Podman 4.9 or newer and Docker Hub, to download the
  image; or the archive copied into `images/` (`gitlab-ce-<version>.tar`).

## Limitations

- A proof of concept: one GitLab per server, named `gitlab`.
- Plain HTTP: passwords and tokens cross the network unencrypted. Keep it on a
  network you trust.
- No email, container registry or Pages; no backups or runner yet.
- Tested in CI with GitLab 19.4.1 on the RHEL 9 test server; not yet on a laptop.

## Options

`ansible-doc -t role aslib.infra.gitlab` (entry points `main`, `image` and
`remove`).
