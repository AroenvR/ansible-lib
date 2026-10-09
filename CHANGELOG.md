# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version
(before 1.0.0, a new minor version).

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
