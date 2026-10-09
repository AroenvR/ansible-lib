# AGENTS.md

Instructions for AI coding agents working on this repository. Humans: see
[README.md](README.md) (using the collection) and [CONTRIBUTING.md](CONTRIBUTING.md)
(developing it). This file only adds what an agent needs on top of those.

## What this is

`aslib.infra` is an Ansible collection: a library of small, tested roles for
RHEL 9.6 and Ubuntu 24.04 (and newer) servers, plus roles and ready-made playbooks that take a
Node.js backend from project to running service (node_setup, node_image,
node_deploy), an always-on Claude Code agent for root (claude_code), and a VM
where Claude Code may have root, for development (claude_vm). Roles
are named by area: `podman_` roles work for any image, `node_` roles add what
Node.js projects need (node_deploy is a thin layer over podman_service), and
claude_code is the same kind of layer for Claude Code. Consumers install a release tarball that holds only runtime
files; tests and tooling never ship (`build_ignore` in `galaxy.yml`).

## Non-negotiable constraints

- **Runtime compatibility.** The oldest systems supported are RHEL 9.6 and
  Ubuntu 24.04. Roles must run on the `ansible-core` they ship: 2.14.18 (RHEL
  9.6, AppStream, on Python 3.11) and 2.16.3 (Ubuntu 24.04, universe, on Python
  3.12), with RHEL 9.6's Podman 5.4 on servers and Ubuntu 24.04's Podman 4.9 on
  build machines. Read module docs for the oldest version offline:
  `.venv/ansible-2.14/bin/ansible-doc ansible.builtin.<module>`.
- **Only `ansible.builtin`.** Any other collection is a dependency for every
  consumer; ask the maintainer first.
