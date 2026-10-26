# aslib.infra.claude_code_podman

An always-on Claude Code agent on RHEL 9 servers, which root reaches from a
terminal. Claude Code runs in a rootless Podman container on Red Hat's UBI 9, as
an account of its own, through [podman_service](../podman_service/README.md): if
you have root, you have the tool. Sessions, background sessions and resuming
them are Claude Code's own (`claude --help`).

Start a project, a repository of its own, from an empty directory:

```sh
mkdir claude-code && cd claude-code && git init
ansible-playbook aslib.infra.claude_code_podman_setup
cd ansible && ansible-playbook build-and-deploy.yml
sudo -i                 # on the server
claude-code             # Claude, in the container; arguments go to claude
```

## The project

| File | What it is | Whose |
|---|---|---|
| `config/` | Claude Code's `/etc/claude-code/`: the project's part of the policy `managed-settings.json` (below) and the instructions `CLAUDE.md` (a template). Its top-level files go to the server, mounted read-only, never in the image | The project's |
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
Without `claude_code_podman_version`, the version is the newest in the repository
(`stable` by default), so every build is also the update; the image only changes
when that version, the base image or the Containerfile did. A new image also has
every package update of its day (`dnf upgrade`), so a pinned version also pins
the packages, until the base image changes. Needs Podman 4.9 or newer, Red Hat's
registry and UBI repositories, Anthropic's repository and GitHub (nvm), or
mirrors of them (`claude_code_podman_base_image` or `registries.conf`,
`claude_code_podman_rpm_repos`, `claude_code_podman_repository`, `claude_code_podman_nvm_url`: the
project guide's "Download sources"). The base image must provide
`/usr/bin/python3` (UBI 9 does; the Containerfile adds Python 3.12 as
`python3.12` and leaves `python3` alone), as the hook of
[loop-to-delivery](../claude_code_skills/README.md#the-loop-to-delivery-skill)
runs with it.

## On the server

| What | Where |
|---|---|
| The service and its account | `claude-code` (`podman_service_user`), no port |
| Its home, with Claude's login, history, memory and notes | `/opt/claude-code/`, the same path in the container; a removal keeps it |
| The policy and instructions | `/opt/claude-code/config/`, read-only in the container, where it is `/etc/claude-code/`; with `claude_code_settings_qa`, also the qa skill and its experts, and with `claude_code_skills_loop_to_delivery` the loop-to-delivery skill, in `.claude/` |
| The shared zone | `/opt/containers/shared/`, with every other service of aslib.infra that has it (`podman_service_shared`) |
| The command | `/usr/local/sbin/claude-code`, for root: runs `claude` in the container, with a terminal or without one (`claude-code -p "..."` in a script) |

A new image, policy, `CLAUDE.md` or skill restarts the service, which ends what runs in
it; conversations stay (`claude-code --continue`, `--resume`). It has no health
check: nothing in it serves until root runs `claude-code`, so a running
container is all there is to check.

The container may use at most 4 GiB of memory (`claude_code_podman_memory: 4g`), so a
runaway build in a session cannot starve the server; past it, the kernel stops a
process in the container. Set another size in `project.yml`, or `""` for no limit.

## The policy

Claude Code reads an organisation's policy, above every other setting, from
`/etc/claude-code/managed-settings.json`. Every deploy assembles it from these,
in this order:

| File | Whose | What |
|---|---|---|
| [claude_code_settings](../claude_code_settings/README.md)'s base | aslib.infra's, the same for every project and for [claude_code_vm](../claude_code_vm/README.md)'s VM | How a session starts (the `claude_code_settings_*` settings, below), ready to work; the self-updater and telemetry off, workflows on, plans in `plans/`, every directory a working directory; keeps Claude away from `.env` files and the files that would run code at its next start (hooks, `.mcp.json`, `.git/config`) |
| [claude_code_skills](../claude_code_skills/README.md)'s part | aslib.infra's, the same for the VM | loop-to-delivery's hooks, after qa-budget's, while `claude_code_skills_loop_to_delivery` is on; nothing otherwise |
| [files/managed-settings.container.json](files/managed-settings.container.json) | aslib.infra's, for the container | Claude's memory in `/opt/claude-code/memory`; keeps it away from its login and config (`.claude/`) and the instruction files in its home (`CLAUDE.md`, `AGENTS.md`) |
| `config/managed-settings.json` | The project's, `{}` to start | What this project adds or changes |

A later value replaces an earlier one, blocks such as `env` merge key by key,
and lists such as `permissions.deny` combine without duplicates, as Claude Code
combines its own drop-in files: a project adds deny rules, it cannot drop the
base's. A change to the base reaches every project with its next deploy, and the
VM with its next run. Projects set up before 0.5.0 hold a full copy of the old
policy, which merges to the same result; they may trim it to what is theirs.

Claude may read the rest of the container, which holds nothing but the
read-only image: Claude Code's `blockReadsOutsideWorkingDirectories` would only
add prompts for that. The project's README.md shows how to limit its shell
commands to an allowlist of hosts. `config/CLAUDE.md` starts from aslib.infra's
template: what Claude needs to know about this setup, for the project to adjust.

Deny rules guard Claude's tools, not every program it runs; the container and
its account are the boundary. Nothing in the container can change `config/`.

## How a session starts

The same settings as in claude_code_vm's VM, with the same names and defaults
([claude_code_settings](../claude_code_settings/README.md)), in `project.yml`
or with `-e`; each deploy installs them:

| Setting | Default |
|---|---|
| `claude_code_settings_permission_mode` | `bypassPermissions`: without permission prompts; `default` keeps them |
| `claude_code_settings_model` | `opus`, the newest Opus |
| `claude_code_settings_effort` | `xhigh` |
| `claude_code_settings_theme` | `dark` |
| `claude_code_settings_agent_teams` | `false` |
| `claude_code_settings_ultracode` | `false` |
| `claude_code_settings_qa` | `false`; `true` installs the [qa skill and its five experts](../claude_code_settings/README.md#the-qa-skill-and-its-five-experts) |
| `claude_code_settings_qa_budget` | `false`: [qa-budget](../claude_code_settings/README.md#qa-budget-a-budget-for-agent-work), which measures and limits what agents spend of the subscription |

**Skills:** the same names and defaults as in the VM
([claude_code_skills](../claude_code_skills/README.md)), set the same way, each
deploy installing them in `config/.claude/`, which the container reads as
`/etc/claude-code/.claude/`:

| Setting | Default |
|---|---|
| `claude_code_skills_loop_to_delivery` | `false`; `true` installs [loop-to-delivery](../claude_code_skills/README.md#the-loop-to-delivery-skill), which keeps long work going until it is delivered, and its hooks. Needs `claude_code_settings_qa_budget: true`: a deploy with the loop on and qa-budget off stops, naming both |
| `claude_code_skills_loop_to_delivery_max_wakes` | `5`, the most wake-ups a loop gets |
| `claude_code_skills_loop_to_delivery_max_hours` | `24`, the most hours a loop runs (1 to 168) |

Whatever they say, Claude Code starts ready to work: bypassPermissions mode
needs no confirmation, no folder asks to be trusted (Claude's home, any
folder in it, repositories cloned there later, the shared zone), the
first-run setup is done (the deploy gives Claude Code's configuration
directory a `.claude.json` that says so, once), and a `cd` sticks for later
commands. The deny rules apply in every mode. The `claude-code` command passes
`CLAUDE_CODE_SANDBOXED=1` on to Claude Code, which reads it before any
settings file.

**Signing in:** put one of these in `ansible/container.env`, whose template
names both: `CLAUDE_CODE_OAUTH_TOKEN=`, the one-year token that `claude
setup-token` prints for a Pro, Max, Team or Enterprise subscription, or
`ANTHROPIC_API_KEY=`, a Console API key. If both are set, the API key wins.
With neither, Claude signs in with a claude.ai account in its first session.

**From before 0.7.0** (when this role was `claude_code`): a deploy, build,
restart or removal that still sets a setting by its old name stops, naming the
new one; `claude_code_bypass_permissions` is gone, as bypassPermissions is
the default now.

## Requirements

- The Ansible machine: ansible-core; Podman 4.9 or newer to build.
- The servers: what podman_service needs (RHEL 9.6 or newer with its Podman).

## Limitations

- The tests build the real image (this role's build_machine scenario), but
  deploy a stand-in for Claude Code ([molecule/mock](molecule/mock/)), next to a
  Node.js service, in [node_deploy](../node_deploy/README.md)'s scenario.
- No Podman inside the container, on purpose for now.

## Options

`ansible-doc -t role aslib.infra.claude_code_podman` (entry points `setup`, `image`,
`main`, `restart` and `remove`); the service's settings are
[podman_service's](../podman_service/README.md#settings).
