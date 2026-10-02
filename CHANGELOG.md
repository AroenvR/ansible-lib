# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version.

## 0.1.0

- Added role `sudoers`: manage sudo rules as validated drop-in files.
- Added role `node_image` and playbook `acme.infra.node_image`: build a
  production container image of a Node.js (e.g. NestJS) project on Red Hat UBI 9.
  Tested with NestJS 10, 11, 12 and NestJS's default branch.
- Added role `node_setup` and playbook `acme.infra.node_setup`: prepare a
  Node.js project with a `deploy/` directory holding a guide, a Quadlet file, an
  inventory and a git-ignored environment file.
- Added role `node_deploy` and playbook `acme.infra.node_deploy`: deploy the
  image as a rootless Podman service (Quadlet) on RHEL 9.2+ that starts at boot.
