# qa-budget: the budget for agent work

The subscription is shared with the person: agent work keeps within a budget, and
stops before it spends what the person needs. Three scripts next to this file
measure and enforce it; this file says how to work with them.

## What is measured

- `~/.claude/qa-budget/rate-limits.json`: the subscription's latest usage, the
  5-hour and the 7-day window, each with its percentage used and its reset. It
  lags one response behind.
- `~/.claude/qa-budget/ledger.jsonl`: a line per expert run when it starts and
  when it stops, and per turn of a session, with its tokens so far and the usage
  then. A `SubagentStop` line is that run's total.

## What the guard enforces

The hook `guard.py` decides before each prompt and each tool call; its comment
lists the limits and their defaults (weekly ceiling 60%, 5-hour ceiling 90%,
the limit 98%, 12 expert runs per session, a token budget per run).

- A turn the person starts is theirs: at a ceiling, they are asked before a new
  expert run, and only they may go on, into extra usage too.
- A turn no person started (a wake-up, a loop) stops at the ceilings and never
  goes into extra usage: its prompt is blocked, a new expert run is denied, and
  at the limit every tool is denied.
- In the last hours before the weekly reset, while the person is inactive, the
  weekly ceiling rises to the limit: what would expire is used, nothing more.

## How to work within it

- Before the first expert run, write the budget into the spec: how many expert
  runs, and at most two review rounds per gate.
- Never start another round for low-severity findings: they go into the list of
  improvements that comes with the delivery.
- When the guard denies an expert run: deliver what passed, with the open
  findings as the list of improvements; or, when nothing can be delivered yet,
  pause: write what is done and what comes next to the task's handoff file, and
  stop. Work goes on after the reset or when the person says so.
- When the guard tells an expert its run is over budget, the expert writes its
  report at once, with what remains as improvements.
- In the final report, give each expert run's tokens (input, cache write, cache
  read, output) and the usage before and after, from the ledger.
- Never work around the guard (another tool, a changed limit, a new session):
  ask the person.
