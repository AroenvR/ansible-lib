# Reference

What aslib.infra holds: its roles, ready-made playbooks and plugins. Each role's
README is that role's reference; the [guides](README.md#guides) walk through a
job from start to end.

## Roles

| Role | Purpose | Runs on | Needs network access |
|---|---|---|---|
| [sudoers](../roles/sudoers/README.md) | sudo rules as validated drop-in files | Servers | Only if sudo is missing |
| [node_setup](../roles/node_setup/README.md) | Prepares a Node.js project: its `ansible/` directory with settings, inventory, playbooks and guide | The project's machine | No |
| [node_image](../roles/node_image/README.md) | Production container image of a Node.js project, and its node_modules for development, built in containers | The build machine | Yes, from sources you choose |
| [node_deploy](../roles/node_deploy/README.md) | Runs that image as a rootless Podman service that starts at boot, with podman_service | Servers (RHEL 9.6+) | Only if the `acl` package is missing |
| [podman_service](../roles/podman_service/README.md) | Runs any image archive as a rootless Podman service that starts at boot | Servers (RHEL 9.6+) | Only if the `acl` package is missing |
| [podman_overview](../roles/podman_overview/README.md) | Shows root the rootless Podman services on a server, with how to read their logs | Servers (RHEL 9.6+) | No |
| [claude_code](../roles/claude_code/README.md) | The index of the Claude Code roles below; runs nothing | - | No |
| [claude_code_podman](../roles/claude_code_podman/README.md) | Writes a Claude Code project, builds its image, deploys it as an always-on service with podman_service, and the `claude-code` command for root | The project's machine, the build machine, servers (RHEL 9.6+) | To build: Red Hat's registry and UBI repositories, Anthropic's repository and GitHub (nvm). To deploy: only if acl is missing |
| [claude_code_vm](../roles/claude_code_vm/README.md) | A VM for Claude Code with sudo, on a host with KVM, kept away from the local network (proof of concept) | Hosts with KVM (Ubuntu 24.04+), with ansible-core 2.16+ | Yes: packages, Ubuntu's cloud image, Anthropic's and the deadsnakes repositories |
| [claude_code_settings](../roles/claude_code_settings/README.md) | How a Claude Code session starts (permission mode, model, effort, theme, agent teams, ultracode) and the qa skill with its five experts (off by default), the same in the container and the VM, which both include it | Wherever the role that includes it runs | No |
| [gitlab](../roles/gitlab/README.md) | GitLab Community Edition as a rootless Podman service, with podman_service, set up for a private instance without email (proof of concept) | Servers (RHEL 9.6+) | The Ansible machine: Docker Hub or a mirror (`gitlab_image`), for the image. The server: no |

Each role's options: [Role options](#role-options).

## Ready-made playbooks

For people who don't write Ansible: run these by name, no playbook of your own
needed. The playbooks node_setup writes import them.

