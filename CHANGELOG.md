# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version
(before 1.0.0, a new minor version).

## 0.8.0

- Added: `claude_code_settings_qa` (off by default) installs the qa skill and
  five expert subagents in Claude Code's `/etc/claude-code/.claude/`, in the
  container and the VM. A request to change a project then goes through the
  skill, which makes the session QA, the lead: it writes the spec and the
  acceptance and runs `architect`, `tester`, `reviewer`, `developer` and
  `documenter` one at a time through the gates G0, GA, GB and GC of the
  protocol next to the skill, passing each one's report to the next, and
  stops to ask after three BLOCKs at one gate; a question is answered without
  it. The texts are the six-role team written for agent teams, changed only
  where running the experts as subagents, one at a time, needs it. Off by
  default because managed skills and subagents win over a person's or a
  project's of the same names; turning it off removes the files at the next
  deploy or run. It needs agent teams off: a run with both on stops, naming
  both settings.
- Added: claude_code_settings hands over `claude_code_settings_files` (the
  files of the features that are on, for the managed settings directory) and
  `claude_code_settings_absent` (the paths of those that are off).
- Changed: podman_service's `podman_service_config_files` takes names with
  folders (`.claude/agents/reviewer.md`) and a mapping's `src` as well as its
  `content`; config/ mirrors the list with its folders, which are the
  account's. A deploy now also removes hidden files and any folder in config/
  that `podman_service_config_files` does not list, with everything in it;
  before, it removed only the other files directly in config/.

### Upgrading from 0.7.0

- A service of podman_service (a Node.js project, Claude Code, GitLab) with
  files placed by hand in its `config/` on the server
  (`/opt/<service>/config/`): the next deploy removes those that are hidden
  or in a folder, as it already removed the others. Move them out of
  `config/` first, or let the deploy bring them: a Node.js project's
  `config/production/*.json`, a Claude Code project's top-level `config/`
  files.

## 0.7.0

- Changed, **breaking**: the Claude Code roles are one family. claude_code,
  the container's role, is now `claude_code_podman`, and claude_vm is
  `claude_code_vm`, each with its settings renamed to match
  (`claude_code_podman_*`, `claude_code_vm_*`). The playbooks are
  `aslib.infra.claude_code_podman_setup` (was `claude_setup`) and
  `aslib.infra.claude_code_vm`, `claude_code_vm_remove`,
  `claude_code_vm_overview` and `claude_code_vm_boot_trial`; the guides
  `docs/claude-code-podman.md` and `docs/claude-code-vm.md`. A run that still
  sets a setting by its old name stops, naming the new one. What the roles
  create on hosts keeps its name: `claude-dev`, `/etc/claude-vm`, the
  `claude-vm` network, firewall table and service, the `claude-code` service
  and command.
- Added: role `claude_code`, the family's index: its README names the role for
  each job, and its entry point stops with that list, so that a project's
  playbook of before 0.7.0 does not silently do nothing.
- Added: role `claude_code_settings`, what both targets share: how a session
  starts, with the same names and defaults in the container and the VM
  (`claude_code_settings_permission_mode` bypassPermissions,
  `claude_code_settings_model` opus, `claude_code_settings_effort` xhigh,
  `claude_code_settings_theme` dark, `claude_code_settings_agent_teams` false,
  `claude_code_settings_ultracode` false), and aslib.infra's base policy, which
  moved there from claude_code's `files/managed-settings.json`. Neither target
  takes Claude Code's settings from the other's folder any more.
- Changed: Claude Code starts ready to work in both targets. bypassPermissions
  mode starts without its confirmation; no folder asks to be trusted (the
  home, any folder in it, git repositories cloned later, the shared zone);
  Claude Code's first-run setup is skipped; and after a `cd`, later Bash
  commands run there, as every directory is a working directory. The
  container's policy no longer lists its own working directories.
- Changed: agent teams and ultracode are off by default (they were on in the
  base policy); `claude_code_settings_agent_teams` and
  `claude_code_settings_ultracode` turn them on.
- Removed: `claude_code_bypass_permissions`. bypassPermissions is the default
  in the container too now; a deploy that still sets it stops, naming
  `claude_code_settings_permission_mode`.
