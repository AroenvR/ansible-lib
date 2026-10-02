# Changelog

All notable changes to this collection. Versions follow [Semantic Versioning](https://semver.org):
a breaking change to any role's interface (meta/argument_specs.yml) means a new major version.

## 0.1.0

- Added role `sudoers`: manage sudo rules as validated drop-in files.
- Added role `node_image` and playbook `acme.infra.node_image`: build a
  production container image of a Node.js project on Red Hat UBI 9.
