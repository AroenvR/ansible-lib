# aslib.infra.claude_vm

A VM where Claude Code may do anything, including root: `claude-dev`, on a
Linux host with KVM, such as a spare laptop. The VM is the boundary, so Claude
can run what needs root inside it, like aslib.infra's own tests (Podman,
Molecule), while the host and your network stay out of reach. A proof of concept.

```sh
ansible-playbook aslib.infra.claude_vm --ask-become-pass   # on the host; it ends with how to log in
ssh claude-dev                                             # with the block below; then, in the VM:
claude                                                     # sign in once
```

In `~/.ssh/config` of the machine that ran the playbook (from another machine,
add `ProxyJump <the host>`):

```text
Host claude-dev
    HostName 192.168.123.10
    User claude
    IdentityFile ~/.ssh/claude-dev
    UserKnownHostsFile ~/.ssh/claude-dev.known_hosts
```

## How it keeps you safe

What matters is what the VM holds and what it can reach, not whether Claude
breaks it: a broken VM is rebuilt in minutes.

| | |
|---|---|
| **Root** | Claude has sudo in the VM and nowhere else. Nothing of the host is shared with it: no folders, no keys |
| **Network** | It reaches the internet, but not the local network (the private address ranges) nor the host's own services. The rules live on the host, out of the VM's reach |
| **Secrets** | Only Claude's own login. Keep it that way: no keys to servers, no git credentials. Fetch Claude's work from the VM (below), review it, and push it yourself |
| **Reset** | `ansible-playbook aslib.infra.claude_vm_remove`, then `aslib.infra.claude_vm` again: a fresh VM |

## The host

Ubuntu (22.04, 24.04) or RHEL 9 on x86_64, with virtualization enabled in the
firmware (`/dev/kvm`), headless is fine. The playbook installs QEMU/KVM,
libvirt, virt-install and nftables where missing, and downloads Ubuntu 24.04's
cloud image once, checked against its published checksums.

Run it on the host itself, where it needs no inventory, or from another machine
with the host in an inventory; the VM is then reached through the host (SSH's
`ProxyJump`). The machine that runs it gets the key `~/.ssh/claude-dev`, which
logs in as `claude`; `claude_vm_authorized_keys` lets more keys in.

| What | Where, on the host |
|---|---|
| The VM | `claude-dev`, 2 CPUs, 4 GiB, a 40 GiB disk on top of the cloud image (`virsh list`) |
| Its network | `claude-vm`, NAT, bridge `virbr-claude`: the host is 192.168.123.1, the VM always 192.168.123.10 |
| The firewall rules | `/etc/claude-vm/firewall.nft`, a table of their own (`nft list table inet claude_vm`), loaded by `claude-vm-firewall.service` before libvirt starts the VM at boot |
| The disk and cloud image | `/var/lib/libvirt/images/` |

## In the VM

Ubuntu 24.04 with the account `claude` (sudo without a password), Podman, git,
make, Python 3.10 next to Ubuntu's 3.12 (from the deadsnakes PPA: ansible-core
2.12 and 2.14 need it for aslib.infra's test venvs) and Claude Code from
Anthropic's signed apt repository, which updates with `sudo apt upgrade`.
Without permission prompts: `claude --dangerously-skip-permissions`; the VM is
what that mode needs.

aslib.infra's tests run there as in CI:

```sh
git clone <repository> ~/src/ansible_collections/aslib/infra && cd $_
PYTHON_COMPAT=python3.10 make setup
sudo make images test-servers-2.14
```

**Getting Claude's work out**, from the host or through it:

```sh
git remote add claude-dev claude-dev:src/ansible_collections/aslib/infra
git fetch claude-dev
```

## Limitations

- A proof of concept: one VM per host, named `claude-dev`. Changing the network
  or the image needs a new VM.
- Tested on an Ubuntu 24.04 host without KVM (QEMU's emulation, with a stand-in
  for the cloud image), where the deadsnakes and Claude Code repositories were
  out of reach: not yet on real hardware, on a RHEL host or in CI.
- The firewall blocks the private address ranges. A local network on public
  addresses, or IPv6 global addresses, is not blocked.
- Claude's login stays in the VM: a prompt injection could take it. Use an
  account with a spending limit.

## Options

`ansible-doc -t role aslib.infra.claude_vm` (entry points `main`, `guest` and
`remove`).
