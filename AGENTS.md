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
Ubuntu 24.04 (and newer) servers, and ready-made playbooks. Roles come in
families named by domain: `podman_` roles work for any image, the `node_`
roles (node_setup, node_image, node_deploy) take a Node.js backend from project
to running service, and the `claude_code_` roles, indexed by `claude_code`,
run Claude Code: claude_code_podman as an always-on agent for root,
claude_code_vm in a VM where it may have root, for development, both starting
sessions as claude_code_settings says and offering the skills that
claude_code_skills names (qa and loop-to-delivery). gitlab runs GitLab CE as a rootless
Podman service. node_deploy, claude_code_podman and gitlab
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
  configuration (see Decisions), and packages are installed only when
  missing, claude_code_vm's VM excepted (see Decisions) ([Offline servers and
  repositories](CONTRIBUTING.md#offline-servers-and-repositories)).
- **Podman, never Docker.**
- **Server conventions for containers.** Root manages the
  accounts, images and Quadlet files; every service runs rootless as an account
  of its own; `/opt/<service>/` is the app's, and a deploy touches nothing in
  it but `config/`. podman_service implements them
  ([Conventions](roles/podman_service/README.md#conventions)): build every
  container-based role on it. By hand, root drives an account's systemd with
  `systemctl --user -M <user>@ ...`; roles use the `runuser` prefix they use
  for Podman (see Known pitfalls).
- **Dependencies.** Development tools may be current but are pinned in
  `dev/requirements-*.txt`. Anything downloaded must be genuinely needed and
  enterprise-proven; prefer the OS repositories.
- **KISS over edge cases.** Clarity and readability come first; do not add
  complexity for a 1% case. SOLID applies at role level, with some
  domain-driven design: families of roles by domain, one job per role, roles
  meeting through their interfaces, not through each other's folders ([Role
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
- Verify from a clean state before opening a pull request (see Working on the
  project).

## Working on the project

The repository is the source of truth and the project's memory: a new session,
in any tool, must be able to continue from it alone. Record decisions and their
reasons under Decisions, and bring Status up to date when a change lands. Its
location has changed before and will again, so files call it `<repository>`,
and galaxy.yml names none: a checkout's git remote is its source.

- **Scope.** The maintainer decides what is built. Work on what a request asks
  for; when a change would reach further, or a design choice is open, propose
  it with its trade-offs and ask first. Work in steps, with a commit per step.
- **Work survives an interruption.** A session can end at any moment, so
  nothing lives only in its context:
  - Commit every step locally, and push work in progress to a backup branch of
    your own (`backup/<branch>`) with `[skip ci]` in the commit message (GitHub
    and GitLab start no pipeline for it). The branch a pull request comes from
    gets only finished commits, without the marker: GitHub's suggested squash
    message lists every commit message, and a marker in it once gave `accept`
    no pipeline. Build that branch from develop with the work squashed in
    (`git merge --squash`), never with a force push. Delete the backup branch
    once its work is on the request's branch.
  - Keep notes, results and a handoff (what is done, what comes next, open
    questions) in files outside `/tmp`, which Ubuntu empties at every boot
    (systemd-tmpfiles, `D /tmp`).
  - Before a long or costly step, make sure a new session could continue from
    the repository, the handoff and this file alone.
- **Branches** ([Branches and pull
  requests](CONTRIBUTING.md#branches-and-pull-requests)). Start every change on
  a branch of its own from the current `develop`, one per pull request, never
  from another of your branches. A pull request into `develop` is
  squash-merged once every CI job is green; then delete what is left of its
  branch, on the remote and locally, with any backup branch, so `git branch -a`
  shows only main, accept, develop and work in progress. `develop` goes into
  `accept`, and `accept` into `main`, as pull requests the maintainer merges
  with a merge commit, never a squash: each long-lived branch stays part of the
  next one's history, so none of them diverges. Nobody pushes to `main` or
  `accept` directly, and `develop`, `accept` and `main` are never deleted.
- **Versions.** Every merge into accept raises galaxy.yml's version. The first
  change on develop after a merge into accept raises it (a patch for fixes and
  refactors, a minor version for new features or, before 1.0.0, a breaking
  change) and starts its CHANGELOG.md section; CI's `version raised` job fails
  on any branch whose version is not higher than accept's. When develop holds
  a version's worth, a pull request from develop into accept proposes it.
- **Commits and pull requests** are plain text, without attribution trailers
  (no Co-Authored-By, no session links, no "Generated with" footers), and
  nothing in the repository carries a mark of the tool that wrote it. A pull
  request's description stands on its own, for any reviewer now or later: what
  changed and why, compatibility, how it was tested, open points.
- **Never touch the maintainer's own files**: `.tools/`, `libs/` (a Bash
  library, a git subtree), `.env.example` and personal files like them. They
  stay exactly as the branch has them; the release tarball leaves them out
  (`build_ignore`). Private directories outside git (e.g. `tmp/`) are the
  maintainer's too.
- **Debugging where you can't reproduce.** When a problem shows only on a
  machine you can't run things on yourself, each step you ask someone to run
  there is a playbook in the collection, not loose shell commands: an
  `overview` entry point that changes nothing, or a trial that changes only
  what its options say (`aslib.infra.claude_code_vm_overview`,
  `aslib.infra.claude_code_vm_boot_trial`). They stay, linted and documented like
  everything else, and add up to a debugging toolkit; the field notes below are
  candidates.
- **Verify from a clean state** before opening a pull request: fresh venvs,
  empty pip and Molecule caches, a git checkout. A cached pip wheel once hid a
  CI failure.
- **Facts that change with versions** (module options, package names, upstream
  behaviour) come from current, credible sources, not memory.

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
- node_image's test needs Red Hat's registry, nodejs.org and GitHub tarballs.
  Without them it runs only with stand-in images and locally served samples;
  CI exercises it with real UBI and GitHub.
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
  downloads needs 2.16: claude_code_vm (its host and its VM) checks for it first, and
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
  overlay). On a machine with cgroup v1 node_deploy's only works with an Ubuntu
  24.04 stand-in for the server and `--cgroups=disabled`; CI is the real check.
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
  machine that runs the tests: it holds the test images. Test them in a
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
  `.gitignore` does not list it.
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
  method), so a marker key must not share a name with a dict method: claude_code_podman's
  file lists use `as_is`.
- In 2.12 and 2.14 the handlers of a role brought in with `import_role` do not
  see the importing role's role variables (2.21 does); they fail with an
  undefined variable. Pass such values as facts (claude_code_podman's `project.yml`).
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
- A real RHEL 9 server lacked the `acl` package (getfacl, setfacl),
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
- A folded block (`>`, `>-`) joins its lines with spaces but keeps the line
  break before a line indented further: a shell command written so with a
  more-indented `|| ...` line reached bash as two lines, a syntax error that
  only the VM test, in CI, ran into (2026-10-25). Indent every line of such a
  block the same; `dev/check_folded.py` (part of `make lint`) finds them.
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
  (`unix:path=/run/user/<uid>/bus`). Seen on a real server, and confirmed on
  2026-10-17 by the first server tests over SSH: root's SSH login
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
  later one does not set: claude_code_podman's podman_service got node_deploy's
  `podman_service_health_cmd`, whose `node_deploy_health_check` was undefined
  there. Each import sets every variable it relies on, and such expressions
  guard with `default()`.
- Quadlet writes `HealthCmd=` into `ExecStart` in double quotes, so a command
  with single quotes (node_deploy's `node -e '...'`) arrives intact; a `%` would
  need `%%`. Podman 5.8.2 fixed double quotes in it, so avoid them.
- `getent` replaces the whole `ansible_facts.getent_<database>`: a later lookup
  of the full passwd database removes the key looked up earlier, and the other way round.
- What the tests assume of the machine that runs them: systemd as PID 1;
  cgroup v2 with cpu, memory and pids delegated to user@.service (for the
  memory limits); Red Hat's registry, nodejs.org, GitHub, PyPI, Ansible Galaxy
  and npm reachable; `/dev/kvm` for `make test-vm-*` (a VM without nested KVM
  can't run it). Where one is missing, only a throwaway copy with stand-ins
  runs the suite, and CI is the real check.
- Run the server tests as root, as CI does (`sudo make images
  test-servers-2.14`): CI proves only the rootful run. On an Ubuntu host,
  rootless, the RHEL 9 test server once failed `sudo --list
  --other-user=deploy` with "sudo: PAM account management error:
  Authentication service cannot retrieve authentication info". The cause was
  Ubuntu's AppArmor profile `unix-chkpwd` (below); with the RHEL test image's
  fix, sudoers' test passes rootless too, over SSH.
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
  (`apparmor="DENIED" ... profile="unix-chkpwd"`) on an Ubuntu host, with
  node_deploy's privileged test server. The RHEL test image makes `/etc/shadow`
  0400, which root reads as its owner; useradd, usermod and userdel keep that
  mode. It was also the cause of the rootless sudo failure above.
- `podman restart` of a test server breaks Ansible's SSH connection; the next
  task fails as unreachable, which an `until` loop does not retry. Reset the
  connection and `wait_for_connection` first (node_deploy's verify).
- get_url without a checksum asks again on every run (If-Modified-Since) and
  replaces the file when the answer differs: keyserver.ubuntu.com ignores that
  header, and in CI a second run got a different answer for deadsnakes' key,
  so claude_code_vm's idempotence step failed. claude_code_vm downloads its repository
  keys only where missing and proves them by fingerprint.
- A hard reset of a VM (`virsh reset`) loses what ext4 has not written out
  yet, up to 30 seconds' worth: a new file comes back empty. claude_code_vm's test
  resets the VM first thing; on GitHub's fast runners that came 19 seconds after
  the policy was written, which then was empty (CI, 2026-10-17). claude_code_vm ends
  its guest setup with `sync`.
- microdnf (librhsm) in UBI's minimal images writes `redhat.repo` into
  `/etc/yum.repos.d` at every run, unless `/var/lib/rhsm` exists (then it leaves
  that to subscription-manager). With node_image_rpm_repos mounted read-only
  there, it failed ("Read-only file system"); the runtime stage creates
  `/var/lib/rhsm` for that step only. dnf with its subscription-manager plugin
  (the full images) does not mind.
- claude_code_vm's VM gets Python 3.11 from a deadsnakes source of claude_code_vm's own
  (`/etc/apt/sources.list.d/deadsnakes.list`, signed by
  `/etc/apt/keyrings/deadsnakes.asc`). Adding the PPA a second time with
  `add-apt-repository ppa:deadsnakes/ppa` broke `apt-get update` there
  ("Conflicting values set for option Signed-By"): use the source it has.
- A default ACL replaces the umask, but not the mode a program asks for: a file
  created 0600 (Python's tempfile) gets `group::---`, whatever the default ACL
  gives the group. A shell's `>` (0666) gets `group::rw-` even with umask 077.
- In `podman build` (4.9.3), a changed `--build-arg` rebuilds every `RUN` after
  that `ARG`'s declaration, not just those that use it: claude_code_podman's ARGs come
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
- An image's `STOPSIGNAL` is the container's stop signal (images built on
  systemd images declare SIGRTMIN+3, which a plain process ignores, so a stop
  waits out its timeout). GitLab's entrypoint stops
  cleanly on SIGTERM; the gitlab role sets `StopSignal=SIGTERM` and 300 seconds.
- GitLab's image runs as root inside its container and writes outside its
  volumes at every start (runit, Chef, SSH host keys): podman_service's hardened
  template (user 1001, read-only, no capabilities) cannot run it. It reads
  `GITLAB_OMNIBUS_CONFIG` (Ruby) before `/etc/gitlab/gitlab.rb`, copies
  `gitlab.rb` there only when missing, and answers `/` with a redirect to its
  `external_url`, which the server itself may not resolve.
- Read in GitLab 19.4.1's source (CI is the proof): `gitlab-healthcheck` passes without its settings file
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
  with claude_code_vm's 4096 MiB), and virt-install leaves it defined, so a rerun
  would only start it again: claude_code_vm checks the size first and undefines a
  VM that did not start. An ARM64 VM (UEFI) keeps its variables in an NVRAM
  file; `virsh undefine` refuses it without `--nvram`.
- virt-install's `--cloud-init` runs the first boot with `on_reboot=destroy` and
  a temporary seed CD, which the VM's saved definition leaves empty; with
  `--noautoconsole` nothing starts the VM again. A restart during that boot
  (most likely UEFI's, on an ARM64 Raspberry Pi) left claude-dev shut off,
  never on its network, and without its account. claude_code_vm builds the NoCloud
  seed itself (xorriso, label `cidata`) and keeps it attached; its test resets
  the VM.
- libvirt on Ubuntu ARM64 gives a new VM `AAVMF_CODE.ms.fd`
  (`40-edk2-aarch64-secure-enrolled.json` comes first): Secure Boot enforced,
  Microsoft's keys enrolled; virt-install adds an emulated TPM when swtpm is
  installed. An x86_64 VM boots with BIOS. On a Raspberry Pi 4
  (Ubuntu 24.04, qemu-efi-aarch64 2024.02) that firmware crashes at every boot
  as it starts Ubuntu's shim from the disk ("Synchronous Exception at
  0x…DC296B98"). Boot trials showed it is the enforcement: the same Secure Boot
  build without keys (`AAVMF_CODE.secboot.fd`, `AAVMF_VARS.fd`) and the plain
  build boot, TPM or not. Likely, unproven: the Pi 4's Cortex-A72 lacks the ARMv8
  crypto instructions that signature checks would use. claude_code_vm boots an ARM64
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
  (`podman-user-wait-network-online.service`, up to 90 seconds each start);
  where the target never comes up, each start takes 90 s.
- Claude Code (2.1.292, verified in a terminal) decides whether it trusts a
  folder before it applies any settings file's `env`: `CLAUDE_CODE_SANDBOXED=1`
  in the claude process's own environment skips the trust dialog, the same in a
  policy's `env` does not. Trusting a folder in `~/.claude.json`
  (`projects[<path>].hasTrustDialogAccepted`) does not reach a git repository
  below it, whose root asks again (documented). The variable is undocumented:
  claude_code_vm's test starts the real Claude Code to catch a release that
  drops it.
- Claude Code's first start shows its setup (theme, then sign-in) until its
  `.claude.json` (in `CLAUDE_CONFIG_DIR`, else `~/.claude.json`) has
  `hasCompletedOnboarding: true`, even with `CLAUDE_CODE_OAUTH_TOKEN` and a
  theme set; no variable skips it. Its Bash tool keeps a `cd` only inside the
  working directories (`additionalDirectories: ["/"]` makes that every one).
  Its environment variables parse booleans: `0` and `false` are off.
- In ansible-core 2.16 the template lookup turns a rendered JSON text into a
  dict, so `| from_json` then fails; `convert_data=false` keeps it text, as in
  2.14.
- `dev/check_shell.py` renders shell templates with `trim_blocks`, as Ansible
  does, and knows only the Ansible filters it lists (`quote`, `dict2items`):
  add a stand-in there for another one a shell template uses.
- Claude Code (2.1.292, verified 2026-10-19) loads managed skills from
  `/etc/claude-code/.claude/skills/<name>/SKILL.md` and managed subagents from
  `/etc/claude-code/.claude/agents/` (the docs did not show the latter's
  path), and expands `${CLAUDE_SKILL_DIR}` in a managed skill to its folder.
  Managed ones win over a person's and a project's of the same name. A
  stand-in for the API (`ANTHROPIC_BASE_URL` at a local server,
  `ANTHROPIC_API_KEY` set) records what Claude Code sends, the skill listing
  and the agent types included, with no model and no sign-in: claude_code_vm's
  test does so (`claude-request.py`). `/agents` is gone in 2.1.292
  (`/list-agents` lists them; `claude agents` is about background sessions),
  and Claude Code refuses bypassPermissions mode as root.
- `ansible.builtin.find` leaves out hidden files and folders unless `hidden:
  true`, and folders unless `file_type` asks for them: podman_service's mirror
  of config/ needs both since config files may sit in `.claude/`.
- A skill's description decides whether Claude takes it unasked. With "Use
  for any request to change a project: ...", Claude (Sonnet, `claude -p`, a
  one-line change) edited the file itself; "Use this skill before changing
  anything in a project: for every request to add, fix, change, ..." made it
  take the qa skill, while questions still went without it (seen 2026-10-19).
- Writes into a project's `.claude/` (the qa skill's `.claude/specs/`) are
  Claude Code's protected paths: allowed in bypassPermissions only, asked in
  `default` and `acceptEdits` (so refused in a `-p` run), refused in
  `dontAsk`; allow rules don't change that (documented; seen in a `-p` run
  with acceptEdits).
- Claude Code (2.1.292, verified 2026-10-20) runs the hooks of the managed policy
  for UserPromptSubmit, Stop, StopFailure and the session events. A hook that
  exits 1 lets the event pass and the transcript records it as
  `hook_non_blocking_error`; exit 2 blocks. `python3 <missing file>` exits 2,
  so as a hook it would block the person's prompt: loop-to-delivery's command
  tests the file first (`[ -r P ] && ...`), which makes a missing program exit
  1. The hooks of a skill's own frontmatter are not restored by `claude
  --resume` (they fired before the resume only), so the loop's hooks are in the
  policy.
- A turn that ends in an API error such as a rate limit runs StopFailure, with
  the turn's `prompt_id` and the error, and no Stop. A job that `CronCreate`
  made during a turn is in the `session_crons` of that turn's first Stop. A
  session-only job fires in an idle session as a prompt with the job's text,
  and a UserPromptSubmit hook that blocks it stops that fire before any API
  request; the job keeps firing. Durable jobs (`durable: true`) go to the
  project's `.claude/scheduled_tasks.json` and resume in a new session;
  `claude --resume` brings back a session-only job. Recurring jobs expire after
  7 days.
- `/clear` gives a new session id in the same process, with no link to the old
  one, and a session-only job made before it keeps firing there: each fire is a
  prompt with the new session id and the job's text. Compaction keeps the
  session id. Whether a job follows a `/resume` switch or a fork is not
  verified.
- A libvirt guest's own reboot does not apply a new definition: `virsh
  setmaxmem`, `setmem` and `setvcpus` with `--config` take effect at the next
  start, so changing a VM's memory or vCPUs takes a shutdown and a start
  (virsh's man page).

## Looking inside a running service (field notes)

Ways to look inside a podman_service service as root on its server. Not a
design yet: candidates for a later feature (one command or playbook for every
podman_service service, a smoke test after a deploy).

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

## Decisions

Each with its reason, newest first. A decision is changed by a new one here.

- 2026-10-25, the qa skill's working rules, from what went wrong while it
  built the skills role and loop-to-delivery (the maintainer: too many
  questions, too long, numbers and labels changed and fixed again and again):
  QA decides what the project's rules decide and lists those decisions in its
  report; it asks only the person's decisions, in one batch at spec time, each
  with a recommendation; it makes behavior-neutral corrections itself with a
  mechanical proof (a word diff, `git diff -w`, unchanged syntax trees), which
  the next review checks; it sizes each expert's task to one run (the per-run
  token budget cut one documentation run short) and pushes tests that only CI
  can run as soon as they exist (a VM test's whitespace defect surfaced only
  after the code review). Product text names the last release, not the
  upcoming one, so a late change of the number touches only galaxy.yml and the
  changelog's heading; spec labels stay in `.claude/specs/` (a hook program
  shipped with them). Each gate takes one review round; lower findings go to
  the list of improvements. Reports to the person use plain words.
- 2026-10-25, qa-budget (PR #35, live on Claude's VM) ships with the skills
  role, so that the qa skill's budget ships with the skill and the VM runs a
  released version: it stays a setting of claude_code_settings,
  `claude_code_settings_qa_budget`, as it needs configuration, and
  claude_code_settings hands over its files again
  (`claude_code_settings_files`, `claude_code_settings_absent`, qa-budget's
  only), which both targets install next to claude_code_skills'.

- 2026-10-25, claude_code_vm's guest upgrades its packages on every run, the
  maintainer's explicit exception to "packages are installed only when
  missing" (offline servers): the VM needs the internet anyway, and the
  playbook that creates the VM should also be how it is updated. A run does
  what `apt upgrade` does,
  Claude Code's repository included, with new dependencies such as a new kernel
  and nothing removed, and restarts the VM cleanly when Ubuntu's marker
  `/var/run/reboot-required` is there, whoever left it, with a bounded wait.
  Every other role, and the host's own packages, still install only when
  missing. Memory and vCPUs of the settings now apply to a VM that exists: a
  run where they differ shuts it down cleanly (never forced; a VM that does
  not shut down within 5 minutes stops the run), sets them for the next start
  and starts it. The disk size and the network stay for a new VM. Both ways
  end the sessions in the VM, so the docs say so.
- 2026-10-25, loop-to-delivery's hook program, the exception to "Markdown and
  Ansible only" of the qa decision (which stands for qa): the maintainer asked
  for work that keeps going across interruptions, and only a hook can block a
  wake-up before it costs a model call and enforce limits (a maximum of
  wake-ups, idle wake-ups in a row, 7 days, one conversation). The skill ships
  one Python program, `loop_to_delivery.py`, which the managed policy's hooks
  (UserPromptSubmit, Stop, StopFailure) and Claude run. It uses only what both
  targets already have: `/usr/bin/python3` (the VM's Ubuntu; the container's
  base image, not the Containerfile), run with `-I`, the standard library, no
  subprocess, no network, no new package or download. A hook that fails never
  blocks the person's prompts; a wake-up without a working hook costs at most
  one model call, as the job's own prompt has Claude delete the job. Its state
  is in Claude's home, and its limits stop a runaway loop, not a hostile model.
  Off by default.
- 2026-10-25, the skills as a role of their own, claude_code_skills: a
  utility both targets include after claude_code_settings. It owns the qa skill
  with its five experts, moved from claude_code_settings (its setting is now
  `claude_code_skills_qa`, and a run that still sets the name it had there
  stops, naming the new one), and loop-to-delivery. It hands over the files of
  the skills that are on, the paths of those that are off, and a part of the
  policy (the loop's hooks, `{}` while it is off); the targets install the
  files before the policy, whose hooks run the program, and merge the part in
  between claude_code_settings' base and their own. One job per role: how a
  session starts and which skills it has change for different reasons, and the
  maintainer found a Claude skill poorly named as a `claude_code_settings`
  setting. In a container project the rename stop is in the build and deploy
  tasks, not in the setup, so `update-playbooks.yml` still runs and rewrites
  `defaults.yml`, which a 0.8.0 setup wrote with the old name.
- 2026-10-19, the qa skill (issue #26, for #11): the skill `qa` (with its
  protocol next to it) and five subagents (architect, tester, reviewer,
  developer, documenter), which both targets install in
  `/etc/claude-code/.claude/`. Synchronous: the session you talk to becomes QA
  through the skill and runs the experts as subagents one at a time, passing
  each report on; QA gives each the protocol's path
  (`${CLAUDE_SKILL_DIR}/protocol.md`), as a subagent starts without the
  conversation. The texts are #11's package (written for agent teams), changed
  only where the synchronous design needs it; its settings, hook script,
  README and examples are not shipped: Markdown and Ansible only. Off by
  default (the maintainer's call), as managed names win over a person's and a
  project's. It needs agent teams off, so a run with both on stops (the issue
  asked only for the README to say so). The targets get the files as facts,
  and the container's config/ (podman_service) now mirrors names with folders;
  the VM removes only what the role ships, so other files there stay. Since
  2026-10-25 claude_code_skills ships it (above).
- 2026-10-18, Claude Code roles as one family (issue #25, the maintainer's
  design): `claude_code` is the index (README and an entry point that stops
  with the map), `claude_code_podman` (was claude_code) and `claude_code_vm`
  (was claude_vm) the targets, `claude_code_settings` the utility both include.
  It owns how a session starts (`claude_code_settings_*`, the same names and
  defaults everywhere) and the base policy, moved from claude_code's
  `files/managed-settings.json`; the container still merges its own part and
  the project's on top (supersedes the 2026-10-09 decision's location of the
  base). Both targets start Claude Code ready to work: bypassPermissions by
  default (`claude_code_bypass_permissions` is gone), no trust dialog
  (`CLAUDE_CODE_SANDBOXED=1` in the claude process's environment, through
  claude-code.sh and the VM's `/usr/local/bin/claude`), no bypass confirmation,
  no first-run setup, `additionalDirectories: ["/"]`. Sign-in through each
  target's own secret channel: container.env (`CLAUDE_CODE_OAUTH_TOKEN` or
  `ANTHROPIC_API_KEY`), and `claude_code_vm_oauth_token` (no_log everywhere,
  root:claude 0640 in the VM, never in the policy or cloud-init). The VM's
  chosen settings live on the host in `/etc/claude-vm/settings.yml`, appended to
  but never rewritten, read by every run as facts (above the inventory, below
  `-e`), kept by a removal. Old setting names stop a run, naming the new ones.
  Names of what the roles create on hosts stay. SOLID, KISS, DDD and TDD are
  the core design of the whole repository (CONTRIBUTING's Role design).
- 2026-10-18, branches: a long-lived `develop` gathers finished changes, each
  a squash-merged pull request from a branch started there; `develop` goes into
  `accept` and `accept` into `main` with merge commits, never squashes, so no
  long-lived branch diverges from the next (squash merges into `accept` and
  `main` had made release after release conflict). Every merge into accept
  raises the version, which CI's `version raised` job checks; `accept` never
  carries the number of a release with other contents.
- 2026-10-17, the end goal (issue #15, a feature not built yet): an offline
  RHEL VM managing all of aslib.infra's non-KVM services, with every
  requirement served by an offline Sonatype Nexus that runs as a container
  managed by aslib.infra and gets its data as a tarball from an online Nexus.
  In it, a RHEL VM develops a Node.js project from a GitLab and builds and
  deploys it to another RHEL VM; aslib.infra itself is one of the packages the
  Nexus serves. Every download source must therefore be able to come from such
  a mirror.
- 2026-10-17, download sources: follow each tool's own configuration and its
  own order, never a layer of aslib's on top, and default to what the
  developer or the machine already provides. For npm the project's `.npmrc`
  comes before the build machine's `~/.npmrc`; for images a role variable
  names the image and the build machine's `registries.conf` says where it comes
  from. aslib adds a setting only where a container build cuts a tool off from
  its own configuration, defaults it to where the tool looks, carries the file
  into the build step only (never into the image) and merges nothing. On a
  subscribed RHEL build machine Podman already gives UBI builds the host's
  repositories. Where no convention exists (an RPM mirror for any other build
  machine), one setting names a directory of `.repo` files that replaces the
  image's repositories for the build instead of adding to them. Built as
  `gitlab_image`, `claude_code_podman_nvm_url` and `claude_code_podman_nvm_sha256`,
  `node_image_rpm_repos` and `claude_code_podman_rpm_repos`. The directory of `.repo`
  files is mounted read-only over the base images' `/etc/yum.repos.d` for the
  build's steps (`podman build --volume ...:ro,z`); claude_code_podman's
  Containerfile therefore imports Anthropic's key into rpm's database and
  installs Claude Code with `--repofrompath` instead of writing
  `claude-code.repo` there. Its default is empty (the images' own
  repositories), not the build machine's `/etc/yum.repos.d`: that holds
  `redhat.repo`, whose certificates a container lacks, and repositories such
  as EPEL that do not belong in an image. Later, a Sonatype Nexus repository,
  to test it all and to store images.
- 2026-10-17, consumers: aslib's consumers are root on the servers they
  manage, mostly RHEL VMs (bare-metal machines are mostly Ubuntu). Managing
  services remotely on RHEL 9.6 VMs comes first; RHEL as a build machine is not
  needed. So the server tests reach their test servers over SSH as root
  (`dev/molecule/test-server-ssh.yml`). SELinux enforcing and a real kernel
  need a real RHEL 9.6 VM, without KVM tests; pin it to 9.6, as UBI's
  repositories already serve 9.8 packages. A dedicated sudo account (issue
  #14) is closed as not planned.
- 2026-10-17, claude_code_vm supports one path, an Ubuntu VM on an Ubuntu host,
  until hosting the VM on RHEL is needed: its hosts are Ubuntu 24.04 or newer,
  it needs ansible-core 2.16 (see Known pitfalls), and its VM test runs in
  GitHub CI, whose standard Linux runners have `/dev/kvm` since April 2024 (an
  x86_64 host; ARM64 is proven by hand on a Raspberry Pi 4). GitLab CI has no
  such job.
- 2026-10-16, documentation: each kind of reader has one place. README.md is
  a short landing page (what aslib.infra is, who it is for, a quick start, how
  to install, links onwards). `docs/` holds the users' guides, one per job, and
  the install page, the reference and the status; it ships with the collection
  (it is not in `build_ignore`), so its relative links work in an installed
  copy too. The role READMEs stay each role's reference. CONTRIBUTING.md is the
  developers' documentation: setup, repository layout, make targets, tests,
  rules, branches, CI and releases. AGENTS.md holds directives, pitfalls,
  decisions and status, and links to CONTRIBUTING.md and `docs/` instead of
  repeating them ([Documentation](CONTRIBUTING.md#documentation)).
- 2026-10-16, location: the repository is aslib (formerly ansible-lib),
  cloned as `aslib/`, anywhere; make's link in `.venv/self/` replaced the
  required `ansible_collections/aslib/infra` path, and both CI pipelines work
  in their checkout itself. Where it is hosted keeps changing (a self-hosted
  GitLab next), so documentation names no location: it says `<repository>`,
  and `<version>` for a release in examples. galaxy.yml names none either (no
  `repository`, the author without a profile URL); a checkout's git remote is
  its source. Once offline hosting works, every URL becomes dynamic.
- 2026-10-16, claude_code_vm's security model allows a credential in the VM that
  pushes branches of the repository Claude works on; never keys to servers.
  claude_code_vm's README says so.
- 2026-10-11, gitlab: GitLab CE as a rootless Podman service (role gitlab, a
  proof of concept) next to claude_code_vm's VM, so that GitLab stays out of the
  VM's reach and Claude has an ordinary account there. Plain HTTP on a private
  network. Collection playbooks with settings in the user's inventory, not a
  project written by a setup (the shared setup mechanism waits). Next, each a
  feature of its own:
  - Backups: `gitlab-backup create` plus `gitlab-ctl backup-etc`
    (gitlab-secrets.json is not in the former), restorable only on the same
    version. Until then [gitlab's README](roles/gitlab/README.md#backups) says
    to copy /opt/gitlab with GitLab stopped. A copy of /opt/gitlab belongs to
    the account's UID and subordinate UIDs: a fixed `podman_service_uid` keeps
    a redeploy on it working; podman_service hands a directory owned by another
    UID to the account with `chown -R`, which would break GitLab's own owners.
  - A runner in the VM (shell executor), matching GitLab's major.minor, from
    packages.gitlab.com (key F6403F6544A38863DAA0B6E03F01618A51312F3F, URL
    /gpgkey/gpg.key since March 2026), registered with a `glrt-` token.
- 2026-10-09, Claude Code's policy has one aslib.infra base, then claude_code's
  `files/managed-settings.json` (claude_code_settings' since 0.7.0), which every
  container deploy merges with
  `files/managed-settings.container.json` and the project's
  `config/managed-settings.json` (later values win, lists combine, as Claude
  Code's own drop-ins do), and which claude_code_vm installs in the VM. Merged by
  Ansible into one file rather than Claude Code's `managed-settings.d/`, where
  a drop-in, read after `managed-settings.json`, would beat the project's
  single values. The VM gets the base only: with sudo, Claude could change it.
- 2026-10-09, from a health check that Claude Code ran in its own container:
  the shared zone's README checksum (read-only for services), `dnf upgrade` in
  claude_code_podman's Containerfile, and memory limits (`podman_service_memory`, no
  limit by default; a role restricts its own service by default, as
  claude_code_podman does with 4g, and the deployer can always lift it). A sticky bit
  for the zone's README stays out (see Known pitfalls).
- 2026-10-08, the oldest systems supported are RHEL 9.6 and Ubuntu 24.04, so
  the tests run ansible-core 2.14 and 2.16 (2.12 and Ubuntu 22.04 are gone);
  ShellCheck joins `make lint`; Podman's own health checks (`HealthCmd`,
  `HealthOnFailure=kill`, `Notify=healthy`, which needs Podman 5, so RHEL
  9.6's servers) watch each service that has one; each role's promises become
  a `verify` entry point, starting with podman_service.
- Releases: CI runs on every push to every branch. A passing branch publishes
  a 7-day branch build (GitHub keeps only the newest); a passing main publishes
  galaxy.yml's version (one patch above the latest tag, should it lag behind)
  as a release with its tag.
- Roles by area: `podman_` roles work for any image (podman_service deploys,
  podman_overview shows root what runs), `node_` roles add what Node.js
  projects need. A future language gets `<language>_` roles on top of
  podman_service. The service's settings are podman_service's
  (`podman_service_port`, ...); node_deploy stops when a project still sets a
  `node_deploy_` name from before 0.1.0.
- Node.js backends:
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
    are Ansible variables in group_vars. The goal is a complete pipeline a
    project's runner executes. Test runs are `npm run test` for now.
  - Images are built on RHEL 9.6 or Ubuntu 24.04 (Podman 4.9+) and are always
    RHEL (UBI); which RHEL major is still open (UBI 9 for now).
  - Projects follow the NestJS convention: a `build` script that makes
    `dist/main.js`, which the image starts by its absolute path (not
    `npm run start:prod`, which would switch to the code's directory);
    `.nvmrc` (default 24) and `package-lock.json` are optional.
  - Download sources: the project holds what is the same everywhere
    (`node_image_registry`, its `.npmrc`, which wins), each build machine what
    differs (registries.conf, its user's `~/.npmrc` as `node_image_npmrc`).
    Never set an npm or node-gyp setting a project's `.npmrc` might set.
  - The build machine keeps `<name>:<version>` and `<name>:build` per project.
  - Supported versions are test data (`roles/node_image/molecule/build_machine/vars/apps.yml`).
  - Services run rootless on RHEL 9.6+ through Quadlet, published on
    127.0.0.1 by default (a containerized Nginx will sit in front later), ports
    3000-3999. `/opt/<service>/` on the server is the app's working directory,
    mounted at the same path; the app may create anything in it (`prod.db`,
    `data/`). `/tmp` is a tmpfs of `podman_service_tmp_size` (512m).
  - prebuild.yml (playbook aslib.infra.node_prebuild) prepares a project for
    development, each step a task there. More steps will come (creating a
    sqlcipher .db file is one, not yet); do not add any unasked.
- Claude Code: one always-on agent per server, as an account of its own
  (`claude-code`, home `/opt/claude-code/`), on UBI 9. Whoever has root has the
  tool: `claude-code` runs `claude` in the container, nothing more. Sessions
  (background ones, resuming, remote) are Claude Code's own, and root users
  keep their terminals with tmux themselves: never manage sessions for them.
  Claude works only in its home and the shared zone. Anthropic's stable
  channel; every build is the update. Network restriction is a setting (the
  sandbox block in the project's README.md), off by default. No Podman in the
  container for now (later, if needed: nested rootless as an opt-in setting,
  never the host's socket). The project is a repository of its own, written by
  `aslib.infra.claude_code_podman_setup`, the only collection playbook for it; everything
  else is in its `ansible/`. Until it is handed over, its image files
  (Containerfile, .containerignore, README.md) are aslib.infra's: every update
  rewrites them, keeping a changed one as `.bak`, and merging is the project
  maintainer's. config/ (the project's part of the policy, CLAUDE.md) is the
  project's, written once from aslib.infra's templates; the deploy merges
  aslib.infra's base policy into it (see the 2026-10-09 decision above).
  `claude_code_bypass_permissions` was the POC's way to autonomy (since 0.7.0,
  bypassPermissions is the default of claude_code_settings). Tests run it
  next to the Node.js service.
- claude_code_vm, a proof of concept: for development, where Claude needs root
  (Molecule's tests use rootful Podman), the boundary is a VM of its own on a
  host with KVM, never a personal machine. What matters is what the VM holds
  (only Claude's login and a credential for its own branches, see above; no
  keys to servers) and what it reaches (the internet, not the local network,
  enforced by nftables on the host). Ubuntu hosts only. Runs on ARM64 (a
  Raspberry Pi 4) and in CI on GitHub's x86_64 runners with KVM. On ARM64 the
  VM boots with UEFI firmware without Secure Boot (qemu-efi-aarch64; see Known
  pitfalls) and is ARM64 itself. The VM has Python 3.11 (deadsnakes, ARM64
  included) next to Ubuntu's 3.12, for both test venvs. GitLab next to it
  needs Podman 5 (podman_service): Ubuntu 24.04 has 4.9, 26.04 has 5.7.
  Without KVM, the alternative is Claude in an unprivileged account with a
  rootless test suite, not started.
- The shared zone `/opt/containers/shared/`: every service reads and writes
  it; a default ACL gives the group the access an app's mode asks for, whatever
  its umask ("tighten later, once the flows work"). A private mode (Python's
  tempfile: 0600) stays private: the README says to `chmod g+rw` before the
  rename. Its README.md (podman_service/files/shared-README.md, root's,
  rewritten by every deploy) is how humans and agents learn to work there;
  Claude's CLAUDE.md points to it instead of repeating it. A service can't
  change it, but could remove or replace it until the next deploy, so its
  checksum sits in `/opt/containers/shared-checksums/` (root's, mounted
  read-only): Claude's CLAUDE.md says to check it first, and `verify` checks
  it. A sticky bit is out (see Known pitfalls).
- Claude's CLAUDE.md: aslib.infra ships the template
  (claude_code_podman/files/CLAUDE.md), each project adjusts its copy in config/.
  Positive, short, facts Claude can't infer; nothing Claude Code's own prompt
  already covers. The policy denies edits to instruction files in Claude's home
  (CLAUDE.md, CLAUDE.local.md, AGENTS.md), which would load in every session.
- Later (SOLID at role level): node_setup and claude_code_podman each write their
  project with the same mechanism (theirs/ours lists, `.bak`), and node_deploy
  and claude_code_podman each wrap podman_service's deploy, restart and remove.
  Extract a shared setup mechanism when a third kind of project arrives, and
  generic lifecycle playbooks after that; not before.

## Status

Last updated 2026-10-25. v0.6.0 is the latest release; accept holds 0.7.0 (the
Claude Code family, issue #25) and 0.8.0 (the qa skill, issue #26); 0.9.0 (the
role claude_code_skills with loop-to-delivery and the qa skill's new working
rules, qa-budget, memory and vCPUs applied to an existing VM, a VM brought up
to date by every run) is next.

- CI passes every job before a release is tagged. Memory limits are checked
  only where cgroup v2 delegates the memory controller (CI's runners).
- Not tested yet ([docs/status.md](docs/status.md#not-tested-yet) lists them
  for users): a real RHEL 9.6 server or VM with SELinux enforcing; a deploy as
  an account that uses sudo; GitLab CI (the `runner-check` job will report
  whether the runner can start containers); claude_code_vm's firewall rules after a
  host reboot (CI resets the VM, but never reboots the host).
- To do: a security review of how pipelines get `container.env`, and of the
  project's `.npmrc`, which stays in the layers of the `<name>:build` image on
  the build machine.
- Open: the license (`LICENSE` is a placeholder, decided later); a pinned source
  for aslib.infra in projects' pipelines once the release location is final.

Update this section whenever the status changes.
