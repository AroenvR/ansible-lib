# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version.

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
  ports) and the latest log lines of those that do not run; read-only. Sets
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
