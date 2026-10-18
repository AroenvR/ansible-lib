<!--
  Claude Code's managed instructions in claude_vm's VM: aslib.infra's claude_vm
  installs this file as /etc/claude-code/CLAUDE.md with every run, so change it
  in aslib.infra (roles/claude_vm/files/CLAUDE.md). Your own instructions go in
  ~/.claude/CLAUDE.md or a project's CLAUDE.md. Block comments like this one
  never reach Claude.
-->

# This VM

You work in a VM of your own, with sudo. Claude Code's policy here is the
project's, and sudo does not change that: a permission denial is a decision,
not an obstacle. Ask about it rather than reaching the same result another way.

## Work that survives an interruption

A session can end at any moment: the VM restarts, or the context fills up and
gets summarised. Keep your work's state on disk as you go,
so that a new session can continue from files alone:

- Commit each finished step, and push work in progress as the project's rules
  say.
- Keep a handoff file per task, outside `/tmp`: what is done, what comes next,
  and open questions. Bring it up to date before every long
  or costly step.
- Save what a future session couldn't rediscover (decisions, preferences,
  corrections) to your memory as soon as you learn it, and remove what turned
  out wrong.

Your home and Claude Code's memory survive restarts; `/tmp` is emptied at every
boot.
