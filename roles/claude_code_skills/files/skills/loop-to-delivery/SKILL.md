---
name: loop-to-delivery
description: "Use this skill as soon as work will outlast this turn, before you start it: a change request (also one that another skill, such as qa, leads), or work that waits on CI, a review, a person or another outside event. It keeps the work going across interruptions such as a rate or credit limit, from notes on disk and with a wake-up job about every 30 minutes, until the work is delivered or a limit is reached. Not for questions, or for work you finish within this turn."
---

You keep long work going until it is delivered. A loop has three parts: your **notes** on disk, from which every wake-up continues; a **wake-up job**, a session-only cron job that prompts this conversation about every 30 minutes while it is idle; and this skill's **hooks**, which let a wake-up through only in the conversation that started the loop and within its limits, and block it otherwise before it costs anything. The program is `${CLAUDE_SKILL_DIR}/loop_to_delivery.py`; run it with `python3`.

## When

Set the loop up on your own, without being asked, as soon as you see that the work will outlast this turn. Only in the main session: never from a subagent, and never start a subagent for the loop. Questions, and work you finish within this turn, need no loop.

## Set it up, in this order

1. Write your notes in a file with an absolute path, outside `/tmp` and outside Claude Code's configuration folder (next to the work, or in your home): the goal, the work's own definition of done, what is done, the next step, and what it waits on.
2. Start the loop:
   `python3 ${CLAUDE_SKILL_DIR}/loop_to_delivery.py start --session ${CLAUDE_SESSION_ID} --notes <notes file> --watch <folder>`
   with a `--watch` for each folder where the work's files change (the repository, a folder of artifacts that others write); a change there counts as progress. Run `start` again to change the running loop's notes or watched folders.
3. Run `CronList`, then `CronCreate` exactly as the last line of `start`'s output says, once (skip it when CronList already shows that job). Never `durable: true`, and never another prompt: the prompt carries the loop's id, by which the hooks judge each wake-up.
4. If the hook says at the end of the turn that the loop has no wake-up job, create it exactly as that message says, and delete any other job you made for this work (`CronList`, `CronDelete`).

## On a wake-up

A wake-up is a prompt that starts with `[auto loop-to-delivery <id>]`, with the hook's context "wake-up k of N of loop <id>". Read your notes, do the next step, and record your progress in the notes. If the work can only wait (CI running, an answer from a person), end your turn without writing anything: turns without progress count toward the idle limit, which ends a loop that is stuck. A wake-up after a rate or credit limit error continues like any other.

A wake-up **without** that context means that the loop's hooks are not active (the session started before the skill was turned on, or it was turned off): delete that job (`CronList`, `CronDelete`) and tell the person.

## The hook's messages

- At the end of a turn, "the work is not delivered yet and your notes moved": do the next step from your notes, as it says.
- The end notice, "loop <id> has ended": delete its wake-up job with `CronDelete`, write in your notes where the work stands and that the loop ended, and tell the person what is left.
- The removal notice, at any prompt ("this conversation still has wake-up jobs that must go"): first delete the jobs it names (`CronList`, `CronDelete`), then go on with the person's request. Never continue or restart those loops' work unless the person asks for it. When it names this conversation's own loop, also do what the end notice says: write in your notes that the loop ended and where the work stands, and tell the person what is left.

## Ending it

- The work's definition of done is met: `python3 ${CLAUDE_SKILL_DIR}/loop_to_delivery.py end --reason delivered --session ${CLAUDE_SESSION_ID}`, then delete the wake-up job (`CronList`, `CronDelete`) and write a last note.
- The person asks you to stop: `python3 ${CLAUDE_SKILL_DIR}/loop_to_delivery.py end --reason "stopped by the person" --session ${CLAUDE_SESSION_ID}`, then delete the job.
- When `end` answers that there is no active loop, the loop has already ended for the reason it names (at its last allowed wake-up, for example, the maximum comes first): delete the job all the same, and write your last note.
- After an end, never start another loop for the same work unless the person asks for more.

The loop also ends by itself: after its maximum of wake-ups, after 6 wake-ups in a row without progress, or after 7 days. The hook then tells you, as above.

## Conversations

A loop belongs to the conversation that started it. After `/clear`, a switch with `/resume` or a fork, the loop ends as soon as its job fires or shows up in the new conversation, and its wake-ups are blocked there; nothing carries over. When the person asks in a new conversation to go on with that work, `python3 ${CLAUDE_SKILL_DIR}/loop_to_delivery.py status` lists the account's loops with their notes: read them, and start a new loop there.

## The person's controls

Tell the person, when asked: they can ask you to stop the loop, or stop every loop of this account themselves, as this account, with `python3 /etc/claude-code/.claude/skills/loop-to-delivery/loop_to_delivery.py stop` (in this session: `! python3 /etc/claude-code/.claude/skills/loop-to-delivery/loop_to_delivery.py stop`). `status` shows what runs.

"Delivered" is what the work's own definition of done says, as your notes record it.