- **Offline servers.** Never assume internet access. Every repository, key or
  download URL is a role variable with an upstream default (npm's settings come
  from the project's `.npmrc`), listed in the guide's "Download sources" table
  (node_setup's README.md.j2) and node_image's README. Install packages only
  when missing (the dnf module contacts every enabled repository even for
  installed packages). Each role README states exactly what the server needs.
- **Podman, never Docker.**
- **The maintainer's server conventions for containers.** Root manages the
  accounts, images and Quadlet files. Every service runs rootless as an account
  of its own (`useradd`, `loginctl enable-linger`). Image archives live in
  `/opt/containers/images/<service>/` and are loaded as that account (`runuser -u <user> --
  env XDG_RUNTIME_DIR=/run/user/<uid> podman load`). Quadlet files live in
  `/etc/containers/systemd/users/<UID>/`. The maintainer drives the account's
  systemd with `systemctl --user -M <user>@ ...`; roles use the same `runuser`
  prefix as for Podman (see Known pitfalls). A service's own directory is
  `/opt/<service>/`: the app's, its working directory at the same path inside
  the container, never touched by a deploy except `config/` in it; it
  survives a removal unless asked (`podman_service_remove_workdir`). `podman_service` implements this; build every
  container-based role on it.
- **Dependencies.** Development tools may be current but are pinned in
  `dev/requirements-*.txt`. Anything downloaded must be genuinely needed and
  enterprise-proven; prefer the OS repositories.
- **KISS over edge cases.** Clarity and readability come first; do not add
  complexity for a 1% case. SOLID applies at role level (see CONTRIBUTING.md).
- **Checks in tests and at runtime (test first).** What a role promises is a
  list of checks in its `verify` entry point (podman_service has the first):
  its Molecule test runs it, and so does every deploy. Write the check first,
  see it fail, then build. Between deploys, Podman's own health checks keep a
  service honest: systemd counts it as started once it is healthy, and
  restarts it when it is not.
- **Documentation and linting are mandatory.** Every public role variable is
  documented in `meta/argument_specs.yml` with the same default as
  `defaults/main.yml`; `make lint` enforces it, and runs ShellCheck on our shell
  scripts (not on the maintainer's `.tools/` and `libs/`). Each option and mechanism is
  described once, by the role that owns it (podman_service for every service's
  settings); other READMEs link to that section and name the option only where
  a reader uses it. A new option then changes its own role, not every README.

## Commands

The repository must sit at `<dir>/ansible_collections/aslib/infra` (the Makefile
refuses otherwise) and be a git checkout (Molecule finds `.config/molecule/` via
the git root).

```sh
make setup images                          # once: venvs, test-only collections, test containers
make lint                                  # ansible-lint (production profile) + interface check
make test-servers-2.14 ROLES=<role>        # roles that run on servers, in the test containers
make test-build-machine-2.14 ROLES=<role>  # roles that run where Ansible runs
make test-dist-2.14                        # build.yml, in a git checkout and without git
make build                                 # everything CI runs: lint, 2.14 and 2.16, native test
make dist                                  # tarball to try out in dist/ (runs build.yml)
```

Write the failing test first (`roles/<role>/molecule/<scenario>/verify.yml`),
then the role. Name test tasks after what they check and end them with the test
case; end each check with a `success_msg: PASSED <role> ...` line. Keep scenario
playbooks free of Molecule-only variables: the native test runs them with plain
`ansible-playbook`. A new role that supports Ubuntu goes into
`UBUNTU_ROLES` in the Makefile, so the native test covers it. CONTRIBUTING.md
explains the test layout and how releases are made.

## Repository map

| Path | Purpose |
|---|---|
| `roles/<role>/` | The library. `defaults/` + `meta/argument_specs.yml` are the public interface |
| `roles/<role>/molecule/server/` | Tests of a role that runs on servers, in the test server containers |
| `roles/<role>/molecule/build_machine/` | Tests of a role that runs where Ansible runs (e.g. `node_image`), on the test machine itself |
| `roles/node_deploy/molecule/server/` | Also the tests of `podman_service`, `podman_overview` and claude_code's deploy, side by side with the Node.js service |
| `roles/claude_code/molecule/mock/` | A stand-in for Claude Code with the image's contract, for tests that cannot reach Anthropic's repository |
| `roles/claude_vm/molecule/vm/` | Creates the VM on the test machine, which needs KVM; not part of `make test` (`make test-vm-<version>`) |
| `playbooks/` | Ready-made playbooks for people who don't write Ansible: `ansible-playbook aslib.infra.<name>` |
| `plugins/callback/` | Callback plugins (`run_log`). ansible-lint skips them; `make lint` loads their documentation with ansible-doc |
| `build.yml` | Builds the collection tarball: try-out builds and, with `-e release=true`, releases. Never shipped |
| `dev/` | ansible-core pins per version, test images, native test, CI helper scripts. Never shipped |
| `.config/molecule/config.yml` | Molecule settings shared by all roles |
| `.github/workflows/ci.yml`, `.gitlab-ci.yml` | CI; both only call make targets |

## Working with the maintainer

The maintainer and the agent work in **separate environments**. The
maintainer's repositories (GitHub `AroenvR/ansible-lib`, later GitLab) are the
source of truth, and this file is the project's memory: a new session, in any
tool, must be able to continue from the repository alone. Record decisions and
their reasons here, and bring Status up to date before ending a block of work.

- **Roles.** The maintainer decides; the agent is the architect: it proposes,
  explains the trade-offs and asks one question at a time, then builds. When the
  maintainer wants to talk something through, talk; build once asked to. Work
  in steps, with a task list and a local commit per step.

- **Never lose the maintainer's edits.** Before changing a file, use the latest
  version the maintainer provided. Files they have edited so far:
  `.gitignore`, the `on:` block of `.github/workflows/ci.yml` (including its
  TODO comments; its push trigger was changed to every branch at their request)
  and `.github/workflows/test.yml` (the starter workflow, fixed for lint with
  `branches: ["main"]`). Their repository may be ahead of the agent's copy: ask
  for the current version of a file they may have changed before replacing it.
  Only change their lines when they ask; suggest changes in chat instead.
- **The maintainer's own tooling.** `.env.example` and `.tools/archive_git.sh`
  are in the repository and every zip exactly as they gave them; never change
  them. `libs/bash/` is their Bash library (which `archive_git.sh` sources), a
  git subtree they maintain: it is not in the agent's copy, so the zip lacks it,
  and their copy stays as it is. The release tarball leaves all three out
  (`build_ignore`). They also keep private directories that are not in the zip
  and restore them after overwriting; ignore them unless told otherwise.
- **Deliver every change as a complete zip** of the repository root (the zip
  root is the repository root), excluding `.git/`, `.venv/`, `dist/` and tool
  caches. The maintainer overwrites their checkout with it, so every file in the
  zip replaces theirs. With each zip, list the changed files and any files to
  delete (overwriting never deletes), and give a commit message for it: plain
  text, without attribution trailers (no Co-Authored-By, no session links).
- **Verify from a clean state** before delivering: fresh venvs, empty pip and
  Molecule caches, a git checkout. A cached pip wheel once hid a CI failure.
- **Communication.** Be concise and end replies with a `TL;DR:` section. The
  maintainer may use speech-to-text: interpret intent, not literal typos.
  Research version-sensitive facts in credible, current sources instead of
  relying on memory, and cite them in a `Sources:` section before the TL;DR.
  Nothing the agent writes carries a mark of its tool (no attribution lines,
  session links or tool names in commits, files or comments).

## Known pitfalls (all verified)

- Molecule 6.0.3 searches `~/.ansible/collections` before `ANSIBLE_COLLECTIONS_PATH`,
  so a stale installed copy can shadow the code under test. Hence the
  `ansible_collections/aslib/infra` layout, `prerun: false` and `offline: true` in `.ansible-lint`.
- Lint runs on a modern ansible-core, so lint passing does not prove 2.14
  compatibility. Only the Molecule tests and the native test do.
- ansible-lint cannot parse GitLab's `!reference` tag; use YAML anchors.
- `meta-runtime[unsupported-version]` is skipped on purpose (2.14 is supported).
- Role argument validation evaluates every default before the first task, so a
  default with a failing lookup (e.g. reading package.json) breaks the role with
  an unreadable error. Read files in tasks instead.
- The agent's sandbox cannot reach Red Hat's registry, nodejs.org or GitHub
  tarballs. `node_image` was verified there with stand-in images and locally
  served samples; only CI exercises real UBI and GitHub.
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
- Quadlet: systemd specifiers (`%h`) work in `Volume=` and `EnvironmentFile=`.
  Avoid `StateDirectory=` for a user service's data: systemd 252 (RHEL 9) puts it
  in ~/.config, newer versions in ~/.local/state.
- Red Hat's ubi-init image (the RHEL test server) cannot run an account's
  systemd instance (user@.service) as it is: systemd-logind is masked (`loginctl`
  fails with "Could not activate remote peer") and the PAM stack of user@.service
  fails, after which /run/user/<uid> disappears again. node_deploy's test fixes
  both in prepare.yml and prints the journal of user@.service if it still fails.
- node_deploy's test runs rootless Podman inside the RHEL 9 test container:
  privileged, with `/home` on a volume (no overlay on overlay). In the agent's
  sandbox it only works with an Ubuntu 24.04 stand-in for the server and
  `--cgroups=disabled` (the sandbox has cgroup v1); CI is the real check.
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
- Never try `podman image prune` or `podman system reset` on the sandbox host's
  own storage: it holds the test and stand-in images. Test them in a container.
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
  (`unix:path=/run/user/<uid>/bus`). Seen on the maintainer's server; the cause is
  the likeliest one, not yet confirmed there.
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
- A cloud sandbox may lack what the tests assume (the agent's had cgroup v1, no
  systemd as PID 1, no Red Hat subscription, no KVM). What made the suite run
  there, in a throwaway copy only: `PodmanArgs=--cgroups=disabled` in the
  Quadlet template; an Ubuntu image standing in for `aslib-test/rhel9` (so
  `package` and Ubuntu's package names in the server prepare); local stand-ins
  for the UBI Node.js images (`node_image_registry`) and for Claude Code's base
  (`claude_code_test_real: false`); NestJS's tarballs from a local web server
  the containers can reach.

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

Last updated 2026-10-08, on main after v0.2.2.

- Decided with the maintainer on 2026-10-08: the oldest systems supported are
  RHEL 9.6 and Ubuntu 24.04, so the tests run ansible-core 2.14 and 2.16 (2.12
  and Ubuntu 22.04 are gone); ShellCheck joins `make lint`; Podman's own health
  checks (`HealthCmd`, `HealthOnFailure=kill`, `Notify=healthy`, which needs
  Podman 5, so RHEL 9.6's servers) watch each service that has one; each role's
  promises become a `verify` entry point, starting with podman_service.

- GitHub Actions passed everything up to v0.2.2, and the maintainer's
  regression tests on their RHEL server pass: the NestJS project and Claude Code
  side by side. Not yet in CI (verified in the agent's sandbox, whose server
  stand-in is Ubuntu 25.04 for its Podman 5.4): ansible-core 2.14 and 2.16 on
  Python 3.11 and 3.12, the Ubuntu 24.04 images and native test, ShellCheck,
  the health checks and podman_service's verify entry point.
- Not tested yet (README "Status" lists them for users): a deploy over SSH with
  sudo to another machine; SELinux enforcing (the maintainer's RHEL server runs
  without it; look at it later); GitLab CI (the `runner-check` job will report
  whether the runner can start containers).
- To do: a security review of how pipelines get `container.env`, and of the
  project's `.npmrc`, which stays in the layers of the `<name>:build` image on
  the build machine.
- Releases, decided with the maintainer: CI runs on every push to every branch
  (main and accept get their own pipelines later). A passing branch publishes a
  7-day branch build (only the newest kept); a passing main publishes the next
  patch version as a release with its tag.
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
  project maintainer's. config/ (the policy, CLAUDE.md) is the project's,
  written once from aslib.infra's templates. `claude_code_bypass_permissions` is the POC's way to autonomy.
  Tests run it next to the Node.js service.
- claude_vm, a proof of concept, decided with the maintainer: for development,
  where Claude needs root (Molecule's tests use rootful Podman), the boundary is
  a VM of its own on a host with KVM (a spare laptop), never the maintainer's
  personal VM, which has no nested KVM and where Claude gets no root. What
  matters is what the VM holds (only Claude's login: no keys to servers, no git
  credentials; the maintainer fetches Claude's branches) and what it reaches
  (the internet, not the local network, enforced by nftables on the host). Not
  yet run on real hardware or a RHEL host. Without KVM, the alternative is
  Claude in an unprivileged account with a rootless test suite, not started.
- The shared zone `/opt/containers/shared/`, decided with the maintainer: every
  service reads and writes it; a default ACL keeps everything group-writable
  ("tighten later, once the flows work"). Its README.md
  (podman_service/files/shared-README.md, root's, rewritten by every deploy) is
  how humans and agents learn to work there; Claude's CLAUDE.md points to it
  instead of repeating it. A service can't change it, but could remove it until
  the next deploy; one directory per service, created by the deploy under a
  root-owned top level, would close that if it matters.
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
- Open: whether claude_code's image files go back to the project when the MVP
  is handed over (decide before 0.2.0 reaches main, as its changelog says they
  are aslib.infra's); the license (`LICENSE` is a placeholder, decided later); a
  pinned source for aslib.infra in projects' pipelines once the release location
  is final.

Update this section whenever the status changes.
