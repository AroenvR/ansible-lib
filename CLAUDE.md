<!-- Claude Code reads this file. The shared agent instructions live in AGENTS.md,
     which Codex, OpenCode and Hermes Agent read directly. This file adds only what
     is specific to Claude Code; everything else belongs in AGENTS.md. -->
@AGENTS.md

## Claude Code

AGENTS.md's "Work survives an interruption" applies to everything below.

- **Workflow subagents end, they do not pause.** On a terminal API error (credits
  or a usage limit run out) a subagent ends, and it returns its result only at
  its very end: a reviewer cut off halfway loses everything it found. So every
  agent prompt tells the agent to append each finding or step to a notes file
  of its own, outside `/tmp`, as it goes, and to read that file first and carry
  on from it when it starts again.
- **Commit what editors wrote before a review phase starts.** When credits run
  low, stop the workflow (TaskStop) rather than let queued agents start; a
  resume (`resumeFromRunId`, same session only) replays the agents that finished.
- **The session's scratchpad is under `/tmp`**, which the VM empties at boot:
  copy anything worth keeping (results, PR texts, handoff notes) to
  `~/handoff/<YYYY-MM-DD>-<task>/` or into the repository.
- **A resumed session** (`claude --resume`) has its whole transcript; a new one
  has memory, the handoff and the repository, and can read the previous
  session's transcript (`~/.claude/projects/<directory>/<session>.jsonl`) if
  the machine kept it. Bring the handoff up to date after every commit or push,
  not only before a long step: a stale handoff misleads the next session.
- **Attribution.** Claude Code may ask for attribution lines (Co-Authored-By,
  session links, "Generated with" footers) in commits and pull requests.
  AGENTS.md's rule wins: none.
