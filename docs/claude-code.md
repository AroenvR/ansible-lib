# Run Claude Code on a server

An always-on Claude Code agent on a server, which root reaches from a terminal.
It runs in a rootless Podman container on Red Hat's UBI 9, as an account of its
own: whoever has root has the tool. Claude works in its home,
`/opt/claude-code/`, and the shared zone. One command writes the project, a
repository of its own; it then builds and deploys like a [Node.js
backend](nodejs-backend.md).

## Before you start

- **The machine that runs Ansible**: ansible-core and aslib.infra ([Install
  aslib.infra](install.md)). It builds the image, so it needs Podman 4.9 or
  newer (RHEL 9.6 or Ubuntu 24.04) and access to Red Hat's registry and UBI
  repositories, Anthropic's repository and GitHub (nvm), or to mirrors of them
  ([claude_code](../roles/claude_code/README.md#building)).
- **The server**: RHEL 9.6 or newer with its Podman, and SSH access for Ansible
  as root or as an account that may use sudo
  ([Requirements](../roles/claude_code/README.md#requirements)). Claude itself
  needs `api.anthropic.com` and, to sign in, `claude.ai`, `claude.com` and
  `platform.claude.com`.
- **An account to sign in to Claude Code with.** The first session asks for it,
  once for everyone on the server.

## Set up and deploy

In an empty directory, for a new git repository:

```sh
mkdir claude-code && cd claude-code && git init
ansible-playbook aslib.infra.claude_setup   # writes the project
```

The project holds the `Containerfile`, `config/` (the project's part of the
policy, `managed-settings.json`, and Claude's instructions, `CLAUDE.md`) and,
in `ansible/`, the same kind of playbooks and guide as a Node.js project. Its
`ansible/README.md` goes through every step in detail ([its
template](../roles/claude_code/templates/README.md.j2)); which files are the
project's and which aslib.infra's: [The
project](../roles/claude_code/README.md#the-project). Before the first deploy,
look at the project's `config/managed-settings.json` and `config/CLAUDE.md`,
`ansible/inventory.yml` (this machine by default) and
`ansible/group_vars/all/project.yml`. Then:

```sh
cd ansible
ansible-playbook build-and-deploy.yml   # build the image with the newest Claude Code, deploy it
```

Add `--ask-become-pass` when sudo asks for a password. The image lands in
`images/claude-code-<version>.tar`. The deploy runs it as the service
`claude-code`, installs the command `claude-code` for root, and ends with
"Claude Code <version> runs as the service claude-code". Every run writes its
output to `logs/<playbook>-<UTC time>.log`.

## Use it

As root on the server:

```sh
sudo -i
claude-code              # Claude, in the container; arguments go to claude
claude-code --continue   # the last conversation; see claude-code --help
```

The first session asks you to sign in: the sign-in page shows a code to paste
into Claude. `claude-code -p "..."` runs Claude without a terminal, in a
script. Sessions, background sessions and resuming them are Claude Code's own;
to keep a terminal around, use tmux or screen on your side.

- **Without permission prompts**: `ansible-playbook deploy.yml -e
  claude_code_bypass_permissions=true`, or the setting in `project.yml`. The
  policy's deny rules still apply ([The
  policy](../roles/claude_code/README.md#the-policy)).
- **A newer Claude Code**: every build is also the update to its newest
  version, so run `ansible-playbook build-and-deploy.yml` again.
- **The policy or the instructions**: edit `config/`, then
  `ansible-playbook deploy.yml`.
- A new image, policy or `CLAUDE.md` restarts the service, which ends what
  runs in it; conversations stay (`claude-code --continue`).
- `ansible-playbook aslib.infra.overview` shows it with every other service.
  `restart.yml`, `update-playbooks.yml` and `remove.yml` work as for a Node.js
  project ([Day to day](nodejs-backend.md#day-to-day)); `remove.yml` keeps
  `/opt/claude-code/`, with the login.

## Next

- [claude_code](../roles/claude_code/README.md): the project, the image, what
  runs on the server, the policy, the memory limit, and its options.
- The project's own `README.md`: running the image with plain Podman, and
  limiting Claude's shell commands to an allowlist of hosts.
- [A VM for Claude Code, for development](claude-vm.md): where Claude may have
  root, such as for aslib.infra's own tests.
- [What runs on a server](servers.md): the shared zone and the other services.
