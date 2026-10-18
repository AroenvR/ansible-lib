# aslib.infra.claude_code_settings

How a new Claude Code session starts, the same wherever aslib.infra installs
Claude Code: in its container ([claude_code_podman](../claude_code_podman/README.md))
and in its VM ([claude_code_vm](../claude_code_vm/README.md)). A utility of the
[Claude Code roles](../claude_code/README.md): each target includes it and
installs what it hands over where its Claude Code reads it. It changes nothing
itself.

## Settings

The same names and defaults in every target. Options and their choices:
`ansible-doc -t role aslib.infra.claude_code_settings`.

| Variable | Default | A new session starts with |
|---|---|---|
| `claude_code_settings_permission_mode` | `bypassPermissions` | this permission mode |
| `claude_code_settings_model` | `opus` | this model (`opus`: the newest Opus) |
| `claude_code_settings_effort` | `xhigh` | this effort level |
| `claude_code_settings_theme` | `dark` | this theme |
| `claude_code_settings_agent_teams` | `false` | agent teams on or off |
| `claude_code_settings_ultracode` | `false` | ultracode on or off |

`/model`, `/effort` and `/config` still change them within a session; the next
session starts from these again. To keep the permission prompts:
`claude_code_settings_permission_mode: default`. The policy's deny rules apply
in every mode.

## Ready to work from the start, in every target

Whatever the settings say:

- **bypassPermissions mode starts without its confirmation**, in interactive
  and background sessions (`skipDangerousModePermissionPrompt`).
- **No folder asks to be trusted**: not the home directory, nor any folder
  under it, git repositories cloned later included, nor the container's shared
  zone. Claude Code asks so before it lets a folder's own settings act; in the
  container and the VM, the target itself is the boundary. The target sets
  `CLAUDE_CODE_SANDBOXED=1` in the environment of every `claude` it starts:
  Claude Code checks it before it reads any settings file, so the policy's
  `env` cannot. Claude Code does not document this variable; the VM's test
  starts the real Claude Code in a new git repository to prove it still works.
- **No first-run setup**: the target writes Claude Code's `.claude.json` with
  `hasCompletedOnboarding: true` for an account that has none yet, as the
  policy already chose the theme. Sign-in comes from each target's own secret
  channel: the container's `container.env`, the VM's `claude_code_vm_oauth_token`.
- **A `cd` sticks**: every directory is a working directory
  (`permissions.additionalDirectories: ["/"]`), so after `cd` to any directory,
  later Bash commands run there. Claude also reads any file without a prompt;
  edits follow the permission mode.

## What it hands over

Facts, for the role that includes it:

| Fact | What | Where the targets put it |
|---|---|---|
| `claude_code_settings_policy` | The base of Claude Code's policy, [templates/managed-settings.json.j2](templates/managed-settings.json.j2) with the settings' values | `/etc/claude-code/managed-settings.json`; the container adds its own part and the project's |
| `claude_code_settings_environment` | Environment variables every `claude` process needs | The VM's `claude` command; the container's `claude-code` command |
| `claude_code_settings_global_config` | Claude Code's `.claude.json` for an account without one | The account's home, written only where missing |

The base policy also turns off Claude Code's auto-updater (each target updates
it its own way) and its telemetry, turns on workflows, keeps plans in
`./plans`, and denies edits to the policy itself, to settings and hooks that
would run code, and reads of `.env` files.

```yaml
- name: Compute Claude Code's settings
  ansible.builtin.include_role:
    name: aslib.infra.claude_code_settings

- name: Install the policy
  ansible.builtin.copy:
    content: "{{ claude_code_settings_policy | to_nice_json(indent=2) }}"
    dest: /etc/claude-code/managed-settings.json
    mode: "0644"
```