- Added: sign-in through each target's own secret channel. A Claude Code
  project's `container.env` template names `CLAUDE_CODE_OAUTH_TOKEN=`, for the
  token that `claude setup-token` prints, next to `ANTHROPIC_API_KEY=` (the API
  key wins when both are set). claude_code_vm takes `claude_code_vm_oauth_token`,
  hidden from every output and the run log, installed in the VM as
  `/etc/claude-vm/oauth-token` (root:claude, 0640), and removed from it once
  emptied; the VM's new `claude` command (`/usr/local/bin/claude`) passes it on.
- Added: claude_code_vm keeps what a person chooses in `/etc/claude-vm/settings.yml`
  on the host (root's, 0600): the VM's size, network, keys, host ports and
  names, the token and how sessions start. A run writes it when missing and
  adds the settings it lacks, never changing a line that is there; every run
  takes its values from it (over the inventory's; `-e` still wins) and checks
  them. `claude_code_vm_remove` keeps it.

### Upgrading from 0.6.0

1. A Claude Code project (container): in its root directory, run
   `ansible-playbook aslib.infra.claude_code_podman_setup` once, which brings
   its playbooks up to date (its `update-playbooks.yml` still names the old
   role). Then, in `ansible/group_vars/all/project.yml`, rename every
   `claude_code_` setting to `claude_code_podman_` (`claude_code_memory` to
   `claude_code_podman_memory`, and so on), and add the
   `claude_code_settings_*` settings you want to differ from the defaults; the
   new `defaults.yml` lists them all.
2. bypassPermissions is now the default in the container. To keep the
   permission prompts, set `claude_code_settings_permission_mode: default` and
   drop `claude_code_bypass_permissions`. Agent teams and ultracode were on:
   `claude_code_settings_agent_teams: true` and
   `claude_code_settings_ultracode: true` keep them.
3. The VM: rename every `claude_vm_` setting in your inventory to
   `claude_code_vm_`, and run `aslib.infra.claude_code_vm` instead of
   `aslib.infra.claude_vm`. Its first run writes `/etc/claude-vm/settings.yml`
   with the values it used; from then on, change settings there.
4. Playbooks of your own: `aslib.infra.claude_code` is now the index and runs
   nothing; use `aslib.infra.claude_code_podman` and `aslib.infra.claude_code_vm`.

## 0.6.0

- Changed: claude_vm supports Ubuntu hosts only (24.04 or newer, x86_64 or
  ARM64) and needs ansible-core 2.16 or newer, as its host and VM have Python
  3.12, which 2.14 does not support on managed machines; it checks both first.
  Its test runs in CI on GitHub's runners, which have KVM.
- Added: every download source of a build can come from a mirror (a Nexus, say):
  - `gitlab_image`, where GitLab CE's image comes from (Docker Hub's by default);
  - `claude_code_nvm_url` and `claude_code_nvm_sha256`, nvm's script and its
    checksum, which image.yml passes to the Containerfile, so a mirror needs no
    change to it;
  - `node_image_rpm_repos` and `claude_code_rpm_repos`, a directory of dnf
    repository files, such as a mirror's, which replaces the base images' own
    repositories while an image builds (mounted over `/etc/yum.repos.d` for the
    build only, never stored in the image).
- Added: claude_vm installs aslib.infra's instructions for Claude Code in the
  VM, `/etc/claude-code/CLAUDE.md`, with every run: keep work on disk as it
  goes (commits, a handoff file per task, memory), so an interrupted session
  loses nothing, and treat a permission denial as a decision, sudo or not.
- Changed: the template of a Claude Code project's `config/CLAUDE.md` asks the
  same of the container's Claude.
- Changed: claude_code's Containerfile imports Anthropic's key into rpm's
  database and installs Claude Code with `--repofrompath`, so the image no
  longer has `/etc/yum.repos.d/claude-code.repo`. `update-playbooks.yml` brings
  the new Containerfile, keeping a changed one as `Containerfile.bak`.
- Changed: the documentation is reorganised. README.md is a short landing page;
  installing (compatibility, where to get a tarball, versions), a guide per job,
  the reference of roles, playbooks and plugins, and what the tests cover are in
  `docs/` (index: `docs/README.md`), which ships with the collection.
- Changed: podman_service's documentation of `podman_service_health_cmd` says
  how to quote in it: single quotes inside, as Quadlet hands the command on in
  double quotes, which break before Podman 5.8.2.
- Changed: galaxy.yml names no repository URL and no profile URL for its
  author: where aslib.infra is hosted keeps changing.
- Fixed: claude_vm's firewall rules are ordered before `virtqemud.service` again
  (as well as `libvirtd.service`), so a host that runs libvirt as per-driver
  daemons cannot start the VM before its rules are loaded.
- Fixed: a second claude_vm run downloaded deadsnakes' signing key again and
  could change it; repository keys are downloaded only where missing. The guest
  setup ends with `sync`, so a reset soon after it loses no new files.
- Fixed: podman_service and podman_overview run Podman as a service's account
  with that account's own D-Bus session bus. Over SSH as root they kept root's,
  and a command in a service's container failed (`cgroup.procs: Permission
  denied`): gitlab's application settings, and `podman exec` in the checks.
- Fixed: the `requirements.yml` example for a release (README's, now in
  `docs/own-playbooks.md`) lacked the repository's address. The examples now
  write `<repository>` for the URL of aslib.infra's repository and `<version>`
  for a release.

### Upgrading from 0.5.0

- claude_vm: run it with ansible-core 2.16 or newer, on an Ubuntu host; RHEL
  hosts are no longer supported.
- Node.js and Claude Code projects: `ansible-playbook update-playbooks.yml`
  brings the new settings (in `group_vars/all/defaults.yml`) and, for Claude
  Code, the new Containerfile (a changed one is kept as `Containerfile.bak`).
- Claude Code projects: `config/CLAUDE.md` is the project's, so an update
  leaves it as it is. To give Claude the new instruction, add the paragraph
  that starts "A session can end at any moment" from aslib.infra's
  `roles/claude_code/files/CLAUDE.md` to "How we work together".

## 0.5.0

- Added role `claude_vm` and playbooks `aslib.infra.claude_vm` and
  `aslib.infra.claude_vm_remove`, a proof of concept: `claude-dev`, a VM from
  Ubuntu 24.04's cloud image on a host with KVM (RHEL 9.6 or Ubuntu 24.04, or
  newer), where Claude Code has sudo and aslib.infra's tests run (Python 3.11
  next to 3.12, for both ansible-core versions), which reaches the internet but
  not the local network (nftables rules on the host).
- Changed: Claude Code's policy has one base for the container and the VM.
  claude_code's `files/managed-settings.json` is aslib.infra's base, which
  every deploy now merges with the container's own settings and the project's
  `config/managed-settings.json` (later values win, lists combine without
  duplicates). Before, it only seeded new projects, so a change to it never
  reached a deployed container. claude_vm installs the same base in the VM. A
  new project's `config/managed-settings.json` starts as `{}`.
- Added role `gitlab` and playbooks `aslib.infra.gitlab` and
  `aslib.infra.gitlab_remove`, a proof of concept: GitLab CE 19.4.1 as the
  rootless Podman service `gitlab`, with podman_service and a Quadlet file of its
  own (GitLab's image runs as root inside its container). Set up for a private
  instance on a small server without email: sign-ups off, private by default,
  nothing public but by administrators, no Service Ping, version check, Auto
  DevOps, registry, Pages or monitoring, size limits. Plain HTTP on port 8929,
  SSH on 2224, at most 4 GB of memory. The deploy downloads the image as an
  archive on the Ansible machine, so the server needs no access to Docker Hub.
- claude_vm also runs on ARM64 hosts (aarch64, such as a Raspberry Pi): it
  takes the cloud image of the host's architecture and, on ARM64, UEFI firmware
  without Secure Boot for the VM (enforced, as libvirt would have it, Ubuntu's
  boot loader crashes on a Raspberry Pi 4). `claude_vm_image_url` is now empty by default,
  for that image. The playbook checks the VM's memory fits in the host's, and
  removes a VM again that did not start, so that a rerun creates it anew.
  The VM's cloud-init data is a CD of its own that stays attached, so a restart
  during its first boot (UEFI on ARM64) no longer leaves it shut off.
- Added playbooks `aslib.infra.claude_vm_overview` and
  `aslib.infra.claude_vm_boot_trial`, for a VM that does not come up: the first
  shows the host and the VM and changes nothing; the second boots the VM once in
  a changed form (other UEFI firmware, no TPM, no CD drive), with its console
  recorded, and shows how far the boot got.
- Changed: the repository may be cloned anywhere, as `aslib/`. make links the
  checkout into `.venv/self/ansible_collections/aslib/infra` for Ansible, and
  both CI pipelines work in their checkout itself; the
  `ansible_collections/aslib/infra` path is no longer needed.
- Added `claude_vm_host_ports` and `claude_vm_host_names`: ports of the host's
  that claude_vm's VM may reach (such as GitLab's), and names that lead to the
  host from inside the VM.
- Changed: podman_service counts a redirect as the service's answer, and no
  longer follows it (GitLab answers with one, to its own URL).

### Upgrading from 0.4

1. Nothing is required: a project's `config/managed-settings.json` from an
   earlier setup is a full copy of the old policy, and merges to the same
   policy plus what the base adds (ultracode, workflows). To see what is the
   project's own, trim it to what differs from aslib.infra's base and the
   container's settings.

## 0.4.0

- Fixed: the shared zone's README said the group may read and write whatever a
  service creates, whatever mode it asks for. A private mode stays private:
  Python's `tempfile` makes files (0600) only their own service can read. The
  README now says so, and says to `chmod g+rw` before the rename.
- Added a checksum of the shared zone's README: a service can't change it, but
  could remove or replace it, as the directory is the group's. Every deploy
  writes its SHA-256 to `/opt/containers/shared-checksums/README.md.sha256`,
  root's and read-only in every container with the zone; `sha256sum --check`
  on it says whether the README is aslib.infra's. Claude's `CLAUDE.md` template
  says to check it before following the README, and podman_service's checks
  (deploy, restart, `verify`) report a README that does not match.
- Added memory limits: `podman_service_memory` (e.g. `4g`; no limit by
  default). node_deploy sets it from `node_deploy_memory` (no limit by default),
  claude_code from `claude_code_memory`: **Claude Code's container now has at
  most 4 GiB**, so a runaway build in a session can't starve the server. Set
  `claude_code_memory: ""` for no limit.
- claude_code's Containerfile upgrades every package before installing the
  tools, the base image's included: every new image has the package updates
  (security fixes) of its day. Before, packages stayed as old as Red Hat's last
  build of the base image.

### Upgrading from 0.3

1. From each project's `ansible/`: `ansible-playbook update-playbooks.yml`, for
   the Quadlet template (the checksum and the memory limit) and, in Claude Code
   projects, the Containerfile; then deploy. A service whose Quadlet file lacks
   the checksum's mount can't check the README.
2. In Claude Code projects, `config/CLAUDE.md` is the project's: copy the shared
   zone's bullet from aslib.infra's template (`roles/claude_code/files/CLAUDE.md`).
   For more memory than 4g, or none set, put `claude_code_memory` in
   `group_vars/all/project.yml`.

## 0.3.0

- **Breaking:** the oldest supported systems are RHEL 9.6 and Ubuntu 24.04
  (before: RHEL 9 and Ubuntu 22.04), and the oldest ansible-core is 2.14, what
  RHEL 9.6 ships (before: 2.12). Servers that run services need RHEL 9.6's
  Podman (5.0 or newer); build machines need Podman 4.9 or newer. Ubuntu 24.04's
  own `ansible-galaxy` installs the tarball, so extracting it by hand is no
  longer needed.
- Added Podman's own health checks: `podman_service_health_cmd`, run in the
  container every 2 seconds from the start until it passes, then every 30 seconds. systemd counts a service as
  started once it is healthy, and Podman stops it after 3 failed checks in a
  row, after which systemd starts it again. node_deploy gives every Node.js
  service one (`node_deploy_health_check`, on by default): healthy while the app
  answers HTTP on its port with anything but a server error, asked with the
  image's own Node.js. Claude Code's service has none.
- Added the `verify` entry point of `podman_service`: checks, changing nothing,
  that a service is installed, starts at boot, runs, is healthy and answers on
  its port. Every deploy and restart now ends with the same checks.

### Upgrading from 0.2

1. Servers that run services need RHEL 9.6 or newer; control nodes and build
   machines RHEL 9.6 or Ubuntu 24.04 (or newer).
2. From each Node.js project's `ansible/`: `ansible-playbook update-playbooks.yml`,
   for the Quadlet template with the health check; until then the service runs
   without one. An app that answers `/` with a server error (5xx) when it is
   fine sets `node_deploy_health_check: false` in `group_vars/all/project.yml`.

## 0.2.2

- Fixed: `build.yml` stopped when its directory was not a git checkout, such as
  an exported copy, or when git was not installed. Such a build is now named
  after the time only, `dist/aslib-infra.<UTC time>.tgz`. A copy inside another
  checkout no longer takes that checkout's branch and commit.

## 0.2.0

- Added role `claude_code` and playbook `aslib.infra.claude_setup`: an
  always-on Claude Code agent for root on each server. The setup writes a
  project of its own: the image (a Containerfile with Claude Code from
  Anthropic's signed dnf repository on Red Hat UBI 9, with Python 3.12,
  Node.js 24 and nvm, compilers and database clients), `config/` with the
  policy `managed-settings.json` and the instructions `CLAUDE.md` (installed
  read-only as /etc/claude-code), and `ansible/` with the playbooks image.yml,
  deploy.yml, build-and-deploy.yml, restart.yml, remove.yml and
  update-playbooks.yml. `config/` is the project's; the image's files and
  `ansible/` are aslib.infra's, brought up to date by every update. Every build
  takes the repository's newest version unless `claude_code_version` pins one.
  The deploy runs it with `podman_service`, without a port, as the account
  `claude-code` with its home in /opt/claude-code/, and installs `claude-code`
  for root, which runs Claude in the container, with or without a terminal.
  `claude_code_bypass_permissions` starts its sessions without permission
  prompts.
- Added the shared zone, /opt/containers/shared/ (`podman_service_shared`, on
  by default): every service of `podman_service` reads and writes it at the
  same path in its container, and a default ACL keeps whatever any of them
  creates there writable for all (the deploy installs the `acl` package when a
  server lacks it). Its README.md, root's and rewritten by every deploy,
  explains how to work there.
- Added the `restart` entry point of `podman_service`, playbook
  `aslib.infra.node_restart` and `restart.yml` in node projects: restart a
  service and wait until it is ready again.
- Added playbook `aslib.infra.overview`: what aslib.infra runs on the servers,
  each with the command that shows its log, and the latest log lines of what
  does not run; so far the rootless Podman services of `podman_overview`, which
  now shows that command too (`log_command` in `podman_overview_services`).
- Added services without a port (`podman_service_port: 0`): they count as
  started once they run. `podman_service_config_files` also takes
  `{name, content}` entries.
- Changed: removing a service keeps its whole directory, /opt/<service>/
  (`config/` included), unless `podman_service_remove_workdir` is true.
  **Breaking:** `podman_service_remove_data` is now
  `podman_service_remove_workdir`; a removal that still sets the old name stops
  before it removes anything.
- Fixed: a removal that followed another `podman_service` task in the same
  play could act as that other service's account.

### Upgrading from 0.1.0

1. Where a project or command sets `podman_service_remove_data`, rename it to
   `podman_service_remove_workdir`.
2. From each Node.js project's `ansible/`: `ansible-playbook update-playbooks.yml`,
   for `restart.yml` and the Quadlet template with the shared zone.

## 0.1.0

- Added role `sudoers`: manage sudo rules as validated drop-in files.
- Added role `node_image` and playbook `aslib.infra.node_image`: build a
  production container image of a Node.js (e.g. NestJS) project on Red Hat UBI 9,
  started as `node /opt/app-root/src/dist/main.js` (`node_image_main`).
  `.nvmrc` may hold a version or an LTS line (`lts/*`, `lts/jod`, ...).
  `config/`, `data/` and `*.db` stay out of the image. npm takes its settings
  from the project's `.npmrc` and, below that, from the build machine's
  `~/.npmrc` (`node_image_npmrc`), which no image stores; the base images come
  from `node_image_registry`, through the machine's registries.conf. The build
  stops when a package is in both `dependencies` and `devDependencies`. The build
  machine keeps the image and its build stage (`<name>:build`) and removes the
  project's older images. Tested with NestJS 10, 11, 12 and NestJS's default branch.
- Added playbook `aslib.infra.node_prebuild` and the `node_modules` entry point of
  `node_image`: install a project's node_modules in a throwaway container,
  keeping the previous one as `node_modules.<time>.bak.tgz`.
- Added role `node_setup` and playbooks `aslib.infra.node_setup` and
  `aslib.infra.node_update`: prepare a Node.js project with an `ansible/`
  directory. The project's files (inventory, settings in
  group_vars/all/project.yml, a git-ignored environment file copied from
  .env.production) are written once. aslib.infra's (ansible.cfg, which logs
  each run, group_vars/all/defaults.yml, the playbooks prebuild.yml, image.yml,
  deploy.yml, build-and-deploy.yml, remove.yml and update-playbooks.yml, the
  Quadlet template and the guide) are brought up to date by every run, keeping
  a changed one as `<file>.bak`. Only the guide names the project.
- Added role `podman_service`: run an image archive on RHEL 9.2+ as a rootless
  Podman service (Quadlet) that starts at boot and restarts 10 seconds after a
  crash, as an account of its own, managed by root: archives in
  /opt/containers/images/<service>/, Quadlet files in
  /etc/containers/systemd/users/<UID>/. The service's directory /opt/<service>/
  is the app's working directory, at the same path in the container; the deploy
  creates it and `data/`, and manages only `config/` in it (read-only for the
  app). `/tmp` is in memory (`podman_service_tmp_size`). Read-only, without
  capabilities; the deploy waits until the service answers HTTP and shows its
  log if it does not. The app's output goes to the journal, also where the
  account cannot read it (RHEL's default). Only the deployed version stays:
  other versions' archives and the account's other images are removed. Its
  `remove` entry point removes the service with its account and files, keeping
  the app's data unless `podman_service_remove_data` is true; a later deploy
  takes the data over, also as an account with another UID.
- Added role `node_deploy` and playbooks `aslib.infra.node_deploy` and
  `aslib.infra.node_remove`: deploy and remove a Node.js project's image with
  `podman_service`, named after package.json, with the project's
  `container.env`, `config/production/*.json` and Quadlet template.
- Added role `podman_overview` and playbook `aslib.infra.podman_overview`: show
  root every rootless Podman service on the servers (account, state, image,
  ports) and the latest log lines of those that do not run; read-only. Without
  an inventory, on a server itself, the playbook shows that server. Sets
  `podman_overview_services` for playbooks that check on services.
- Added callback plugin `aslib.infra.run_log`: each playbook run in a log file
  of its own, `logs/<playbook>-<UTC time>.log`, readable by its owner only.

### Upgrading a project set up with a branch build before 0.1.0

The collection was called `acme.infra` before 0.1.0. For a project whose
`ansible/` came from such a build:

1. Install aslib.infra 0.1.0 and remove acme.infra
   (`rm -rf ~/.ansible/collections/ansible_collections/acme`).
2. From the project's `ansible/`: `ansible-playbook aslib.infra.node_update`
   (its old `update-playbooks.yml` still imports acme.infra).
3. Rename the service's settings in `group_vars/all/project.yml` (and wherever
   else the project sets them); the deploy stops until they are renamed:
   `sed -i -E 's/^node_deploy_(port|bind_address|container_port|tmp_size|dir|user|uid):/podman_service_\1:/' group_vars/all/project.yml`
4. Delete `site.yml` (now `build-and-deploy.yml`) and `ansible.log` (each run
   now writes a log of its own in `logs/`).
5. On each server, once: `sudo rm /opt/containers/images/<service>-*.tar`. The
   archives now live in `/opt/containers/images/<service>/`.
