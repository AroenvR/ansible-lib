# Documentation

The documentation of aslib.infra: guides by job, and the reference. It ships
with the collection, so these links work in an installed copy too. The landing
page is [README.md](../README.md).

## Guides

Each guide walks through one job, in order, from nothing to working, and links
to the role READMEs for every option and mechanism.

- [Install aslib.infra](install.md): compatibility, where to get a tarball,
  installing it, versions.
- [Deploy a Node.js backend](nodejs-backend.md): from project to running
  service, for backend developers without Ansible knowledge.
- [Run Claude Code on a server](claude-code.md): an always-on agent for root,
  in a rootless container.
- [A VM for Claude Code, for development](claude-vm.md): where Claude may have
  root, away from the host and the local network (a proof of concept).
- [Run a GitLab of your own](gitlab.md): GitLab CE as a rootless Podman service
  (a proof of concept).
- [What runs on a server](servers.md): see every service, the conventions they
  follow, and what a managed server needs.
- [Use the roles in your own playbooks](own-playbooks.md): pin aslib.infra in a
  project, call its roles, read their options.

## Reference

- [Reference](reference.md): the roles, the ready-made playbooks, the plugins,
  and where each role's options are.
- The role READMEs, each the reference of its role: what it does, how, and its
  options: [sudoers](../roles/sudoers/README.md),
  [node_setup](../roles/node_setup/README.md),
  [node_image](../roles/node_image/README.md),
  [node_deploy](../roles/node_deploy/README.md),
  [podman_service](../roles/podman_service/README.md),
  [podman_overview](../roles/podman_overview/README.md),
  [claude_code](../roles/claude_code/README.md),
  [claude_vm](../roles/claude_vm/README.md),
  [gitlab](../roles/gitlab/README.md).
- `ansible-doc -t role aslib.infra.<role>`: a role's options, offline.
- A project's own guide: `ansible/README.md`, which `aslib.infra.node_setup`
  and `aslib.infra.claude_setup` write into the project, for every step from
  its `ansible/` directory.
- [Status](status.md): what the tests cover, what they do not yet, and known
  limits.
- [CHANGELOG.md](../CHANGELOG.md): every change, with how to upgrade.

## For developers

In the repository only; the tarball leaves them out.

- [CONTRIBUTING.md](../CONTRIBUTING.md): setup, repository layout, make
  targets, tests, rules for library code, branches and pull requests, CI and
  releases.
- [AGENTS.md](../AGENTS.md): instructions for AI coding agents: rules,
  pitfalls, decisions, status.
