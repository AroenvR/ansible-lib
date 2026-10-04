# aslib.infra.claude_code

An always-on Claude Code agent on RHEL 9 servers, which root enters for an
interactive session. Claude Code runs in a rootless Podman container on Red Hat's
UBI 9, as an account of its own, through [podman_service](../podman_service/README.md).
Each root user gets a tmux session of their own on the server: if you have root,
you have the tool.

Start a project, a repository of its own, from an empty directory:

```sh
mkdir claude-code && cd claude-code && git init
ansible-playbook aslib.infra.claude_setup
cd ansible && ansible-playbook build-and-deploy.yml
sudo -i                 # on the server
claude-code             # your session; detach with Ctrl-b d
```

## The project

| File | What it is | Whose |
|---|---|---|
| `Containerfile` | UBI 9, the tools Claude needs, and Claude Code from Anthropic's signed dnf repository | The project's |
| `managed-settings.json` | The policy (below), mounted read-only, never in the image | The project's |
| `.containerignore`, `README.md` | What stays out of the image; running it with plain Podman | The project's |
| `ansible/inventory.yml`, `ansible/group_vars/all/project.yml`, `ansible/container.env` | The servers, the settings, the container's environment (git-ignored) | The project's |
| `ansible/group_vars/all/defaults.yml` | Every setting at its default; `project.yml` wins | aslib.infra's |
| `ansible/image.yml`, `deploy.yml`, `build-and-deploy.yml`, `remove.yml`, `update-playbooks.yml` | Build, deploy, both, remove, update these files | aslib.infra's |
| `ansible/templates/service.container.j2`, `ansible.cfg`, `.gitignore`, `README.md` | The Quadlet file, Ansible's settings, git rules, the guide | aslib.infra's |

As with [node_setup](../node_setup/README.md): the project's files are written
once and never touched again; aslib.infra's are brought up to date by every
setup and `update-playbooks.yml`, each changed one kept as `<file>.bak`. The
project needs nothing beforehand, and builds without aslib.infra too (its
README.md shows how).

## Building

`image.yml` builds the Containerfile into `ansible/images/claude-code-<version>.tar`.
Without `claude_code_version`, the version is the newest in the repository
(`stable` by default), so every build is also the update; the image only changes
when that version or the Containerfile did. Needs Podman 3.4 or newer, Red Hat's
registry and Anthropic's repository (or mirrors).

## On the server

| What | Where |
|---|---|
| The service and its account | `claude-code` (`podman_service_user`), no port |
| Its home, with Claude's login and history | `/opt/claude-code/`, the same path in the container |
| The policy | `/opt/claude-code/config/managed-settings.json`, read-only, seen as `/etc/claude-code/` |
| The shared zone | `/opt/containers/shared/`, with every other service of aslib.infra |
| The command | `/usr/local/sbin/claude-code`, for root: `tmux new-session -A -s claude-<you>`, running `claude` in the container |

tmux runs on the server, not in the container, and is installed when missing.
A new image or policy restarts the service, which ends the running sessions; the
conversations stay (`claude-code --continue`).

## The policy

`managed-settings.json` is where Claude Code reads an organisation's policy,
above every other setting. It keeps Claude to its home and the shared zone, away
from its login and config, `.env` files and the files that would run code at its
next start (hooks, `.mcp.json`, `.git/config`), and turns off the self-updater
and telemetry. The project's README.md shows how to limit its shell commands to
an allowlist of hosts.

## Requirements

- The Ansible machine: ansible-core; Podman 3.4 or newer to build.
- The servers: what podman_service needs (RHEL 9.2 or newer with Podman), and
  tmux or a repository that has it.

## Limitations

- The real image is built only in CI: the tests deploy a stand-in for Claude Code
  ([molecule/mock](molecule/mock/)), next to a Node.js service, in
  [node_deploy](../node_deploy/README.md)'s scenario.
- Not tested: whether the UBI 9 repositories of a server's test image have tmux.

## Options

`ansible-doc -t role aslib.infra.claude_code` (entry points `setup`, `image`,
`main` and `remove`); the service's settings are podman_service's.
