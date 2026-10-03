# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version.

## 0.1.0

- Added role `sudoers`: manage sudo rules as validated drop-in files.
- Added role `node_image` and playbook `acme.infra.node_image`: build a
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
- Added playbook `acme.infra.node_prebuild` and the `node_modules` entry point of
  `node_image`: install a project's node_modules in a throwaway container,
  keeping the previous one as `node_modules.<time>.bak.tgz`.
- Added role `node_setup` and playbooks `acme.infra.node_setup` and
  `acme.infra.node_update`: prepare a Node.js project with an `ansible/`
  directory. The project's files (inventory, settings in
  group_vars/all/project.yml, a git-ignored environment file copied from
  .env.production) are written once; acme.infra's (ansible.cfg with a log,
  group_vars/all/defaults.yml, the playbooks prebuild.yml, image.yml, deploy.yml,
  site.yml, remove.yml and update-playbooks.yml, the Quadlet template, the guide)
  are brought up to date by every run, keeping a changed one as `<file>.bak`.
  Only the guide names the project.
- Added role `node_deploy` and playbook `acme.infra.node_deploy`: deploy the
  image on RHEL 9.2+ as a rootless Podman service (Quadlet) that starts at boot
  and restarts 10 seconds after a crash, as an account of its own, managed by
  root: images in /opt/containers/images/, Quadlet files in
  /etc/containers/systemd/users/<UID>/. The service's directory /opt/<service>/
  is the app's working directory, at the same path in the container; the deploy
  creates it and `data/`, and manages only `config/` in it (the project's
  `config/production/*.json`, read-only). `/tmp` is in memory
  (`node_deploy_tmp_size`). Read-only, without capabilities; the deploy waits
  until the service answers and shows its log if it does not. Deploying a new
  version replaces the old one, whose archive and images are removed.
- Added playbook `acme.infra.node_remove`: remove a deployed service with its
  account and files, keeping the app's data unless `node_deploy_remove_data` is
  true. A later deploy takes the data over, also as an account with another UID.
