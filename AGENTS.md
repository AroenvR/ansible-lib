# AGENTS.md

Instructions for AI coding agents working on this repository, as directives.
[CONTRIBUTING.md](CONTRIBUTING.md) is part of these instructions: setup,
repository layout, make targets, tests, rules for library code, branches, CI
and releases are there, written for every developer. Read it before changing
anything. This file adds what applies to agents: rules, pitfalls, decisions
and status. What applies to every developer goes into CONTRIBUTING.md, a role
README or `docs/`, and this file links to it instead of repeating it.

## What this is

`aslib.infra` is an Ansible collection: small, tested roles for RHEL 9.6 and
Ubuntu 24.04 (and newer) servers, and ready-made playbooks. Roles are named by
area: `podman_` roles work for any image, and the `node_` roles (node_setup,
node_image, node_deploy) take a Node.js backend from project to running
service. claude_code runs an always-on Claude Code agent for root, claude_vm
creates a VM where Claude Code may have root, for development, and gitlab runs
GitLab CE as a rootless Podman service. node_deploy, claude_code and gitlab
are thin layers over podman_service. Consumers install a release tarball that
holds only runtime files; tests and tooling never ship (`build_ignore` in
`galaxy.yml`). What it offers and how it is used: [README.md](README.md), and
the guides and the reference in [docs/](docs/README.md).

## Non-negotiable constraints

