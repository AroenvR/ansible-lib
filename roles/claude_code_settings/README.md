# aslib.infra.claude_code_settings

How a new Claude Code session starts, and qa-budget, where turned on, the same
wherever aslib.infra installs Claude Code: in its container
([claude_code_podman](../claude_code_podman/README.md)) and in its VM
([claude_code_vm](../claude_code_vm/README.md)). A utility of the [Claude Code
roles](../claude_code/README.md): each target includes it and installs what it
hands over where its Claude Code reads it. It changes nothing itself.

The skills Claude Code gets, the qa skill and loop-to-delivery among them, come
from [claude_code_skills](../claude_code_skills/README.md). Up to 0.8.0 the qa
skill was this role's option `claude_code_settings_qa`, now
`claude_code_skills_qa`.

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
| `claude_code_settings_qa_budget` | `false` | [qa-budget](#qa-budget-a-budget-for-agent-work): measuring and limiting what agents spend of the subscription, on or off |

`/model`, `/effort` and `/config` still change them within a session; the next
session starts from these again. To keep the permission prompts:
`claude_code_settings_permission_mode: default`. The policy's deny rules apply
in every mode.

## qa-budget: a budget for agent work

With `claude_code_settings_qa_budget: true`, every target installs qa-budget in
`/etc/claude-code/qa-budget/` and runs it from the policy: it measures what
agents spend of the subscription and keeps agent work within a budget, so that
wake-ups, loops and expert runs never use up what the person needs. It needs
`python3` on the target.

| File | Run as | What it does |
|---|---|---|
| `statusline.py` | The status line (`statusLine`) | Shows the model and the subscription's usage, the 5-hour and the 7-day window with their resets in UTC, and saves it: `rate-limits.json` (the latest reading) and `rate-limits.jsonl` (each change) |
| `ledger.py` | Hook on `SubagentStart`, `SubagentStop` and `Stop` | Adds a line to `ledger.jsonl` per agent and session: its tokens so far (input, cache write, cache read, output, each API response once) and the usage of that moment |
| `guard.py` | Hook on `UserPromptSubmit` and `PreToolUse` | Enforces the budget, below |
| `budget.md` | Read by the qa skill (its `SKILL.md` points to it) | How QA and the experts work within the budget: plan it, deliver with a list of improvements or pause when the guard says so, report each run's tokens |

Both write in `~/.claude/qa-budget/` (`$CLAUDE_CONFIG_DIR/qa-budget/`). Only
Claude Code's status line receives the usage (`rate_limits`), hooks do not,
so the ledger reads the status line's latest reading; it lags one response.
Off by default: the managed status line replaces a person's own.

The guard tells a turn the person started from one no person started by its
prompt: every wake-up and loop prompt must begin with an `[auto ...]` tag
(`[auto qa-budget step 3] Read ...`) or hold an autonomous-loop sentinel. A
session it has seen no prompt of counts as one no person started, unless the
person typed a prompt in the last 3 hours. The status line refreshes every
minute, also while an expert runs.

| Where | A turn the person started | A turn no person started |
|---|---|---|
| The prompt, at a ceiling or the limit | Runs | Blocked, before it costs anything |
| A new expert run (Agent or Workflow tool), at a ceiling, the limit or the session's run cap | Asks the person | Denied: deliver with a list of improvements, or pause; also while the usage is unknown (no reading, or one older than 10 minutes, `QA_BUDGET_STALE_MINUTES`) |
| Any tool, at the limit | Runs (the person may go into extra usage) | Denied: pause |
| An expert's tool call, once its run used its token budget | Denied: the expert reports now | The same |

[loop-to-delivery](../claude_code_skills/README.md#how-it-stays-inside-the-budget)
needs qa-budget: its wake-ups are such automatic prompts, and its hook asks the
guard itself whether to let one through, by calling `prompt_block(moment)` in
`guard.py`, which returns why an automatic prompt is not run (a ceiling or the
limit is reached) or `None`. That function and the guard's path,
`/etc/claude-code/qa-budget/guard.py`, are an interface that
claude_code_skills relies on.

| Limit | Default | Environment variable |
|---|---|---|
| Weekly ceiling for agent work | 60% of the 7-day window | `QA_BUDGET_WEEKLY` |
| 5-hour ceiling | 90% | `QA_BUDGET_FIVE_HOUR` |
| The subscription's limit, as the guard sees it (readings lag a response) | 98% | `QA_BUDGET_LIMIT` |
| Spend-down: from this many hours before the weekly reset, while the person has been inactive for `QA_BUDGET_INACTIVE_HOURS` (3), the weekly ceiling is the limit | 4 | `QA_BUDGET_SPEND_DOWN_HOURS` |
| Expert runs per session | 12 | `QA_BUDGET_RUNS` |
| Tokens per expert run, weighted by price (input 1, cache write 1.25, cache read 0.1, output 5) | 1,500,000 | `QA_BUDGET_RUN_TOKENS` |

The person counts as active for 3 hours after a prompt they typed, and also
when the weekly usage rose by more than a point between two readings at least
30 minutes apart: someone else used the subscription meanwhile. A reading from
before a window's reset counts as 0. The defaults suit a Pro subscription; set
the variables in a settings file's `env` to change them.

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
| `claude_code_settings_files` | qa-budget's files when it is on, each its path in the managed settings directory (`name`) and its file in this role (`src`) | `/etc/claude-code/`: the container's `config/`, the VM's `/etc/claude-code/` |
| `claude_code_settings_absent` | qa-budget's folder there when it is off | Removed where an earlier run installed it (the container's `config/` holds only what the deploy lists anyway) |

The base policy also turns off Claude Code's auto-updater (each target updates
it its own way) and its telemetry, turns on workflows and keeps plans in
`./plans`.