| Playbook | Run it from | What it does |
|---|---|---|
| `ansible-playbook aslib.infra.node_setup` | The project's root | Writes `ansible/` into the Node.js project, see [node_setup](../roles/node_setup/README.md) |
| `ansible-playbook aslib.infra.node_update` | `ansible/` | Brings aslib.infra's files in `ansible/` up to date, the same as node_setup |
| `ansible-playbook aslib.infra.node_prebuild` | `ansible/` | Prepares the project for development: node_modules from a throwaway container, see [node_image](../roles/node_image/README.md#node_modules-for-development) |
| `ansible-playbook aslib.infra.node_image` | `ansible/` | Builds the project into an image archive, see [node_image](../roles/node_image/README.md) |
| `ansible-playbook aslib.infra.node_deploy` | `ansible/` | Deploys that image to the servers, or a newer version over the old one, see [node_deploy](../roles/node_deploy/README.md) |
| `ansible-playbook aslib.infra.node_restart` | `ansible/` | Restarts the service on the servers and waits until it answers, see [node_deploy](../roles/node_deploy/README.md) |
| `ansible-playbook aslib.infra.node_remove` | `ansible/` | Removes the service from the servers, keeping its directory unless asked, see [node_deploy](../roles/node_deploy/README.md#remove-a-service) |
| `ansible-playbook aslib.infra.overview` | A server itself, or any directory with an inventory, such as `ansible/` | Shows what aslib.infra runs on that server, or on the inventory's servers, each with the command that shows its log |
| `ansible-playbook aslib.infra.podman_overview` | The same | Shows only the rootless Podman services, see [podman_overview](../roles/podman_overview/README.md) |
| `ansible-playbook aslib.infra.claude_code_podman_setup` | An empty directory, or the root of an earlier setup | Writes a Claude Code project; its `ansible/` holds every other playbook it needs, see [claude_code_podman](../roles/claude_code_podman/README.md) |
| `ansible-playbook aslib.infra.claude_code_vm` | A host with KVM, or a directory with it in an inventory | Creates `claude-dev`, a VM where Claude Code has sudo, away from the local network, see [claude_code_vm](../roles/claude_code_vm/README.md) |
| `ansible-playbook aslib.infra.claude_code_vm_remove` | The same | Removes that VM, for a fresh one |
| `ansible-playbook aslib.infra.claude_code_vm_overview` | The same | Shows the host and the VM, for finding out why the VM does not come up; changes nothing |
| `ansible-playbook aslib.infra.claude_code_vm_boot_trial` | The same | Boots the VM once in a changed form (other firmware, no TPM, no CD drive) and shows how far it got, see [claude_code_vm](../roles/claude_code_vm/README.md#when-the-vm-does-not-come-up) |
| `ansible-playbook aslib.infra.gitlab` | The directory with `gitlab.env`, and an inventory with a group `gitlab` if GitLab goes elsewhere | Deploys GitLab CE, see [gitlab](../roles/gitlab/README.md) |
| `ansible-playbook aslib.infra.gitlab_remove` | The same | Removes GitLab's service, keeping its data in `/opt/gitlab` |

## Plugins

| Plugin | What it does |
|---|---|
| `aslib.infra.run_log` (callback) | Writes each playbook run to a file of its own, `logs/<playbook>-<UTC time>.log`. The `ansible.cfg` that node_setup and claude_code_podman_setup write enables it: `callbacks_enabled = aslib.infra.run_log`. Options: `ansible-doc -t callback aslib.infra.run_log` |

## Role options

Every role documents its variables in its `meta/argument_specs.yml`, for each
of its entry points (`main`, and others such as `remove`), with the same
defaults as its `defaults/main.yml`. Read them offline with
`ansible-doc -t role aslib.infra.<role>`. Each option is described once, by the
role that owns it (podman_service for every service's settings): in its
`meta/argument_specs.yml`, and in its README where a reader needs more. Where
each README covers its options:

| Role | Where its README covers its options |
|---|---|
| sudoers | [Interface](../roles/sudoers/README.md#interface), and an [example](../roles/sudoers/README.md#example) |
| node_setup | [Options](../roles/node_setup/README.md#options) |
| node_image | [Options](../roles/node_image/README.md#options), [Download sources](../roles/node_image/README.md#download-sources) |
| node_deploy | [Settings](../roles/node_deploy/README.md#settings); the service's settings are podman_service's |
| podman_service | [Settings](../roles/podman_service/README.md#settings), those of every service: its port, directory, account and more |
| podman_overview | [In a playbook](../roles/podman_overview/README.md#in-a-playbook) |
| claude_code_podman | [Options](../roles/claude_code_podman/README.md#options); the service's settings are podman_service's |
| claude_code_vm | [Settings](../roles/claude_code_vm/README.md#settings), [Options](../roles/claude_code_vm/README.md#options) |
| claude_code_settings | [Settings](../roles/claude_code_settings/README.md#settings), for both claude_code_podman and claude_code_vm |
| gitlab | [Its settings](../roles/gitlab/README.md#its-settings), [Options](../roles/gitlab/README.md#options) |
