# aslib.infra.claude_code

The index of aslib.infra's Claude Code roles: one family, named
`claude_code_<what>`, which share their settings through one role. It runs
nothing itself (its entry point stops with this list): run one of these.

| Role | What it does | Runs on |
|---|---|---|
| [claude_code_podman](../claude_code_podman/README.md) | Claude Code as an always-on agent in a container, for root on a server, built and deployed from a project of its own; built on [podman_service](../podman_service/README.md) | Servers (RHEL 9.6, Ubuntu 24.04) and the machine that builds |
| [claude_code_vm](../claude_code_vm/README.md) | `claude-dev`, a VM where Claude Code may have root, for development | An Ubuntu host with KVM |
| [claude_code_settings](../claude_code_settings/README.md) | How a new session starts, the same in both: permission mode, model, effort, theme, agent teams, ultracode; and ready to work from the first start | Wherever the role that includes it runs |

Each target includes claude_code_settings and adds only what is its own:
where the files go, how Claude signs in, and, for the container, its own part
of the policy and the project's. Guides: [Run Claude Code on a
server](../../docs/claude-code-podman.md) and [A VM for Claude Code, for
development](../../docs/claude-code-vm.md).

A role that fits two families carries both names: claude_code_podman is a
Claude Code role and a Podman one ([Role design](../../CONTRIBUTING.md#role-design)).
