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
  ([claude_code_podman](../roles/claude_code_podman/README.md#building)).
- **The server**: RHEL 9.6 or newer with its Podman, and SSH access for Ansible
  as root or as an account that may use sudo
  ([Requirements](../roles/claude_code_podman/README.md#requirements)). Claude itself
  needs `api.anthropic.com` and, to sign in, `claude.ai`, `claude.com` and
  `platform.claude.com`.
- **An account to sign in to Claude Code with**: the token that `claude
  setup-token` prints for a Pro, Max, Team or Enterprise subscription, or a
  Console API key, in `ansible/container.env` (`CLAUDE_CODE_OAUTH_TOKEN=` or
  `ANTHROPIC_API_KEY=`). Without either, the first session asks you to sign
  in, once for everyone on the server.

## Set up and deploy

In an empty directory, for a new git repository:

```sh
mkdir claude-code && cd claude-code && git init
ansible-playbook aslib.infra.claude_code_podman_setup   # writes the project
```

The project holds the `Containerfile`, `config/` (the project's part of the
policy, `managed-settings.json`, and Claude's instructions, `CLAUDE.md`) and,
in `ansible/`, the same kind of playbooks and guide as a Node.js project. Its
`ansible/README.md` goes through every step in detail ([its
template](../roles/claude_code_podman/templates/README.md.j2)); which files are the
project's and which aslib.infra's: [The
project](../roles/claude_code_podman/README.md#the-project). Before the first deploy,
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

Claude starts ready to work, in bypassPermissions mode by default: without
permission prompts, without asking to trust a folder or for its first-run
setup, and signed in with the token or key of `container.env`. Without one, the
first session asks you to sign in: the sign-in page shows a code to paste into
Claude. `claude-code -p "..."` runs Claude without a terminal, in a script. Sessions, background sessions and resuming them are Claude Code's own;
to keep a terminal around, use tmux or screen on your side.

- **How sessions start**: the `claude_code_settings_*` settings in
  `project.yml` (permission mode, model, effort, theme, agent teams,
  ultracode), then `ansible-playbook deploy.yml`. With permission prompts:
  `claude_code_settings_permission_mode: default`. The policy's deny rules
  apply in every mode ([How a session
  starts](../roles/claude_code_podman/README.md#how-a-session-starts)).
- **Changes through QA and five experts**: `claude_code_skills_qa: true` in
  `project.yml`, then `ansible-playbook deploy.yml`: a request to change a
  project then goes through the [qa
  skill](../roles/claude_code_skills/README.md#the-qa-skill-and-its-five-experts),
  which runs an architect, a tester, a reviewer, a developer and a documenter
  one at a time. Off by default, as its names win over skills and agents of
  your own.
- **Long work that keeps going**: `claude_code_skills_loop_to_delivery: true`
  in `project.yml`, then `ansible-playbook deploy.yml`: Claude then sets up a
  [loop](../roles/claude_code_skills/README.md#the-loop-to-delivery-skill) by
  itself for work that outlasts a turn, which wakes it about every 30 minutes
  until the work is delivered, a limit is reached or you stop it. Off by
  default.
- **A newer Claude Code**: every build is also the update to its newest
  version, so run `ansible-playbook build-and-deploy.yml` again.
- **The policy or the instructions**: edit `config/`, then
  `ansible-playbook deploy.yml`.
- A new image, policy, skill or `CLAUDE.md` restarts the service, which ends
  what runs in it; conversations stay (`claude-code --continue`).
- `ansible-playbook aslib.infra.overview` shows it with every other service.
  `restart.yml`, `update-playbooks.yml` and `remove.yml` work as for a Node.js
  project ([Day to day](nodejs-backend.md#day-to-day)); `remove.yml` keeps
  `/opt/claude-code/`, with the login.

## Next

- [claude_code_podman](../roles/claude_code_podman/README.md): the project, the image, what
  runs on the server, the policy, the memory limit, and its options.
- The project's own `README.md`: running the image with plain Podman, and
  limiting Claude's shell commands to an allowlist of hosts.
- [A VM for Claude Code, for development](claude-code-vm.md): where Claude may have
  root, such as for aslib.infra's own tests.
- [What runs on a server](servers.md): the shared zone and the other services.
