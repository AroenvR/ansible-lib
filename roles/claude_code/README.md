# aslib.infra.claude_code

An always-on Claude Code agent on RHEL 9 servers, which root reaches from a
terminal. Claude Code runs in a rootless Podman container on Red Hat's UBI 9, as
an account of its own, through [podman_service](../podman_service/README.md): if
you have root, you have the tool. Sessions, background sessions and resuming
them are Claude Code's own (`claude --help`).

Start a project, a repository of its own, from an empty directory:

```sh
mkdir claude-code && cd claude-code && git init
ansible-playbook aslib.infra.claude_setup
cd ansible && ansible-playbook build-and-deploy.yml
sudo -i                 # on the server
claude-code             # Claude, in the container; arguments go to claude
```

## The project

| File | What it is | Whose |
|---|---|---|
| `config/` | Claude Code's `/etc/claude-code/`: the policy `managed-settings.json` (below) and the instructions `CLAUDE.md` (a template). Mounted read-only, never in the image | The project's |
| `Containerfile` | UBI 9, the tools Claude needs (Python 3.12, Node.js 24 with nvm, compilers, database clients), and Claude Code from Anthropic's signed dnf repository | aslib.infra's |
| `.containerignore`, `README.md` | What stays out of the image; running it with plain Podman | aslib.infra's |
| `ansible/inventory.yml`, `ansible/group_vars/all/project.yml`, `ansible/container.env` | The servers, the settings, the container's environment (git-ignored) | The project's |
| `ansible/group_vars/all/defaults.yml` | Every setting at its default; `project.yml` wins | aslib.infra's |
| `ansible/image.yml`, `deploy.yml`, `build-and-deploy.yml`, `restart.yml`, `remove.yml`, `update-playbooks.yml` | Build, deploy, both, restart, remove, update these files | aslib.infra's |
| `ansible/templates/service.container.j2`, `ansible.cfg`, `.gitignore`, `README.md` | The Quadlet file, Ansible's settings, git rules, the guide | aslib.infra's |

As with [node_setup](../node_setup/README.md): the project's files are written
once and never touched again; aslib.infra's are brought up to date by every
setup and `update-playbooks.yml`, each changed one kept as `<file>.bak` for the
project to merge from. The image's files are aslib.infra's while it builds the
agent up, so every project gets the same tools. The project needs nothing
beforehand, and builds without aslib.infra too (its README.md shows how).

## Building

`image.yml` builds the Containerfile into `ansible/images/claude-code-<version>.tar`.
Without `claude_code_version`, the version is the newest in the repository
(`stable` by default), so every build is also the update; the image only changes
when that version or the Containerfile did. Needs Podman 3.4 or newer, Red Hat's
registry, Anthropic's repository and GitHub (nvm), or mirrors of them.

## On the server

| What | Where |
|---|---|
| The service and its account | `claude-code` (`podman_service_user`), no port |
| Its home, with Claude's login, history, memory and notes | `/opt/claude-code/`, the same path in the container; a removal keeps it |
| The policy and instructions | `/opt/claude-code/config/`, read-only in the container, where it is `/etc/claude-code/` |
| The shared zone | `/opt/containers/shared/`, with every other service of aslib.infra |
| The command | `/usr/local/sbin/claude-code`, for root: runs `claude` in the container, with a terminal or without one (`claude-code -p "..."` in a script) |

A new image, policy or `CLAUDE.md` restarts the service, which ends what runs in
it; conversations stay (`claude-code --continue`, `--resume`).

## The policy

`config/managed-settings.json` is where Claude Code reads an organisation's
policy, above every other setting. It makes Claude's home and the shared zone
its working directories; keeps it away from its login and config (`.claude/`),
`.env` files, the instruction files in its home (`CLAUDE.md`, `AGENTS.md`) and
the files that would run code at its next start (hooks, `.mcp.json`,
`.git/config`); keeps its memory in `/opt/claude-code/memory`; and turns off the
self-updater and telemetry. Claude may read the rest of the container, which
holds nothing but the read-only image: Claude Code's
`blockReadsOutsideWorkingDirectories` would only add prompts for that. The
project's README.md shows how to limit its shell commands to an allowlist of
hosts. `config/CLAUDE.md` starts from aslib.infra's template: what Claude needs
to know about this setup, for the project to adjust.

Deny rules guard Claude's tools, not every program it runs; the container and
its account are the boundary. Nothing in the container can change `config/`.

**Without permission prompts:** `ansible-playbook deploy.yml -e
claude_code_bypass_permissions=true` (or the setting in `project.yml`) installs
the policy with `permissions.defaultMode: bypassPermissions`. The deny rules
still apply. Claude Code asks once, in the first interactive session, to accept
the mode; background sessions start only after that.

## Requirements

- The Ansible machine: ansible-core; Podman 3.4 or newer to build.
- The servers: what podman_service needs (RHEL 9.2 or newer with Podman).

## Limitations

- The tests build the real image (this role's build_machine scenario), but
  deploy a stand-in for Claude Code ([molecule/mock](molecule/mock/)), next to a
  Node.js service, in [node_deploy](../node_deploy/README.md)'s scenario.
- No Podman inside the container, on purpose for now.

## Options

`ansible-doc -t role aslib.infra.claude_code` (entry points `setup`, `image`,
`main`, `restart` and `remove`); the service's settings are
[podman_service's](../podman_service/README.md#settings).
