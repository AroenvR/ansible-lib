# Status

What aslib.infra's tests prove, what they do not prove yet, and its known
limits. The changes of each version are in [CHANGELOG.md](../CHANGELOG.md).

## Tested on every change

In CI:

- every role but claude_vm with ansible-core 2.14 and 2.16, on test containers
  that mimic default RHEL 9.6 and Ubuntu 24.04 installs, reached over SSH as
  root, as Ansible reaches a real server; and the roles that support Ubuntu also
  with the ansible-core 2.16.3 and Podman 4.9 packages of Ubuntu 24.04 itself;
- node_image with NestJS 10, 11 and 12 and NestJS's default branch;
- a service's deploy, update, overview, removal and redeploy as another
  account, on a RHEL 9.6 test container, next to Claude Code (with a stand-in for
  it) on the same server: separate accounts and UIDs, the shared zone both ways,
  root running Claude Code, its read-only policy, and its removal; podman_service's
  checks after every deploy and restart, and the Node.js service's health check
  getting an app that answers with server errors restarted; a private file in the
  shared zone staying private, a replaced README caught by its checksum and put
  back by the next deploy, and Claude Code's 4 GiB memory limit;
- the Claude Code project's setup, update and real image build, with every
  package up to date;
- GitLab 19.4.1, deployed and used as a person would: an account and token, a
  private project, pushes and clones over HTTP and SSH, a fork, its settings, a
  restart, and a removal and new deploy on the data it left;
- claude_vm, with ansible-core 2.16 on an x86_64 Ubuntu 24.04 host with KVM
  (GitHub's runners): the VM created and set up, a hard reset survived, logged in
  as claude with sudo, Podman, Python 3.11 and Claude Code there, the internet
  reachable but not the local network nor the host's services, apart from the
  port it is given, and a second run that changes nothing.

## Not tested yet

- a real RHEL server or VM: the test servers are containers on the machine that
  runs the tests, sharing its kernel. They run without SELinux, and only a RHEL
  server with SELinux enforcing proves the relabelling (`:Z`) of the service's
  directory;
- a deploy as an account that uses sudo: the tests connect as root;
- claude_vm on an ARM64 host in CI: it runs on a Raspberry Pi 4 (Ubuntu 24.04),
  checked by hand;
- claude_vm's firewall rules after a reboot of the host: CI resets the VM, but
  never reboots the host;
- GitLab CI: `.gitlab-ci.yml` is written but has not run.

## Known limits and open work

- A service with a port must answer HTTP on it: that is how the deploy knows it
  started. One without a port (Claude Code) counts as started once it runs.
- The [shared zone](../roles/podman_service/README.md#the-shared-zone) lets
  every service change what any other wrote there; who writes what is up to the
  apps.
- To review for security: how a pipeline gets `container.env` to the deploy (a
  secret variable written to a file, see "In a pipeline" in a Node.js project's
  guide, `ansible/README.md`, [its template](../roles/node_setup/templates/README.md.j2)),
  and the project's `.npmrc`, which the build stage copies
  in: it stays in the layers of the build stage's image (`<name>:build`, the
  build machine's cache), though not in the image that is deployed.
