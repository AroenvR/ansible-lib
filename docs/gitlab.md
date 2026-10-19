# Run a GitLab of your own

GitLab Community Edition as a rootless Podman service, on the host of [the VM
for Claude Code](claude-code-vm.md) or any server: repositories, merge requests,
forks and CI configuration for a few people and agents, such as Claude in that
VM. A proof of concept: plain HTTP, no email, no backups or runner yet.

## Before you start

- **The server**: RHEL 9.6 or newer with its Podman, x86_64 or arm64
  ([podman_service](../roles/podman_service/README.md#what-a-server-needs));
  it needs no access to Docker Hub. For Claude in claude_code_vm's VM, put it on the
  VM's host, whose ports you name are all of the local network the VM reaches;
  that host then has to be such a server too, as Ubuntu 24.04's Podman (4.9) is
  too old for the service.
- **The machine that runs Ansible**, the server itself or another one:
  ansible-core and aslib.infra ([Install aslib.infra](install.md)), and Podman
  4.9 or newer with access to Docker Hub or a mirror of it (`gitlab_image`), to
  download GitLab's image (about 1.5 GB). Without that access, copy the archive into `images/` there
  (`gitlab-ce-<version>.tar`).
- **A directory** on that machine for `gitlab.env` and your inventory, if any,
  such as `~/infra`. Without an inventory, or without a group `gitlab` in it,
  GitLab goes to the machine the playbook runs on; otherwise to the hosts in
  that group.
- **The four steps of [Before the first
  deploy](../roles/gitlab/README.md#before-the-first-deploy)**: root's first
  password in `gitlab.env`, the name `gitlab.home.arpa` on every machine that
  uses GitLab, a fixed UID for the account, and room (about 4 GB of memory and
  15 GB of disk, plus GitLab's data).

## Deploy it

On the machine that runs Ansible; `gitlab.env` stays out of git:

```sh
mkdir -p ~/infra && cd ~/infra
(umask 077 && touch gitlab.env)                         # readable by you only; add GITLAB_ROOT_PASSWORD=<password>
ansible-playbook aslib.infra.gitlab --ask-become-pass   # then http://gitlab.home.arpa:8929, as root
```

The deploy checks root's first password and GitLab's directory first, then
downloads the image to `images/` unless the archive is there. The first start
takes minutes, while GitLab creates its database. The deploy ends with "GitLab
<version> runs at http://gitlab.home.arpa:8929 (SSH on port 2224)". Then:

1. Sign in at `http://gitlab.home.arpa:8929` as root, with the first password.
   Change root's password in GitLab, and remove the line from `gitlab.env`
   (the file stays; it may be empty).
2. Create the other accounts in the Admin area, with a password each, as no
   email can: [Accounts, without
   email](../roles/gitlab/README.md#accounts-without-email).
   Claude gets an account of its own with a personal access token, never an
   administrator's.
3. git over SSH uses port 2224:
   `ssh://git@gitlab.home.arpa:2224/<group>/<project>.git`.

What runs where on the server, and GitLab's log: [What runs
where](../roles/gitlab/README.md#what-runs-where). `ansible-playbook
aslib.infra.overview` shows it with every other service.

## Next

- [From claude_code_vm's VM](../roles/gitlab/README.md#from-claude_vms-vm): let
  Claude in the VM reach GitLab on the VM's host.
- [Its settings](../roles/gitlab/README.md#its-settings): what the deploy sets
  in `gitlab.rb` and in GitLab's application settings, and why.
- [Upgrading](../roles/gitlab/README.md#upgrading), one required stop at a time,
  and [Backups](../roles/gitlab/README.md#backups), by hand until the role makes
  them.
- To remove it, keeping its data in `/opt/gitlab` for a later deploy:
  `ansible-playbook aslib.infra.gitlab_remove --ask-become-pass`.
- [Limitations](../roles/gitlab/README.md#limitations): plain HTTP sends
  passwords and tokens unencrypted, so keep it on a network you trust.
- [gitlab](../roles/gitlab/README.md): everything else, and its options.
