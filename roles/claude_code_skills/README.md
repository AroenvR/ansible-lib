# aslib.infra.claude_code_skills

The skills Claude Code gets, both off by default, the same wherever
aslib.infra installs Claude Code: in its container
([claude_code_podman](../claude_code_podman/README.md)) and in its VM
([claude_code_vm](../claude_code_vm/README.md)): the
[qa skill](#the-qa-skill-and-its-five-experts) with the five expert subagents
it runs, and [loop-to-delivery](#the-loop-to-delivery-skill). A utility of the
[Claude Code roles](../claude_code/README.md): each target includes it after
[claude_code_settings](../claude_code_settings/README.md) and installs what it
hands over where its Claude Code reads it. It changes nothing itself.

## Settings

The same names and defaults in every target. Options and their choices:
`ansible-doc -t role aslib.infra.claude_code_skills`.

| Variable | Default | What |
|---|---|---|
| `claude_code_skills_qa` | `false` | The [qa skill and its five experts](#the-qa-skill-and-its-five-experts) on or off. Needs `claude_code_settings_agent_teams` off |
| `claude_code_skills_loop_to_delivery` | `false` | The [loop-to-delivery skill](#the-loop-to-delivery-skill), its program and its hooks on or off. Needs `claude_code_settings_qa_budget: true` |
| `claude_code_skills_loop_to_delivery_max_wakes` | `5` | The most wake-ups a loop gets; a whole number above 0 |
| `claude_code_skills_loop_to_delivery_max_hours` | `24` | The most hours a loop runs, from its start; a whole number from 1 to 168 (a recurring job expires after 7 days) |

The defaults are small on purpose: a handful of wake-ups and a day. Raise them
once you have seen the budget hold on your subscription.

Managed skills and subagents win over a person's and a project's with the same
name, so turning one on hides those. Turning it off again removes its files (and
the loop's hooks) at the next run or deploy.

Up to 0.8.0 the qa skill was `claude_code_settings_qa`, an option of
claude_code_settings. A run, build or deploy of the VM or the container that
still sets it stops, naming `claude_code_skills_qa`
([upgrading from 0.8.0](../../CHANGELOG.md#upgrading-from-080)). This role
itself ignores the old name: the stops are in the targets.

A run or deploy with `claude_code_skills_loop_to_delivery: true` while
`claude_code_settings_qa_budget` is off stops, naming both settings
([why](#how-it-stays-inside-the-budget)). With the loop off, qa-budget is not
needed.

## The qa skill and its five experts

With `claude_code_skills_qa: true`, every target installs a skill and five
subagents in Claude Code's managed settings directory, `/etc/claude-code/`:

| File | What |
|---|---|
| `.claude/skills/qa/SKILL.md` | The skill `qa`: the session you talk to becomes QA, the lead |
| `.claude/skills/qa/protocol.md` | The protocol QA and every expert follow: roles, ownership, artifacts, the four review gates, the handoff, when to stop |
| `.claude/agents/architect.md` | Technical architecture and contracts |
| `.claude/agents/tester.md` | Tests and their RED |
| `.claude/agents/reviewer.md` | The gates' verdicts; never edits what it reviews. Runs on Sonnet |
| `.claude/agents/developer.md` | Production code, GREEN and REFACTOR |
| `.claude/agents/documenter.md` | Docs and code comments. Runs on Sonnet |

Its description has Claude take the skill for any request to change a
project, without being told; a question is answered without it, and `/qa`
starts it by hand. The architect, the tester and the developer run on the
session's model, the reviewer and the documenter on Sonnet. QA writes the spec and the acceptance, and runs the experts
one at a time, passing each one's report on to the next, in the protocol's
order: spec, architect, review of the architecture, tester (RED), review of the
tests, developer (GREEN), review of the code, documenter, final review,
acceptance. A small change takes only the experts it needs (documentation
only: the documenter and the final review; a test only: the tester and its
review). Each gate takes one review round:
only a serious finding sends work back to the expert who owns it, and the rest
goes to the list of improvements that comes with the delivery; after three
BLOCKs in a row at the same gate, QA stops and asks. QA writes no production
code, tests or docs itself, apart from corrections that change no behavior and
that it proves mechanically (a version number replaced everywhere, whitespace,
a label removed from a comment, a merge of reviewed work); the next review
checks them. Each expert writes only the paths QA gives it, reading only the
files and sections its brief names, so that each run fits its token budget.

When the person brainstorms (ideas or problems for later, not a request to do
the work now), QA changes nothing: it files each idea as an issue in the
project's tracker, one per change, and starts work only when asked.

QA works so that the person can leave the work with it. It decides what the
project's own rules decide (the version number, who fixes a finding, re-running
an expert within the budget) and lists those decisions in its report; it asks
only what is the person's to decide, in one batch while it writes the spec,
each question with its recommendation. Its messages and pull requests use
plain words, not the team's labels; nothing the project keeps (code, comments,
tests, docs, changelogs, commits) carries a label from the spec or the number
of the upcoming release, which only the version file and the changelog's
heading hold. It runs the tests that only CI can run as soon as they exist, so
their defects surface before the reviews. The artifacts go in
`.claude/specs/<change-id>/` in the project; whether it commits them is the
project's choice. Git, branches and releases stay under the project's own
rules. With loop-to-delivery on as well, QA starts a loop for the change
request before the first expert runs. With
[qa-budget](../claude_code_settings/README.md#qa-budget-a-budget-for-agent-work)
on, QA reads its `budget.md` before the first expert run and works within it.

Claude Code protects a project's `.claude/` folder: in bypassPermissions mode
(the default) QA and the experts write their artifacts there freely; in
`default` and `acceptEdits` mode Claude Code asks first (its prompt can allow it
for the session), and in `dontAsk` mode it refuses.

The qa skill needs agent teams off (`claude_code_settings_agent_teams: false`,
the default): with agent teams on, Claude starts a subagent it names as a
teammate instead, and the run stops when both are on.

## The loop-to-delivery skill

For work that outlasts a turn, such as a change request, or waiting on CI, a
review or an answer. Without being asked, Claude sets up a loop as soon as it
sees such work, and the loop keeps the work going across interruptions (a rate
or credit limit, a closed laptop) until it is delivered or a limit ends it. It
is generic: it knows nothing about a forge, a project or a branch flow.
"Delivered" is what the work's own definition of done says, which Claude writes
down first.

### How it works

A loop has three parts:

- **Notes** that Claude writes to a file of its own choosing, with the goal, the
  definition of done, what is done, the next step and what it waits on. Every
  wake-up continues from them.
- **A wake-up job**, a session-only job that prompts the conversation at :07 and
  :37 of every hour while it is idle. Its prompt starts with
  `[auto loop-to-delivery <id>]`, which names the loop.
- **Hooks** in the policy (`UserPromptSubmit`, `Stop` and `StopFailure`), which
  run the skill's program, `loop_to_delivery.py`. They let a wake-up through
  only for the conversation that started the loop and within its limits, and
  block it otherwise before it costs a model call. At the end of a turn they
  ask Claude to go on while its notes moved (at most 20 times in a turn), and
  to create the job if it forgot. A person's own prompts are never blocked.

Progress is a change to the notes, or to the folders that Claude asked the loop
to watch (the repository, a folder of artifacts). A wake-up that can only wait
ends its turn without writing anything, so that the idle limit can work.

### How it stays inside the budget

A loop runs without a person, so it must never use up what the person needs of
the subscription. Four things keep it inside:

- **qa-budget is required.** The loop is only as safe as the guard of
  [qa-budget](../claude_code_settings/README.md#qa-budget-a-budget-for-agent-work),
  so a run with the loop on and `claude_code_settings_qa_budget` off stops,
  naming both settings.
- **A wake-up is an automatic prompt.** Its `[auto loop-to-delivery <id>]` tag
  is what the guard recognises as a turn no person started. The guard blocks
  such a prompt at the weekly and the 5-hour ceilings (60% and 90% by default)
  and at the subscription's limit, before it costs anything, so a wake-up never
  runs into extra usage. A person's own prompt in the loop's conversation is
  not blocked.
- **A block by the guard ends the loop.** Claude Code runs the hooks of one
  event side by side, so the loop's hook cannot see what the guard decides on
  the same prompt. It asks the guard itself when a wake-up arrives (the guard's
  `prompt_block` function). If the guard says no, the loop ends in that very
  hook call and stays ended: a later wake-up is blocked as well, also after the
  usage has dropped below the ceiling, and Claude is told why at the next prompt a
  person starts in that conversation. With no usage reading at all, a wake-up
  passes, as for the guard itself; a reading counts however old it is, so a
  stale one over a ceiling still ends the loop (the readings come from
  qa-budget's status line, so they are as recent as the last session that
  showed it). A guard that cannot be asked (missing or broken) ends the loop,
  which never lets a wake-up through unchecked.
- **The loop's own limits**, below: wake-ups, hours and wake-ups in a row
  without progress.

### When a loop ends

Whichever comes first. After the end, further wake-ups are blocked, and Claude
is asked to delete the job at its next turn.

- Claude marks the work delivered, or the person asks it to stop.
- The maximum of wake-ups, `claude_code_skills_loop_to_delivery_max_wakes`, is
  reached. A wake-up whose turn failed on a rate or credit limit, an overload or
  a server error does not count: such a turn may have used some requests, but
  an outage cannot use the maximum up. Any other failed turn (the output limit,
  an invalid request, an authentication failure) counts. With wake-ups every 30
  minutes, the default of 5 is about two and a half hours of waiting.
- The maximum of hours, `claude_code_skills_loop_to_delivery_max_hours`, has
  passed since the loop began.
- 6 wake-ups in a row passed without progress.
- qa-budget's guard blocked a wake-up: a ceiling of the subscription or its
  limit is reached ([above](#how-it-stays-inside-the-budget)). The loop does not
  resume when the usage drops; Claude starts a new one when the person asks for
  more.
- A wake-up arrives in another conversation. A loop belongs to the conversation
  that started it: `/clear`, a switch with `/resume` and a fork each start
  another conversation, so they end it as soon as its job fires there. Nothing
  carries over; `status` (below) lists the loops with their notes, to start a
  new one from.

These limits protect against a runaway loop, not against a hostile model: the
loop's state is in the home of the account that Claude runs as.

### Stopping it, and seeing what runs

Ask Claude to stop the loop. Or stop every loop of the account yourself, as
Claude's account (in the VM, the account you log in as; in a session,
with `!`):

```sh
python3 /etc/claude-code/.claude/skills/loop-to-delivery/loop_to_delivery.py stop
python3 /etc/claude-code/.claude/skills/loop-to-delivery/loop_to_delivery.py status   # what runs, and why loops ended
```

A stopped loop's job is deleted by Claude at its next turn in that conversation.

### What it needs and leaves

- **qa-budget**, on, for its guard at `/etc/claude-code/qa-budget/guard.py`,
  where claude_code_settings installs it in both targets. That path is the one
  thing the role knows of another role's files; the hook passes it to the
  program.
- **State**, in the home of Claude's account: `~/.local/state/loop-to-delivery/`
  (folders 0700, files 0600), a folder per loop with its state, its log and, once
  it ended, the reason. It holds no prompt text. The files are not removed when
  the skill is turned off; without the hooks they do nothing.
- **`/usr/bin/python3`**, for the hook, which runs it with `-I`. The VM's Ubuntu
  has it. The container gets it from its base image
  (`claude_code_podman_base_image`, UBI 9 by default), not from the
  Containerfile, so another base image must provide it. Without it, or with the
  program gone, the hooks do nothing (they fail without blocking anything), and
  a wake-up that reaches Claude without the hook's context makes Claude delete
  its job and say so: at most one model call per job.
- **Turning it off** removes the skill, its program and the hooks at the next
  run or deploy. Do it with no loop running (`status`), or end the sessions
  that hold one: otherwise each such job costs one model call before Claude
  deletes it. The same goes for rolling back to a version without it.
- **Turning it on**: sessions that were open before may not have its hooks;
  start new ones.

## What it hands over

Facts, for the role that includes it:

| Fact | What | Where the targets put it |
|---|---|---|
| `claude_code_skills_files` | The files of the skills that are on, with the subagents they use (the qa skill's first), each its path in the managed settings directory (`name`) and its file in this role (`src`) | `/etc/claude-code/`: the container's `config/`, the VM's `/etc/claude-code/` |
| `claude_code_skills_absent` | The paths there of the skills that are off (a skill's folder, an agent's file) | Removed where an earlier run installed them (the container's `config/` holds only what the deploy lists anyway) |
| `claude_code_skills_policy` | A part of the policy: loop-to-delivery's hooks with the maximums of wake-ups and hours; `{}` while it is off | Merged into [claude_code_settings](../claude_code_settings/README.md)' base, so its hooks come after qa-budget's, before the container's own part and the project's |

A target installs the files before the policy, whose hooks run the program,
and removes those of skills that are off after it.

```yaml
- name: Compute Claude Code's settings and skills
  ansible.builtin.include_role:
    name: "{{ item }}"
  loop: [aslib.infra.claude_code_settings, aslib.infra.claude_code_skills]

- name: Create the folders of the files
  ansible.builtin.file:
    path: /etc/claude-code/{{ item }}
    state: directory
    mode: "0755"
  loop: "{{ (claude_code_settings_files + claude_code_skills_files) | map(attribute='name') | map('dirname') | unique | list }}"

- name: Install the files of the features that are on
  ansible.builtin.copy:
    src: "{{ item.src }}"
    dest: /etc/claude-code/{{ item.name }}
    mode: "0644"
  loop: "{{ claude_code_settings_files + claude_code_skills_files }}"

- name: Install the policy
  ansible.builtin.copy:
    content: "{{ claude_code_settings_policy | combine(claude_code_skills_policy, recursive=True, list_merge='append_rp') | to_nice_json(indent=2) }}"
    dest: /etc/claude-code/managed-settings.json
    mode: "0644"

- name: Remove those of the features that are off
  ansible.builtin.file:
    path: /etc/claude-code/{{ item }}
    state: absent
  loop: "{{ claude_code_settings_absent + claude_code_skills_absent }}"
```
