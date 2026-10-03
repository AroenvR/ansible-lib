# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version.

## 0.1.0

- Added role `sudoers`: manage sudo rules as validated drop-in files.
- Added role `node_image` and playbook `acme.infra.node_image`: build a
  production container image of a Node.js (e.g. NestJS) project on Red Hat UBI 9.
  `.nvmrc` may hold a version or an LTS line (`lts/*`, `lts/jod`, ...).
  Tested with NestJS 10, 11, 12 and NestJS's default branch.
- Added role `node_setup` and playbook `acme.infra.node_setup`: prepare a
  Node.js project with an `ansible/` directory (ansible.cfg, inventory, settings
  in group_vars, the playbooks image.yml, deploy.yml, site.yml and remove.yml, a git-ignored
  environment file and a guide). Building and deploying run from there.
- Added role `node_deploy` and playbook `acme.infra.node_deploy`: deploy the
  image on RHEL 9.2+ as a rootless Podman service (Quadlet) that starts at boot,
  as an account of its own, managed by root: images in /opt/containers/images/,
  Quadlet files in /etc/containers/systemd/users/<UID>/, the service's directory
  in /opt/<service>/. Read-only, without capabilities; the deploy waits until the
  service answers and shows its log if it does not. Deploying a new version
  replaces the old one, whose archive and images are removed.
- Added playbook `acme.infra.node_remove`: remove a deployed service with its
  account, files and data, leaving the server as it was.