Its deny rules follow one rule: a deny marks a change the person makes or
approves, not one Claude makes in its work. Those are Claude Code's own
controls (`settings.json` and `settings.local.json`, which hold its permissions
and hooks, the scripts in `.claude/hooks/`, and `.mcp.json`, which declares MCP
servers), the code git runs by itself (its hooks and config), and reads of
`.env` secrets. With `settings.json` editable, a hook added there would get
round the deny on hooks. A deny is not a boundary: Bash can write the same
files, and the container and the VM are the boundary. It holds for every tool,
Bash and sudo included, because the targets' instructions have Claude ask about
a denial instead of reaching the same result another way. A program keeping its
own files in its ordinary work (git recording a branch or a remote in
`.git/config`) is not such a change; changing what they run or allow is.

The policy in `/etc/claude-code/` is the one exception, with no deny. It
changes only through the playbooks that install it: claude_code_vm's runs, and,
where the person approves it, Claude applying a branch of the playbooks under
review to its own VM (aslib.infra's development VM does). A deny there would
make that approved path "another way" around the denial. In
the container, `/etc/claude-code/` is the project's `config/`, mounted
read-only, so the rule changes nothing there.

```yaml
- name: Compute Claude Code's settings
  ansible.builtin.include_role:
    name: aslib.infra.claude_code_settings

- name: Install the policy
  ansible.builtin.copy:
    content: "{{ claude_code_settings_policy | to_nice_json(indent=2) }}"
    dest: /etc/claude-code/managed-settings.json
    mode: "0644"

- name: Create the folders of the files
  ansible.builtin.file:
    path: /etc/claude-code/{{ item }}
    state: directory
    mode: "0755"
  loop: "{{ claude_code_settings_files | map(attribute='name') | map('dirname') | unique | list }}"

- name: Install the files of the features that are on
  ansible.builtin.copy:
    src: "{{ item.src }}"
    dest: /etc/claude-code/{{ item.name }}
    mode: "0644"
  loop: "{{ claude_code_settings_files }}"

- name: Remove those of the features that are off
  ansible.builtin.file:
    path: /etc/claude-code/{{ item }}
    state: absent
  loop: "{{ claude_code_settings_absent }}"
```
