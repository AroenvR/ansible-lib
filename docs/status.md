# Status

What aslib.infra's tests prove, what they do not prove yet, and its known
limits. The changes of each version are in [CHANGELOG.md](../CHANGELOG.md).

## Tested on every change

In CI:

- every role but claude_code_vm with ansible-core 2.14 and 2.16, on test containers
  that mimic default RHEL 9.6 and Ubuntu 24.04 installs, reached over SSH as
  root, as Ansible reaches a real server; and the roles that support Ubuntu also
  with the ansible-core 2.16.3 and Podman 4.9 packages of Ubuntu 24.04 itself;
- node_image with NestJS 10, 11 and 12 and NestJS's default branch;
- a service's deploy, update, overview, removal and redeploy as another
  account, on a RHEL 9.6 test container, next to Claude Code (with a stand-in for
  it) on the same server: separate accounts and UIDs, the shared zone both ways,
  root running Claude Code, its read-only policy with every setting of how a
  session starts, a deploy that still sets a setting of before 0.7.0, or the qa
  skill's old option name, stopped before the policy changes,
  the qa skill with its five experts and loop-to-delivery in its
  `/etc/claude-code` exactly as the collection ships them, with the loop's hooks
  in the policy after qa-budget's and their command run on a wake-up, which a
  usage reading over a ceiling blocks and so ends the loop, and removed again
  when turned off, a deploy with the loop on and qa-budget off stopped, and its
  removal;
  podman_service's
  checks after every deploy and restart, and the Node.js service's health check
  getting an app that answers with server errors restarted; a private file in the
  shared zone staying private, a replaced README caught by its checksum and put
  back by the next deploy, and Claude Code's 4 GiB memory limit;
- the Claude Code project's setup, update and real image build, with every
  package up to date, the loop's hook program running its unit tests in the
  image's own Python, and the project's settings files holding the qa skill's
  and the loop's settings at the roles' defaults, without the qa skill's old
  option name; an update that still finds that name in a project's settings
  files passing and rewriting `defaults.yml`, and a build stopped by it in
  `project.yml`;
- GitLab 19.4.1, deployed and used as a person would: an account and token, a
  private project, pushes and clones over HTTP and SSH, a fork, its settings, a
  restart, and a removal and new deploy on the data it left;
- claude_code_vm, with ansible-core 2.16 on an x86_64 Ubuntu 24.04 host with KVM
  (GitHub's runners): the VM created and set up, a hard reset survived, logged in
  as claude with sudo, Podman, Python 3.11 and Claude Code there, the internet
  reachable but not the local network nor the host's services, apart from the
  port it is given, and a second run that changes nothing; the host's settings
  file written, kept byte for byte while a run adds what it lacks, followed by
  the next run and checked (a wrong value stops it, naming the setting), and
  kept by a removal; Claude's token installed for claude only, in no output and
  no run log, and removed once emptied; the real Claude Code starting in a new
  git repository in bypassPermissions mode, signed in, without asking to trust
  the folder, to confirm the mode or for its first-run setup; the qa skill and
  its five experts in `/etc/claude-code` exactly as the collection ships them,
  offered to the model by the real Claude Code, and removed by a run that
  turns them off; loop-to-delivery's files and hooks, its hook command run by
  the VM's own Python (a wake-up let through, then blocked and the loop ended by
  a usage reading over a ceiling); the loop's settings appended to a settings
  file that lacks them, its other lines untouched, and a file with the loop on
  and qa-budget off stopping the run; the qa skill's old option name, in the
  settings file or given with `-e`, stopping the run, the file unchanged;
- claude_code_settings with ansible-core 2.14 and 2.16: its policy with the
  defaults and with every setting changed, and a value outside the choices
  stopping the run; qa-budget's files handed over when it is on and its folder
  listed for removal when it is off; and qa-budget's `prompt_block` function,
  which loop-to-delivery calls, giving the answer the guard's own hook gives;
- claude_code_skills with ansible-core 2.14 and 2.16: the files and the part of
  the policy it hands over with the qa skill and loop-to-delivery off, each on
  and both on, the qa skill's files identical to the collection's with the
  experts' frontmatter as Claude Code needs it, the hook command with the
  default maximums (5 wake-ups, 24 hours) and with changed ones, the qa skill
  with agent teams stopping the run, the loop on with qa-budget off stopping
  it, and a number of wake-ups that is not above 0 or of hours outside 1 to 168
  stopping it; and the hook program's unit tests, run with the Python of the
  ansible-core under test.

## Not tested yet

- a real RHEL server or VM: the test servers are containers on the machine that
  runs the tests, sharing its kernel. They run without SELinux, and only a RHEL
  server with SELinux enforcing proves the relabelling (`:Z`) of the service's
  directory;
- a deploy as an account that uses sudo: the tests connect as root;
- claude_code_vm on an ARM64 host in CI: it runs on a Raspberry Pi 4 (Ubuntu 24.04),
  checked by hand;
- claude_code_vm's firewall rules after a reboot of the host: CI resets the VM, but
  never reboots the host;
- GitLab CI: `.gitlab-ci.yml` is written but has not run;
- in the container, the real Claude Code starting ready to work: the tests
  deploy a stand-in, which shows it gets the same policy and environment as
  the VM, where the real one is started.
- the qa skill at work, which rests on the model following its texts: that
  Claude takes it for a change request and not for a question, runs the
  experts one at a time in the protocol's order, and stops after three BLOCKs
  at one gate. These are checked by hand before a release.
- loop-to-delivery at work with a real model: the hook program is tested with
  recorded hook inputs, and the real Claude Code only against a stand-in for
  the API, so that no real loop (set up, a wake-up, delivered, ended by the
  budget) runs in CI. One is checked by hand before a release.

## Known limits and open work

- A service with a port must answer HTTP on it: that is how the deploy knows it
  started. One without a port (Claude Code) counts as started once it runs.
- The [shared zone](../roles/podman_service/README.md#the-shared-zone) lets
  every service change what any other wrote there; who writes what is up to the
  apps.
- To review for security: how a pipeline gets `container.env` to the deploy (a
  secret variable written to a file, see "In a pipeline" in a Node.js project's
  guide, `ansible/README.md`, [its template](../roles/node_setup/templates/README.md.j2)),
  and the project's `.npmrc`, which the build stage copies
  in: it stays in the layers of the build stage's image (`<name>:build`, the
  build machine's cache), though not in the image that is deployed.