- **Runtime compatibility.** Roles must run on the `ansible-core` the oldest
  supported systems ship: 2.14.18 (RHEL 9.6, AppStream) and 2.16.3 (Ubuntu
  24.04, universe), with Podman 5.4 on servers and 4.9 on build machines. Read
  module docs for 2.14, offline, as [Compatibility](CONTRIBUTING.md#compatibility)
  shows.
- **Only `ansible.builtin`.** Any other collection is a dependency for every
  consumer; ask the maintainer first.
- **Offline servers.** Never assume internet access: everything a build or a
  deploy downloads can come from a mirror, through each tool's own
  configuration (see Status, 2026-10-17), and packages are installed only when
  missing ([Offline servers and
  repositories](CONTRIBUTING.md#offline-servers-and-repositories)).
- **Podman, never Docker.**
- **The maintainer's server conventions for containers.** Root manages the
  accounts, images and Quadlet files; every service runs rootless as an account
  of its own; `/opt/<service>/` is the app's, and a deploy touches nothing in
  it but `config/`. podman_service implements them
  ([Conventions](roles/podman_service/README.md#conventions)): build every
  container-based role on it. The maintainer drives an account's systemd with
  `systemctl --user -M <user>@ ...`; roles use the same `runuser` prefix as for
  Podman (see Known pitfalls).
- **Dependencies.** Development tools may be current but are pinned in
  `dev/requirements-*.txt`. Anything downloaded must be genuinely needed and
  enterprise-proven; prefer the OS repositories.
- **KISS over edge cases.** Clarity and readability come first; do not add
  complexity for a 1% case. SOLID applies at role level ([Role
  design](CONTRIBUTING.md#role-design)).
- **Checks in tests and at runtime (test first).** Write the check first, see
  it fail, then build ([Writing a test](CONTRIBUTING.md#writing-a-test)). What
  a role promises is a list of checks in its `verify` entry point, which its
  Molecule test and every deploy run. Between deploys, Podman's own health
  checks keep a service honest ([The Quadlet
  file](roles/podman_service/README.md#the-quadlet-file)).
- **Documentation and linting are mandatory.** Document every public variable
  in `meta/argument_specs.yml`, and each option and mechanism once, by the role
  that owns it, as [Documentation](CONTRIBUTING.md#documentation) says; `make
  lint` must pass.

## Commands

[Setup](CONTRIBUTING.md#setup) prepares a machine, [Make
targets](CONTRIBUTING.md#make-targets) says what each target runs and which
need root, and [Writing a test](CONTRIBUTING.md#writing-a-test) how to write a
test. On top of those:

- Run the server tests as root, as CI does, images included (`sudo make images
  test-servers-2.14 ROLES=<role>`): rootful Podman has images of its own, and CI
  proves only the rootful run (see Known pitfalls).
- Verify from a clean state before delivering (see Working with the
  maintainer).

## Working with the maintainer

Several agents work on the project at the same time, each in **an environment
of its own**, separate from the maintainer's. The maintainer's repository is the
source of truth. It has moved between names and hosts and will move again, so
files call it `<repository>`, and galaxy.yml names none: a checkout's git
remote is its source.
This file is the project's memory: a new session, in any tool, must be able to
continue from the repository alone. Record decisions and their reasons here,
and bring Status up to date before ending a block of work.

- **Roles.** The maintainer decides; the agent is the architect: it proposes,
  explains the trade-offs and asks one question at a time, then builds. When the
  maintainer wants to talk something through, talk; build once asked to. Work
  in steps, with a task list and a local commit per step.
- **Work survives an interruption.** An agent can be cut off at any moment (its
  credits run out, its machine reboots), so nothing lives only in its context:
  - Commit every step locally, and push work in progress to a backup branch
    of the agent's own (`backup/<branch>`) with `[skip ci]` in the commit
    message (GitHub and GitLab start no pipeline for it). The branch a pull
    request comes from gets only finished commits, without the marker:
    GitHub's suggested squash message lists every commit message, and on
    2026-10-17 a squash merge with it gave `accept` no pipeline. Build that
    branch from accept with the work squashed in (`git merge --squash`),
    never with a force push. Delete the backup branch once its work is on the
    request's branch.
  - Keep notes, results and a handoff (what is done, what comes next, open
    questions for the maintainer) in files outside `/tmp`: Ubuntu, claude_vm's
    VM included, empties `/tmp` at every boot (systemd-tmpfiles, `D /tmp`).
  - Before a long or costly step, make sure a new session could continue from
    the repository, the handoff and this file alone.

- **Branches.** `main` and `accept` are the maintainer's: an agent starts from
  `accept` (not main) and never pushes to either; the maintainer merges accept
  into main. On top of accept, every file of the repository, CI's included, is
  the agent's to change as the work needs. Each agent works on branches of its
  own, named as [Branches and pull
  requests](CONTRIBUTING.md#branches-and-pull-requests) says: one per pull
  request, started from the current accept, never from another of its own
  branches. After the merge it deletes what is left of the branch, on the
  remote and locally, with any backup branch, so `git branch -a` shows only
  main, accept and work in progress (stacked branches once left hanging
  branches behind every squash merge).
- **Never touch the maintainer's own tooling**: `.tools/`, `libs/` (their Bash
  library, a git subtree), `.env.example` and personal files like them. They
  stay exactly as the branch has them, in a pushed branch and in a zip; the
  release tarball leaves them out (`build_ignore`). Private directories outside
  git (e.g. `tmp/`) are theirs too.
- **Delivery is hybrid**, as the maintainer asks, and may take forms not
  written down here yet. In every form, commit messages are plain text, without
  attribution trailers (no Co-Authored-By, no session links).
  - A pushed branch. An agent with push access pushes its branches (CI runs on
    every push). It may open a pull or merge request into accept only when the
    gates pass: every CI job green, the relevant tests proven to pass, lint
    clean. The request's description stands on its own, for any reviewer:
    never written as a continuation of the conversation with the maintainer.
  - A complete zip of the repository root (`git archive` of the agent's
    branch). The maintainer replaces their tree with it, keeping `.git/`, so
    the zip is taken exactly as it is: what it adds, changes or lacks is added,
    changed or deleted. With each zip, give a commit message.
- **Debugging on the maintainer's machines.** When the agent cannot reproduce
  a problem itself, each step it asks the maintainer to run is a playbook in the
  collection, not loose shell commands: an `overview` entry point that changes
  nothing, or a trial that changes only what its options say
  (`aslib.infra.claude_vm_overview`, `aslib.infra.claude_vm_boot_trial`). They
  stay, linted and documented like everything else, and add up to a debugging
  toolkit; the field notes below are candidates. Meanwhile the agent runs lint
  and small checks only, and the full suite once a fix is settled.
- **Verify from a clean state** before delivering: fresh venvs, empty pip and
  Molecule caches, a git checkout. A cached pip wheel once hid a CI failure.
- **Communication.** Be concise and end replies with a `TL;DR:` section. The
  maintainer may use speech-to-text: interpret intent, not literal typos.
  Research version-sensitive facts in credible, current sources instead of
  relying on memory, and cite them in a `Sources:` section before the TL;DR.
  Nothing the agent writes carries a mark of its tool (no attribution lines,
  session links or tool names in commits, files or comments).

## Known pitfalls

All verified (seen, reproduced, or read in documentation or source), unless
the entry says it is likely or not verified yet.

- Molecule 6.0.3 searches `~/.ansible/collections` before `ANSIBLE_COLLECTIONS_PATH`,
  so a stale installed copy can shadow the code under test. Hence `prerun: false`
  (Molecule never installs a copy), `offline: true` in `.ansible-lint`, and
  make's link `.venv/self/ansible_collections/aslib/infra` to the checkout.
- Lint runs on a modern ansible-core, so lint passing does not prove 2.14
  compatibility. Only the Molecule tests and the native test do.
- ansible-lint cannot parse GitLab's `!reference` tag; use YAML anchors.
- `meta-runtime[unsupported-version]` is skipped on purpose (2.14 is supported).
- `galaxy[no-repository]` is skipped on purpose: galaxy.yml names no repository
  (anonymised, 2026-10-16) and aslib.infra is not published on Galaxy.
- Role argument validation evaluates every default before the first task, so a
  default with a failing lookup (e.g. reading package.json) breaks the role with
  an unreadable error. Read files in tasks instead.
- The cloud sandbox some agents use cannot reach Red Hat's registry, nodejs.org
  or GitHub tarballs. `node_image` was verified there with stand-in images and
  locally served samples. claude_vm's VM reaches them, but has not run
  node_image's test yet: so far only CI exercises it with real UBI and GitHub.
- A role called from a loop shares the caller's `item`. Loops inside roles use
  their own `loop_var` (`__<role>_<name>`), and so do loops calling a role.
- NestJS's default branch is `master`, not `main`. Its samples have no lockfile
  and conflicting peer dependencies; NestJS installs them with
  `--legacy-peer-deps`, so the tests write that into the sample's `.npmrc`.
- Podman inside Podman (the native test) needs its own subnet: both default to
  10.88.0.0/16, which makes the inner containers unreachable. The native image
  changes the inner one.
- ansible-core 2.14 modules break on Python 3.12 for HTTPS (`cert_file`
  errors; 2.12 did too). GitHub's runners have 3.12 as python3, so build_machine
  scenarios run modules with the venv's Python (`ansible_python_interpreter`).
  2.14 supports managed machines' Python only up to 3.11 (ansible-core's support
  matrix; 2.16 up to 3.12), so a role that manages Ubuntu 24.04 machines with
  downloads needs 2.16: claude_vm (its host and its VM) checks for it first, and
  CI runs its VM test with 2.16 only (seen 2026-10-17: get_url of the cloud
  image's checksums failed with 2.14).
- Quadlet: systemd specifiers (`%h`) work in `Volume=` and `EnvironmentFile=`.
  Avoid `StateDirectory=` for a user service's data: systemd 252 (RHEL 9) puts it
  in ~/.config, newer versions in ~/.local/state.
- Red Hat's ubi-init image (the RHEL test server) cannot run an account's
  systemd instance (user@.service) as it is: systemd-logind is masked (`loginctl`
  fails with "Could not activate remote peer") and the PAM stack of user@.service
  fails, after which /run/user/<uid> disappears again. The tests of node_deploy
  and gitlab fix both in their shared prepare play
  (`dev/molecule/prepare-podman-server.yml`); if the account's systemd still
  does not start, podman_service's error names the command that shows why
  (`journalctl --unit user@<uid>.service`).
- node_deploy's test runs rootless Podman inside the RHEL 9 test container, and
  so does gitlab's: privileged, with `/home` on a volume (no overlay on
  overlay). In the cloud sandbox node_deploy's only works with an Ubuntu 24.04
  stand-in for the server and `--cgroups=disabled` (that sandbox has cgroup
  v1); CI is the real check.
- An `until` loop with `failed_when: false` never fails, even when its retries
  run out: put the real condition in `failed_when`.
- `--userns=keep-id:uid=1001,gid=0` fails (crun: invalid gid_map); podman_service maps
  uid and gid 1001 and runs the app as 1001:1001 (`User=`, `Group=`).
- Quadlet keys differ between Podman versions (`UserNS=` is not in 4.4); use
  `PodmanArgs=` for anything newer than 4.4.
- `systemctl --user -M <user>@` needs a D-Bus session bus for the account, which
  the UBI test server lacks ("Transport endpoint is not connected"). `runuser
  --user=<user> -- env XDG_RUNTIME_DIR=/run/user/<uid> systemctl --user ...` talks
  to the account's systemd directly and works everywhere.
- `runuser` keeps the caller's working directory, which the account usually
  cannot enter (Ansible's is under /root): Podman then fails with "cannot chdir".
  Run such commands with `chdir: /`.
- Never try `podman image prune` or `podman system reset` on the storage of the
  machine that runs the tests (the cloud sandbox, claude_vm's VM): it holds the
  test images, and the cloud sandbox's stand-in images. Test them in a
  container.
- `.nvmrc` LTS aliases (`lts/*`, `lts/<codename>`) map to majors in
  `roles/node_image/vars/main.yml`; add a line when a new LTS gets its codename.
- Podman's `--env-file` (and Quadlet's `EnvironmentFile=`) keeps quotes and
  `#` as part of a value, unlike dotenv; multiline and quote support was reverted
  in Podman 4.7.1 (containers/podman#19565). node_setup drops the quotes when it
  copies `.env.production`.
- Rootless Podman can relabel (`:Z`) only files the account owns, so everything
  mounted into a service's container belongs to its account, the config files too.
  No test environment has SELinux enforcing; only a real RHEL server shows mistakes here.
- npm counts a package listed in both `dependencies` and `devDependencies` as a
  devDependency: `npm prune --omit=dev` removes it without a word (npm 10.9 and
  11.21), and the app fails with "Cannot find module". node_image refuses such a
  package.json. A stale lockfile alone does not cause this: prune recomputes the flags.
- `npm_config_*` environment variables override the project's `.npmrc`; never set
  one for a setting a project may want to choose (the registry, above all).
- node-gyp reads its options from `npm_package_config_node_gyp_<option>` (and the
  deprecated `npm_config_<option>`, which npm 11 warns about: "Unknown env config").
- Ansible stops reading `group_vars/all.yml` once a `group_vars/all/` directory
  exists (2.12, 2.14); in the directory, files are read in lexical order and the
  last one wins (`defaults.yml`, then `project.yml`).
- In a playbook brought in with `import_playbook` (with `vars:`), `playbook_dir`
  is the imported playbook's directory, not the caller's.
- `-e name=true` gives the string "true", which role argument validation does not
  turn into a boolean for the tasks: test such variables with `| bool`.
- node-gyp prefers its own `dist-url` (e.g. `npm_package_config_node_gyp_dist_url`)
  over npm's `disturl`, so setting it would override a project's `.npmrc`. npm 10,
  11 and 12 still pass unknown `.npmrc` settings (`disturl`,
  `sqlite3_binary_host_mirror`) to install scripts; 11 and 12 warn.
- Podman 3.4 already supported what node_image uses: `podman build --secret` with
  `RUN --mount=type=secret,uid=...`, `--target`, and removing an image's untagged
  parents with `podman rmi` (verified in the Ubuntu 22.04 image), so 4.9 does too.
- Binary output (a tar stream) cannot go through a module's stdout, which is
  text: redirect it to a file in the shell command.
- Podman 3.4 (Ubuntu 22.04) cuts the output of `podman run --interactive` short
  (30 MB came out as 172 kB, with exit code 0) and can hang. Move files in and
  out of a container with `podman cp`, run it with `podman start` and `podman wait`.
- Ansible doubles backslashes inside `{{ }}` (2.12, 2.14), so regular expressions
  in Jinja string literals behave differently than in variables. Put patterns
  and replacements in variables, or avoid backslashes (`[.]` for a dot).
- Handlers do not run when a later task fails. podman_service therefore loads the
  image whenever the account lacks it, not only when the archive changed.
- `podman images --format=json` and `podman image inspect --format=json` give the
  same image ID (`Id`, 64 hex digits); `--format={{.ID}}` with `--no-trunc` adds
  `sha256:`.
- A callback's task results have `result`, `task` and `host` from ansible-core
  2.19 on, and only `_result`, `_task` and `_host` before (deprecated from 2.23).
  run_log supports both.
- Python writes `__pycache__` next to a collection's plugins when Ansible loads them
  from the checkout; the Makefile exports `PYTHONDONTWRITEBYTECODE=1`, as the
  maintainer's `.gitignore` does not list it.
- The command module's `chdir` does not change `PWD`, from which the project's
  playbooks take their directory: a test that runs ansible-playbook from the
  project's `ansible/` sets `PWD` (and `ANSIBLE_CONFIG`) in `environment`.
- Rootless Podman logs to the journal by default only when the account can read
  a journal directory (containers/common `useJournald`). RHEL keeps the journal
  in memory by default, in `/run/log/journal/<machine ID>/` (mode 2750), so it
  falls back to `k8s-file` and the app's output never reaches the journal. The
  Quadlet file sets `--log-driver=journald`. Test containers hid this: Podman's
  systemd mode mounts a tmpfs on `/var/log/journal` (persistent, readable), so
  node_deploy's test server sets `Storage=volatile`, as on RHEL.
- `selectattr('copy', 'defined')` is true for every dict (`dict.copy` is a
  method), so a marker key must not share a name with a dict method: claude_code's
  file lists use `as_is`.
- In 2.12 and 2.14 the handlers of a role brought in with `import_role` do not
  see the importing role's role variables (2.21 does); they fail with an
  undefined variable. Pass such values as facts (claude_code's `project.yml`).
- A rootless container drops the account's supplementary groups unless
  `--group-add=keep-groups`: without it the shared zone gives "Permission
  denied". A new group reaches an account's services only after its systemd
  instance (user@<uid>.service) restarts.
- The file module gives every parent directory it creates the task's owner,
  group and mode: creating `/opt/containers/shared` (2770) first made
  `/opt/containers` 2770 too, locking accounts outside the group out of their
  image archives. Create parents explicitly.
- The command module expands `$VAR` and `~` in its arguments itself, also in
  `argv` (2.12, 2.14; `expand_argument_vars` came in 2.16): `sh -c 'echo $HOME'`
  prints Ansible's HOME, not the container's. Use `printenv HOME`.
- The maintainer's RHEL 9 server lacked the `acl` package (getfacl, setfacl),
  while the test server had it from prepare.yml, so the tests missed it.
  Roles install what they need when it is missing; prepare.yml installs only what
  a default RHEL install would have.
- Red Hat's UBI repositories lack tmux (RHEL has it in BaseOS) and shellcheck;
  UBI's unversioned nodejs is 16 (end of life), so enable a module stream
  (`nodejs:24`). `blockReadsOutsideWorkingDirectories` made Claude Code refuse or
  prompt for every read of the image (/etc, /usr, /tmp), even in bypass mode, for
  nothing the container hides: the policy leaves it off. The policy deny
  `Read(//opt/claude-code/.claude/**)` blocks a
  whole Bash command that touches `.claude/`, and Claude's default memory
  location (`~/.claude/projects/<project>/memory/`) with it: the policy sets
  `autoMemoryDirectory` instead (an allow rule cannot override a deny).
- Claude Code sources `~/.bashrc` when it starts a session's shell (documented)
  and keeps its functions. The image's nvm is in /etc/profile.d, so the deploy
  writes RHEL's default `.bashrc` (which loads /etc/bashrc and profile.d) into
  Claude's home when it has none: useradd never did, as the home is the
  service's directory. Not verified in a real session yet.
- A fact (set_fact, register) beats a block's or task's `vars:` of the same name,
  for the rest of the run. podman_service's removal kept its account command in
  a block variable; after a restart of Claude Code in the same run, the removal of
  the Node.js service ran `podman system reset --force` as claude-code and wiped
  its images. A role that runs for several services in one play sets such
  per-service values with set_fact every time.
- A plain YAML list item containing `: ` is a mapping, not text: an assert's
  `- lookup(...) is search('key: value')` was such a mapping, and assert passed it
  without checking anything. Quote such conditions (`- "..."`);
  `dev/check_conditions.py` (part of `make lint`) finds them.
- YAML flow lists split on commas: an argument like `setfacl --modify=a,b`
  belongs in a block list.
- A sticky bit on a group-writable directory (tried on the shared zone) also
  makes `fs.protected_regular=2` (Ubuntu's default, also on CI's runners) refuse
  O_CREAT opens of another user's file there, so `>>` and most writes fail with
  Permission denied; RHEL's default is 1. Avoid the sticky bit there.
- `runuser` keeps the caller's environment, including `DBUS_SESSION_BUS_ADDRESS`.
  From a root shell entered with `su`, that is another user's bus: Podman as the
  account then warns "no systemd user session available", falls back to
  cgroupfs, and `podman exec` fails writing `cgroup.procs` (Permission denied).
  The claude-code command sets the account's own address
  (`unix:path=/run/user/<uid>/bus`). Seen on the maintainer's server, and
  confirmed on 2026-10-17 by the first server tests over SSH: root's SSH login
  brings root's bus, and node_deploy's checks and gitlab's application settings
  (`podman exec` as the account) failed that way in CI. Every runuser prefix of
  the roles and tests now sets the account's own address too.
- Quadlet with `Notify=healthy`: the first health check runs as the container
  starts; if the app is not listening yet, the next one waits for the full
  `HealthInterval`, so a 4-second app took 31 seconds to start. A startup check
  (`HealthStartupCmd`, every 2 seconds until it passes) brings it back to 5.
  A service whose container systemd restarts while still unhealthy stays
  `activating` until a check passes; wait for `is-active`, not for HTTP.
- In ansible-core 2.14 (not 2.16) the `vars:` of one `import_role` of a role
  reach a later import of the same role in the same play, for the variables the
  later one does not set: claude_code's podman_service got node_deploy's
  `podman_service_health_cmd`, whose `node_deploy_health_check` was undefined
  there. Each import sets every variable it relies on, and such expressions
  guard with `default()`.
- Quadlet writes `HealthCmd=` into `ExecStart` in double quotes, so a command
  with single quotes (node_deploy's `node -e '...'`) arrives intact; a `%` would
  need `%%`. Podman 5.8.2 fixed double quotes in it, so avoid them.
- `getent` replaces the whole `ansible_facts.getent_<database>`: a later lookup
  of the full passwd database removes the key looked up earlier, and the other way round.
- An agent's environment may lack what the tests assume. Two are known: a
  cloud sandbox and claude_vm's VM.
  - The cloud sandbox some agents use had cgroup v1, no systemd as PID 1, no
    Red Hat subscription and no KVM. What made the suite run there, in a
    throwaway copy only: `PodmanArgs=--cgroups=disabled` in the Quadlet
    template; an Ubuntu image standing in for `aslib-test/rhel9` (so `package`
    and Ubuntu's package names in the server prepare); local stand-ins for the
    UBI Node.js images (`node_image_registry`) and for Claude Code's base
    (`claude_code_test_real: false`); NestJS's tarballs from a local web server
    the containers can reach.
  - claude_vm's VM `claude-dev` on the maintainer's Raspberry Pi 4 (Ubuntu
    24.04 ARM64, 2 vCPUs, 2.4 GiB of memory; verified 2026-10-16) has cgroup v2
    with cpu, memory and pids delegated to user@.service, and reaches Red Hat's
    registry, nodejs.org, GitHub, PyPI, Ansible Galaxy and npm. `make setup`,
    `make lint` and `make images` pass there; run the server tests as root (see
    below). It has no /dev/kvm (no nested KVM), so `make test-vm-*` cannot run
    there.
- Run the server tests as root, as CI does (`sudo make images
  test-servers-2.14`). Rootless, in claude_vm's VM, `make test-servers-2.14
  ROLES=sudoers` failed on the RHEL 9 test server: `sudo --list
  --other-user=deploy` gave "sudo: PAM account management error: Authentication
  service cannot retrieve authentication info". A plain ubi-init:9.6 container
  fails the same way under rootless Podman (4.9.3) and passes under rootful
  Podman. Run as root (`sudo make images test-servers-2.14 ROLES=sudoers`), the
  test passes on both test servers. The cause, found on 2026-10-17, is
  Ubuntu's AppArmor profile `unix-chkpwd` (below): with the RHEL test image's
  fix, sudoers' test passes rootless too, over SSH. CI still proves only the
  rootful run.
- sshd in a test container (2026-10-17): the PAM session of RHEL's and
  Ubuntu's sshd requires pam_loginuid, which writes `/proc/self/loginuid` and
  needs `CAP_AUDIT_CONTROL`. A rootful container without it ends every login at
  once (`pam_open_session(): Cannot make/remove an entry for the specified
  session`, ssh exit status 254). The test servers get `capabilities:
  [AUDIT_CONTROL]`; privileged ones have it anyway.
- Ubuntu 24.04's AppArmor profile `unix-chkpwd` attaches by path to RHEL's
  `/usr/sbin/unix_chkpwd` in any unconfined container (privileged, or rootless)
  on an Ubuntu host, and denies it `dac_read_search` and `dac_override`: it is
  written for Debian's `/etc/shadow` (0640, group shadow), not RHEL's (0000).
  PAM's account check then fails (`unix_chkpwd: could not obtain user info
  (root)`, `Access denied for user root by PAM account configuration`), and
  OpenSSH 9.9 penalizes the failed attempts. Seen in the kernel log
  (`apparmor="DENIED" ... profile="unix-chkpwd"`) on claude_vm's VM, with
  node_deploy's privileged test server. The RHEL test image makes `/etc/shadow`
  0400, which root reads as its owner; useradd, usermod and userdel keep that
  mode. It was also the cause of the rootless sudo failure above.
- `podman restart` of a test server breaks Ansible's SSH connection; the next
  task fails as unreachable, which an `until` loop does not retry. Reset the
  connection and `wait_for_connection` first (node_deploy's verify).
- get_url without a checksum asks again on every run (If-Modified-Since) and
  replaces the file when the answer differs: keyserver.ubuntu.com ignores that
  header, and in CI a second run got a different answer for deadsnakes' key,
  so claude_vm's idempotence step failed. claude_vm downloads its repository
  keys only where missing and proves them by fingerprint.
- A hard reset of a VM (`virsh reset`) loses what ext4 has not written out
  yet, up to 30 seconds' worth: a new file comes back empty. claude_vm's test
  resets the VM first thing; on GitHub's fast runners that came 19 seconds after
  the policy was written, which then was empty (CI, 2026-10-17). claude_vm ends
  its guest setup with `sync`.
- microdnf (librhsm) in UBI's minimal images writes `redhat.repo` into
  `/etc/yum.repos.d` at every run, unless `/var/lib/rhsm` exists (then it leaves
  that to subscription-manager). With node_image_rpm_repos mounted read-only
  there, it failed ("Read-only file system"); the runtime stage creates
  `/var/lib/rhsm` for that step only. dnf with its subscription-manager plugin
  (the full images) does not mind.
- claude_vm's VM gets Python 3.11 from a deadsnakes source of claude_vm's own
  (`/etc/apt/sources.list.d/deadsnakes.list`, signed by
  `/etc/apt/keyrings/deadsnakes.asc`). Adding the PPA a second time with
  `add-apt-repository ppa:deadsnakes/ppa` broke `apt-get update` there
  ("Conflicting values set for option Signed-By"): use the source it has.
- A default ACL replaces the umask, but not the mode a program asks for: a file
  created 0600 (Python's tempfile) gets `group::---`, whatever the default ACL
  gives the group. A shell's `>` (0666) gets `group::rw-` even with umask 077.
- In `podman build` (4.9.3), a changed `--build-arg` rebuilds every `RUN` after
  that `ARG`'s declaration, not just those that use it: claude_code's ARGs come
  before the first RUN, so a new Claude Code version reruns `dnf upgrade`.
- Quadlet in Podman 5.4 has no `Memory=` key: the memory limit is
  `PodmanArgs=--memory=`. Rootless, it needs the memory controller
  delegated to `user@.service`, which systemd 252 (RHEL 9) and 255 (Ubuntu
  24.04) do by default. A host with cgroup v1 can't apply it.
- `role_path` in the `vars:` of an `import_role` is the imported role's when
  it is evaluated there: the gitlab role sets a fact with its own path first.
- Quadlet (5.4) passes `Environment="NAME=value"` on as `--env "NAME=value"`,
  single quotes intact; without the double quotes, systemd would take single
  quotes as its own quoting. `quadlet -dryrun -user` (with QUADLET_UNIT_DIRS)
  shows the `podman run` a Quadlet file becomes.
- An image's `STOPSIGNAL` is the container's stop signal (the cloud sandbox's
  stand-in images, built on systemd images, declare SIGRTMIN+3, which a plain
  process ignores, so a stop waited out its timeout). GitLab's entrypoint stops
  cleanly on SIGTERM; the gitlab role sets `StopSignal=SIGTERM` and 300 seconds.
- GitLab's image runs as root inside its container and writes outside its
  volumes at every start (runit, Chef, SSH host keys): podman_service's hardened
  template (user 1001, read-only, no capabilities) cannot run it. It reads
  `GITLAB_OMNIBUS_CONFIG` (Ruby) before `/etc/gitlab/gitlab.rb`, copies
  `gitlab.rb` there only when missing, and answers `/` with a redirect to its
  `external_url`, which the server itself may not resolve.
- Read in GitLab 19.4.1's source (the cloud sandbox cannot run GitLab, so CI
  is the proof): `gitlab-healthcheck` passes without its settings file
  (`/opt/gitlab/etc/gitlab-healthcheck-rc`) since 19.1, and `gitlab-ctl
  reconfigure` writes that file at the end of every start, while Quadlet's
  `--rm` starts each container without it: the health command tests for the
  file first. Product usage events (to events.gitlab.net) are on by default and
  independent of Service Ping; `GITLAB_PRODUCT_USAGE_DATA_ENABLED=false` in the
  Rails environment turns them off. A rejected `initial_root_password` makes the
  database seed `exit 1`, so reconfigure fails at every start (no root without a
  password); the weak-password check also refuses parts of root's name and
  email (Administrator, root, gitlab_admin_...@example.com).
- QEMU reserves a VM's whole memory when it starts: a VM larger than the host
  can give fails with "cannot set up guest memory" (seen on a 4 GB Raspberry Pi
  with claude_vm's 4096 MiB), and virt-install leaves it defined, so a rerun
  would only start it again: claude_vm checks the size first and undefines a
  VM that did not start. An ARM64 VM (UEFI) keeps its variables in an NVRAM
  file; `virsh undefine` refuses it without `--nvram`.
- virt-install's `--cloud-init` runs the first boot with `on_reboot=destroy` and
  a temporary seed CD, which the VM's saved definition leaves empty; with
  `--noautoconsole` nothing starts the VM again. A restart during that boot
  (most likely UEFI's, on an ARM64 Raspberry Pi) left claude-dev shut off,
  never on its network, and without its account. claude_vm builds the NoCloud
  seed itself (xorriso, label `cidata`) and keeps it attached; its test resets
  the VM.
- libvirt on Ubuntu ARM64 gives a new VM `AAVMF_CODE.ms.fd`
  (`40-edk2-aarch64-secure-enrolled.json` comes first): Secure Boot enforced,
  Microsoft's keys enrolled; virt-install adds an emulated TPM when swtpm is
  installed. An x86_64 VM boots with BIOS. On the maintainer's Raspberry Pi 4
  (Ubuntu 24.04, qemu-efi-aarch64 2024.02) that firmware crashes at every boot
  as it starts Ubuntu's shim from the disk ("Synchronous Exception at
  0x…DC296B98"). Boot trials showed it is the enforcement: the same Secure Boot
  build without keys (`AAVMF_CODE.secboot.fd`, `AAVMF_VARS.fd`) and the plain
  build boot, TPM or not. Likely, unproven: the Pi 4's Cortex-A72 lacks the ARMv8
  crypto instructions that signature checks would use. claude_vm boots an ARM64
  VM without Secure Boot (`--boot uefi,firmware.feature0.name=secure-boot,
  firmware.feature0.enabled=no`), and keeps virt-install's `ds=nocloud` SMBIOS
  serial, which tells cloud-init's early ds-identify where its data is.
- virt-xml takes one kind of change per call. `--xml xpath.delete=` with an
  attribute predicate (`disk[@device='cdrom']`) changes nothing ("XML did not
  change"); `--remove-device --disk target=sda` and `--tpm all` work. Deleting
  `<boot dev='hd'/>` is pointless: libvirt puts it back.
- `userdel` removes the account's `/etc/subuid` and `/etc/subgid` ranges and
  `useradd` takes the first free one: files of a removed account's subordinate
  UIDs (GitLab's own users) match a new account only when nothing else took or
  freed a range in between.
- Rootless Quadlet units wait for the system's `network-online.target`
  (`podman-user-wait-network-online.service`, up to 90 seconds each start); in
  the cloud sandbox the target never comes up, so each start there takes 90 s.

## Looking inside a running service (field notes)

Gathered while writing Claude's CLAUDE.md with the maintainer, as root on their
server. Not a design yet: candidates for a later feature (one command or
playbook for every podman_service service, a smoke test after a deploy).

- A command in a service's container, as podman_service itself reaches it:
  `cx() { (cd / && runuser -u <account> -- env XDG_RUNTIME_DIR=/run/user/<uid>
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus podman exec -i <service> "$@"); }`.
  `cd /` because runuser keeps the working directory, which the account usually
  cannot enter; `-i` so a script can come from a heredoc (`cx bash <<'EOF'`); the
  bus address for the reason in Known pitfalls. It is `claude-code` without its
  terminal handling.
- Claude itself, without a terminal: `claude-code -p "<question>"
  --permission-prompts none --allowedTools <tools>` shows what Claude's own shell
  and permissions see, which differs from `cx` (its `.bashrc` snapshot, working
  directories, deny rules). `--allowedTools` takes several values and swallows a
  prompt that follows it: the prompt goes right after `-p`. `claude-code doctor`
  checks Claude Code's own settings and installation.
- The service's state on the host: `/opt/<service>/` as root.

## Status

Last updated 2026-10-18, for accept. v0.5.0 is released (main); what accept has
since goes into 0.6.0.

- Decided with the maintainer on 2026-10-18: pull request descriptions stand on
  their own, and every pull request has one branch, started from the current
  accept and deleted after its merge, remote and local (see Working with the
  maintainer).

- Decided with the maintainer on 2026-10-16: each kind of reader has one place.
  README.md is a short landing page (what aslib.infra is, who it is for, a
  quick start, how to install, links onwards). `docs/` holds the users' guides,
  one per job, and the install page, the reference and the status; it ships
  with the collection (it is not in `build_ignore`), so its relative links work
  in an installed copy too. The role READMEs stay each role's reference.
  CONTRIBUTING.md is the developers' documentation: setup, repository layout,
  make targets, tests, rules, branches, CI and releases. AGENTS.md holds
  directives, pitfalls, decisions and status for agents, and links to
  CONTRIBUTING.md and `docs/` instead of repeating them
  ([Documentation](CONTRIBUTING.md#documentation)).
- Decided with the maintainer on 2026-10-16: the repository is aslib (formerly
  ansible-lib), cloned as `aslib/`, anywhere; make's link in `.venv/self/`
  replaced the required `ansible_collections/aslib/infra` path, and both CI
  pipelines work in their checkout itself. Where it is hosted keeps changing
  (a self-hosted GitLab next), so documentation names no location: it says
  `<repository>`, and `<version>` for a release in examples. galaxy.yml names
  none either (anonymised: no `repository`, the author without a profile URL);
  a checkout's git remote is its source. Once offline hosting works, every URL
  becomes dynamic.
- Decided with the maintainer on 2026-10-16: several agents at once, each in an
  environment of its own, starting from `accept` on branches of their own;
  delivery by pushed branch (requests into accept only past the gates) or by
  zip. See Working with the maintainer.
- Decided with the maintainer on 2026-10-16: the way to `main` is a branch of
  one's own from `accept`, a pull or merge request into `accept`, accepted with
  a green CI at the very least, and the maintainer merging `accept` into
  `main`. A foundation the maintainer will extend
  ([Branches and pull requests](CONTRIBUTING.md#branches-and-pull-requests)).
- Decided with the maintainer on 2026-10-16: the security model allows a push
  credential in claude_vm's VM: a key with which the agent there pushes its own
  branches of aslib.infra's repository (main and accept stay the maintainer's).
  Still no keys to servers. claude_vm's README says so.
- Decided with the maintainer on 2026-10-16: every download source becomes a
  role variable with an upstream default. Gaps to close: GitLab's image
  (`__gitlab_image` in roles/gitlab/vars/main.yml), nvm's URL (`NVM_URL` only
  in claude_code's Containerfile) and the UBI RPM repositories inside the image
  builds of node_image and claude_code. A feature of its own, designed first.
  Closed on 2026-10-17: `gitlab_image`, `claude_code_nvm_url` and
  `claude_code_nvm_sha256`, `node_image_rpm_repos` and `claude_code_rpm_repos`.
- Decided with the maintainer on 2026-10-17, for those gaps and every download
  source: follow each tool's own configuration and its own order, never a layer
  of aslib's on top, and default to what the developer or the machine already
  provides. For npm the project's `.npmrc` comes before the build machine's
  `~/.npmrc`; for images a role variable names the image and the build
  machine's `registries.conf` says where it comes from. aslib adds a setting
  only where a container build cuts a tool off from its own configuration,
  defaults it to where the tool looks, carries the file into the build step
  only (never into the image) and merges nothing. On a subscribed RHEL build
  machine Podman already gives UBI builds the host's repositories. Where no
  convention exists (an RPM mirror for any other build machine), one setting
  names a directory of `.repo` files that replaces the image's repositories for
  the build instead of adding to them. The details are the feature's design.
  Later, a Sonatype Nexus repository, to test it all and to store images.
  Built on 2026-10-17 as designed. The directory of `.repo` files is mounted
  read-only over the base images' `/etc/yum.repos.d` for the build's steps
  (`podman build --volume ...:ro,z`); claude_code's Containerfile therefore
  imports Anthropic's key into rpm's database and installs Claude Code with
  `--repofrompath` instead of writing `claude-code.repo` there. Its default is
  empty (the images' own repositories), not the build machine's
  `/etc/yum.repos.d`: that holds `redhat.repo`, whose certificates a container
  lacks, and repositories such as EPEL that do not belong in an image.
- The end goal, from the maintainer on 2026-10-17 (issue #15, a feature not
  built yet): an offline RHEL VM managing all of aslib.infra's non-KVM services,
  with every requirement served by an offline Sonatype Nexus that runs as a
  container managed by aslib.infra and gets its data as a tarball from an
  online Nexus. In it, a RHEL VM develops a Node.js project from a GitLab and
  builds and deploys it to another RHEL VM; aslib.infra itself is one of the
  packages the Nexus serves. Every download source must therefore be able to
  come from such a mirror.
- Decided with the maintainer on 2026-10-17: aslib's consumers are root on the
  servers they manage, mostly RHEL VMs (bare-metal machines are mostly Ubuntu).
  Managing services remotely on RHEL 9.6 VMs comes first; RHEL as a build
  machine is not needed. Since then the server tests reach their test servers
  over SSH as root (`dev/molecule/test-server-ssh.yml`). SELinux enforcing and a
  real kernel need a real RHEL 9.6 VM, which the maintainer will set up for
  regression runs from claude-dev, without KVM tests; pin it to 9.6, as UBI's
  repositories already serve 9.8 packages. A dedicated sudo account (issue #14)
  is closed as not planned.
- Decided with the maintainer on 2026-10-17: claude_vm supports one path, an
  Ubuntu VM on an Ubuntu host, until hosting the VM on RHEL is needed. Done the
  same day: its supported hosts are Ubuntu 24.04 or newer, it needs
  ansible-core 2.16 (see Known pitfalls), and its VM test runs in GitHub CI,
  whose standard Linux runners have `/dev/kvm` since April 2024 (an x86_64
  host; ARM64 stays proven by hand on the Pi). GitLab CI has no such job.
- Since 2026-10-17 claude-dev also holds a GitHub CLI login of Claude's own
  account (device flow, approved by the maintainer), to open pull requests and
  read issues. It reaches what the push key reaches.
- In claude_vm's VM on the Pi (2026-10-16): `make setup`, `make lint` and
  `make images` pass; sudoers' server test passes as root, not rootless;
  node_setup's and claude_code's build-machine tests pass as root with
  ansible-core 2.14, the latter building the real Claude Code image (2.1.292,
  `dnf upgrade` included) on ARM64; no nested KVM, so no `make test-vm-*` there
  (see Known pitfalls).

- Debugged with the maintainer on their Raspberry Pi 4 (2026-10-16), with the
  new claude_vm_overview and claude_vm_boot_trial: claude-dev's firmware crashed
  in Ubuntu's shim whenever Secure Boot was enforced (libvirt's ARM64 default;
  see Known pitfalls). The page offset of the address (`…B98`) matches
  LP #2145095, whose reporter saw Noble guests fail on a Raspberry Pi 4. Fixed
  by booting an ARM64 VM without Secure Boot. Then claude_vm created and set up
  claude-dev on the Pi in one run (cloud-init from the CD, deadsnakes' Python
  3.11 for arm64, Claude Code): its first run on real hardware.

- Decided with the maintainer on 2026-10-11: a GitLab of Claude's own, GitLab CE
  as a rootless Podman service (role gitlab, a proof of concept) on the laptop
  next to claude_vm's VM, so that GitLab stays out of Claude's reach and Claude
  has an ordinary account. Plain HTTP (a home network). Collection playbooks with
  settings in the user's inventory, not a project written by a setup (the shared
  setup mechanism waits). Next, each a feature of its own:
  - Backups, which the maintainer will copy to a NAS: `gitlab-backup create`
    plus `gitlab-ctl backup-etc` (gitlab-secrets.json is not in the former),
    restorable only on the same version. Until then [gitlab's
    README](roles/gitlab/README.md#backups) says to copy
    /opt/gitlab with GitLab stopped. A copy of /opt/gitlab belongs to the
    account's UID and subordinate UIDs: a fixed `podman_service_uid` keeps a
    redeploy on it working; podman_service hands a directory owned by another UID
    to the account with `chown -R`, which would break GitLab's own owners.
  - A runner in the VM (shell executor), matching GitLab's major.minor, from
    packages.gitlab.com (key F6403F6544A38863DAA0B6E03F01618A51312F3F, URL
    /gpgkey/gpg.key since March 2026), registered with a `glrt-` token.

- Decided with the maintainer on 2026-10-09: Claude Code's policy has one
  aslib.infra base, claude_code's `files/managed-settings.json`, which every
  container deploy merges with `files/managed-settings.container.json` and the
  project's `config/managed-settings.json` (later values win, lists combine, as
  Claude Code's own drop-ins do), and which claude_vm installs in the VM. Merged
  by Ansible into one file rather than Claude Code's `managed-settings.d/`,
  where a drop-in, read after `managed-settings.json`, would beat the project's
  single values. The VM gets the base only: with sudo, Claude could change it.
- Decided with the maintainer on 2026-10-09, from a health check that Claude
  Code ran in its own container: the shared zone's README checksum (read-only for
  services), `dnf upgrade` in claude_code's Containerfile, and memory limits
  (`podman_service_memory`, no limit by default; a role restricts its own
  service by default, as claude_code does with 4g, and the deployer can always
  lift it). A sticky bit for the zone's README stays out (see Known pitfalls).
- Decided with the maintainer on 2026-10-08: the oldest systems supported are
  RHEL 9.6 and Ubuntu 24.04, so the tests run ansible-core 2.14 and 2.16 (2.12
  and Ubuntu 22.04 are gone); ShellCheck joins `make lint`; Podman's own health
  checks (`HealthCmd`, `HealthOnFailure=kill`, `Notify=healthy`, which needs
  Podman 5, so RHEL 9.6's servers) watch each service that has one; each role's
  promises become a `verify` entry point, starting with podman_service.

- GitHub Actions passed everything up to v0.4.0 (CI tags a release only once
  every job passed), and the maintainer's regression tests on their RHEL server
  pass: the NestJS project and Claude Code side by side. The real Claude Code
  image's `dnf upgrade` needs Red Hat's registry, out of the cloud sandbox's
  reach: CI checks it, and so did claude_vm's VM (2026-10-16, above). So far
  only CI checks the memory limits (the cloud sandbox has cgroup v1);
  claude_vm's VM could (cgroup v2) but has not yet.
- Not tested yet ([docs/status.md](docs/status.md#not-tested-yet) lists them
  for users): a real RHEL server or VM, with SELinux enforcing (the
  maintainer's RHEL server runs without it; the RHEL 9.6 VM above is for this);
  a deploy as an account that uses sudo; GitLab CI (the `runner-check` job will
  report whether the runner can start containers).
- To do: a security review of how pipelines get `container.env`, and of the
  project's `.npmrc`, which stays in the layers of the `<name>:build` image on
  the build machine.
- Releases, decided with the maintainer: CI runs on every push to every branch
  (main and accept get their own pipelines later). A passing branch publishes a
  7-day branch build (GitHub keeps only the newest); a passing main publishes
  the next version (one patch above the latest tag, or galaxy.yml's version
  when that is higher) as a release with its tag.
- Roles by area, decided with the maintainer: `podman_` roles work for any image
  (podman_service deploys, podman_overview shows root what runs), `node_` roles
  add what Node.js projects need. A future language gets `<language>_` roles on
  top of podman_service. The service's settings are podman_service's
  (`podman_service_port`, ...); node_deploy stops when a project still sets a
  `node_deploy_` name from before 0.1.0.
- Node.js backends, decided with the maintainer:
  - A project runs `node_setup` once from its root and commits `ansible/`.
    The project's files (inventory.yml, group_vars/all/project.yml written as a
    full copy of the defaults, container.env) are never touched again.
    aslib.infra's files (ansible.cfg with the run_log callback, .gitignore, the
    guide, group_vars/all/defaults.yml, the playbooks,
    templates/service.container.j2) are brought up to date by every setup or
    update-playbooks.yml, a changed one kept as `<file>.bak` (one copy,
    git-ignored): projects ask for template changes upstream instead of patching
    locally. Only the guide names the project; it follows a project's life: set
    up, prebuild, build and deploy, check on it, update aslib.infra, remove.
    A new version is a new build and deploy (build-and-deploy.yml); remove.yml
    keeps the service's directory, `/opt/<service>/` with all the app wrote,
    unless `-e podman_service_remove_workdir=true`.
  - Config: the app reads `config/<file>.json` relative to where it runs. The
    deploy mirrors the project's `config/production/*.json` (not secret, no
    development files) into `/opt/<service>/config/`, read-only for the app.
    Secrets go in container.env, which node_setup first copies from
    `.env.production`. Every later command runs from `ansible/`, and settings
    are Ansible variables in group_vars. The maintainer's goal is a complete
    pipeline a project's runner executes. Test runs are `npm run test` for now.
  - Images are built on RHEL 9.6 or Ubuntu 24.04 (Podman 4.9+) and are always
    RHEL (UBI); which RHEL major is still open (UBI 9 for now).
  - Projects follow the NestJS convention: a `build` script that makes
    `dist/main.js`, which the image starts by its absolute path (not
    `npm run start:prod`, which would switch to the code's directory);
    `.nvmrc` (default 24; the maintainer's projects use `lts/*`) and
    `package-lock.json` are optional.
  - Download sources: the project holds what is the same everywhere
    (`node_image_registry`, its `.npmrc`, which wins), each build machine what
    differs (registries.conf, its user's `~/.npmrc` as `node_image_npmrc`). Never
    set an npm or node-gyp setting a project's `.npmrc` might set.
  - The build machine keeps `<name>:<version>` and `<name>:build` per project.
  - Supported versions are test data (`roles/node_image/molecule/build_machine/vars/apps.yml`).
  - Services run rootless on RHEL 9.6+ through Quadlet, published on
    127.0.0.1 by default (a containerized Nginx will sit in front later), ports
    3000-3999. `/opt/<service>/` on the server is the app's working directory,
    mounted at the same path; the app may create anything in it (`prod.db`,
    `data/`). `/tmp` is a tmpfs of `podman_service_tmp_size` (512m).
  - prebuild.yml (playbook aslib.infra.node_prebuild) prepares a project for
    development, each step a task there. More steps will come (an idea of the
    maintainer's: creating a sqlcipher .db file); do not add any unasked.
- Claude Code, decided with the maintainer: one always-on agent per server, as
  an account of its own (`claude-code`, home `/opt/claude-code/`), on UBI 9.
  Whoever has root has the tool: `claude-code` runs `claude` in the container,
  nothing more. Sessions (background ones, resuming, remote) are Claude Code's
  own, and root users keep their terminals with tmux themselves: never manage
  sessions for them. Claude works only in its home and the shared zone.
  Anthropic's stable channel; every build is the update. Network restriction is
  a setting (the sandbox block in the project's README.md), off by default. No
  Podman in the container for now (later, if needed: nested rootless as an
  opt-in setting, never the host's socket). The project is a repository of its
  own, written by `aslib.infra.claude_setup`, the only collection playbook for
  it; everything else is in its `ansible/`. Until it is handed over, its image
  files (Containerfile, .containerignore, README.md) are aslib.infra's: every
  update rewrites them, keeping a changed one as `.bak`, and merging is the
  project maintainer's. config/ (the project's part of the policy, CLAUDE.md)
  is the project's, written once from aslib.infra's templates; the deploy merges
  aslib.infra's base policy into it (see the 2026-10-09 decision above).
  `claude_code_bypass_permissions` is the POC's way to autonomy.
  Tests run it next to the Node.js service.
- claude_vm, a proof of concept, decided with the maintainer: for development,
  where Claude needs root (Molecule's tests use rootful Podman), the boundary is
  a VM of its own on a host with KVM (the maintainer's is a Raspberry Pi with
  Ubuntu Server 24.04, ARM64), never the maintainer's
  personal VM, which has no nested KVM and where Claude gets no root. What
  matters is what the VM holds (only Claude's login, and since 2026-10-16 a key
  that pushes Claude's own branches, see above; no keys to servers) and what it reaches
  (the internet, not the local network, enforced by nftables on the host).
  Ubuntu hosts only (2026-10-17). Runs on the maintainer's Raspberry Pi 4 (ARM64),
  and in CI on GitHub's x86_64 runners with KVM. On ARM64 the VM boots with UEFI firmware without Secure Boot
  (qemu-efi-aarch64; see Known pitfalls) and is ARM64 itself. The VM has Python
  3.11 (deadsnakes, ARM64 included) next to Ubuntu's 3.12, for both test venvs.
  GitLab next to it needs Podman 5 (podman_service): Ubuntu 24.04 has 4.9,
  26.04 has 5.7. Without KVM, the alternative is Claude in an unprivileged
  account with a rootless test suite, not started.
- The shared zone `/opt/containers/shared/`, decided with the maintainer: every
  service reads and writes it; a default ACL gives the group the access an app's
  mode asks for, whatever its umask ("tighten later, once the flows work"). A
  private mode (Python's tempfile: 0600) stays private: the README says to
  `chmod g+rw` before the rename. Its README.md
  (podman_service/files/shared-README.md, root's, rewritten by every deploy) is
  how humans and agents learn to work there; Claude's CLAUDE.md points to it
  instead of repeating it. A service can't change it, but could remove or
  replace it until the next deploy, so its checksum sits in
  `/opt/containers/shared-checksums/` (root's, mounted read-only): Claude's
  CLAUDE.md says to check it first, and `verify` checks it. The maintainer
  asked for the checksum; a sticky bit is out (see Known pitfalls).
- Claude's CLAUDE.md: aslib.infra ships the template (claude_code/files/CLAUDE.md),
  each project adjusts its copy in config/. Positive, short, facts Claude can't
  infer; nothing Claude Code's own prompt already covers. The policy denies edits
  to instruction files in Claude's home (CLAUDE.md, CLAUDE.local.md, AGENTS.md),
  which would load in every session.
- Later, decided with the maintainer (SOLID at role level): node_setup and
  claude_code each write their project with the same mechanism (theirs/ours
  lists, `.bak`), and node_deploy and claude_code each wrap podman_service's
  deploy, restart and remove. Extract a shared setup mechanism when a third kind
  of project arrives, and generic lifecycle playbooks after that; not before.
- Open: the license (`LICENSE` is a placeholder, decided later); a pinned source
  for aslib.infra in projects' pipelines once the release location is final.

Update this section whenever the status changes.
