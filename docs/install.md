# Install aslib.infra

aslib.infra is installed on the control node, the machine that runs Ansible:
a laptop, a build machine, a pipeline's runner, or a server itself. Managed
servers need nothing of it: see [What a managed server
needs](servers.md#what-a-managed-server-needs).

## Compatibility

| | Supported |
|---|---|
| Ansible control node | The `ansible-core` package of RHEL 9.6 (2.14) or Ubuntu 24.04 (2.16), or newer |
| Managed servers | RHEL 9.6, Ubuntu 24.04. `podman_service`, `podman_overview`, `node_deploy`, `claude_code` and `gitlab`: RHEL 9.6 or newer with its Podman (5.4) |
| Image build machines | RHEL 9.6, Ubuntu 24.04, with their Podman (5.4, 4.9) |
| Other collections | None. Only `ansible.builtin` is used. |

## Get it

Each tarball holds only what runs: no tests, no dev tooling.

- **Releases** (`aslib-infra-<version>.tar.gz`, `<version>` being X.Y.Z): every
  change to main that passes CI is released with the next version, as a GitHub
  release (or in GitLab's package registry). Each comes with its SHA-256
  checksum, `aslib-infra-<version>.tar.gz.sha256`; with both in one directory,
  `sha256sum --check aslib-infra-<version>.tar.gz.sha256` checks the download.
- **Branch builds** (`aslib-infra.<branch>.<commit>.<time>.tgz`), to try out
  work in progress: the newest build of each branch is an artifact of its CI
  run (GitHub: Actions > the run > Artifacts; GitLab: the `branch-build` job's
  artifacts) for 7 days.
- **Your own build**, of any checkout of this repository, for example before CI
  has published one. From the repository root, with any ansible-core 2.14 or newer:

  ```sh
  ansible-playbook build.yml   # writes dist/aslib-infra.<branch>.<commit>.<time>.tgz
  ```

  A copy without git (an exported archive) builds too, as `dist/aslib-infra.<time>.tgz`.
  Either way, the checksum is written next to it, as `<file>.sha256`.

  CI uses the same playbook for branch builds and releases; its header explains both.

## Install it

The control node needs `ansible-core`, from its OS: `sudo dnf install
ansible-core` on RHEL, `sudo apt install ansible-core` on Ubuntu. Then install
the tarball. `--force` replaces an installed copy, also one with the same
version (branch builds carry the version of their `galaxy.yml`):

```sh
ansible-galaxy collection install --force aslib-infra-<version>.tar.gz   # or the .tgz of a branch build
ansible-galaxy collection list aslib.infra                               # shows the version installed
```

It goes to `~/.ansible/collections/` of the user who runs the command, so
install it as the user who runs the playbooks.

**Offline control node:** copy the tarball over; installing it needs no network.

A project with playbooks of its own pins the version it uses in a
`requirements.yml` instead: see [Pin aslib.infra in a
project](own-playbooks.md#pin-aslibinfra-in-a-project).

## Versions

[Semantic Versioning](https://semver.org): a breaking change to any role's
variables means a new major version (before 1.0.0, a new minor version).
[CHANGELOG.md](../CHANGELOG.md) lists what each version changed and, where a
version asks for it, what to do when upgrading ("Upgrading from ...").

To upgrade, install the newer tarball as above. A project that `node_setup` or
`claude_setup` wrote then brings aslib.infra's files in its `ansible/`
directory up to date, from that directory, keeping a changed one as
`<file>.bak` ([node_setup](../roles/node_setup/README.md),
[claude_code](../roles/claude_code/README.md#the-project)):

```sh
ansible-playbook update-playbooks.yml
```
