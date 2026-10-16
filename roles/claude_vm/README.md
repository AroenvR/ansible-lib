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
| **Network** | It reaches the internet, but not the local network (the private address ranges) nor the host's own services, except the ports you name (`claude_vm_host_ports`, such as GitLab's, below). The rules live on the host, out of the VM's reach |
| **Secrets** | Only Claude's own login. Keep it that way: no keys to servers, no git credentials. Fetch Claude's work from the VM (below), review it, and push it yourself |
| **Reset** | `ansible-playbook aslib.infra.claude_vm_remove`, then `aslib.infra.claude_vm` again: a fresh VM |

## The host

Ubuntu 24.04 or RHEL 9.6 (or newer) on x86_64 or ARM64 (aarch64, such as a
Raspberry Pi 5), with virtualization enabled in the firmware (`/dev/kvm`),
headless is fine. The playbook installs QEMU/KVM, libvirt, virt-install,
xorriso (for the cloud-init CD) and nftables where missing (on ARM64 also the
UEFI firmware the VM boots with, without Secure Boot), and downloads Ubuntu
24.04's cloud image for the host's architecture once, checked against its
published checksums. The VM has the host's architecture: on a Raspberry Pi,
Claude works on ARM64, and the test images it builds are ARM64's.
Mind the memory: the VM takes 4 GiB (`claude_vm_memory`) of the host's, all of
it from the start. The playbook checks it fits with 1 GiB left for the host and
says what does; on a Raspberry Pi with 4 GB, `-e claude_vm_memory=2560`.

Run it on the host itself, where it needs no inventory, or from another machine
with the host in an inventory; the VM is then reached through the host (SSH's
`ProxyJump`). The machine that runs it gets the key `~/.ssh/claude-dev`, which
logs in as `claude`; `claude_vm_authorized_keys` lets more keys in. Run it as
yourself with `--ask-become-pass`, not with `sudo`: the key goes into the home
of whoever runs `ansible-playbook`, root's with `sudo`.

| What | Where, on the host |
|---|---|
| The VM | `claude-dev`, 2 CPUs, 4 GiB, a 40 GiB disk on top of the cloud image (`virsh list`) |
| Its network | `claude-vm`, NAT, bridge `virbr-claude`: the host is 192.168.123.1, the VM always 192.168.123.10 |
| The firewall rules | `/etc/claude-vm/firewall.nft`, a table of their own (`nft list table inet claude_vm`), loaded by `claude-vm-firewall.service` before libvirt starts the VM at boot |
| The disk, cloud image and cloud-init CD | `/var/lib/libvirt/images/` |

## In the VM

Ubuntu 24.04 with the account `claude` (sudo without a password), Podman, git,
make, Python 3.11 next to Ubuntu's 3.12 (from the deadsnakes PPA: aslib.infra's
test venvs run ansible-core 2.14 on it, as RHEL 9.6 does) and Claude Code from
Anthropic's signed apt repository, which updates with `sudo apt upgrade`.
Without permission prompts: `claude --dangerously-skip-permissions`; the VM is
what that mode needs.

Claude Code's policy, `/etc/claude-code/managed-settings.json`, is aslib.infra's
base, the one Claude Code's container starts from too
([claude_code's managed-settings.json](../claude_code/files/managed-settings.json)):
change that file, and both get it with their next run. Claude can change it with
sudo, so here it sets defaults; the VM is the boundary.

aslib.infra's tests run there as in CI (`<repository>` is the URL of the
aslib.infra repository you use):

```sh
git clone <repository> ~/src/aslib && cd $_
make setup
sudo make images test-servers-2.14
```

**Getting Claude's work out**, from the host or through it:

```sh
git remote add claude-dev claude-dev:src/aslib
git fetch claude-dev
```

**Or a GitLab on the host** ([gitlab](../gitlab/README.md)), where Claude has
an account of its own and you review its pushes. The VM reaches only the ports
you name, at the host's address, by the names you give the host:

```yaml
claude_vm_host_ports: [8929, 2224]       # GitLab's HTTP and SSH
claude_vm_host_names: [gitlab.home.arpa]
```

Claude's token for that account is a git credential in the VM after all: give
it to Claude's own account only, never yours.

## When the VM does not come up

Two playbooks find out why, run like the others:

```sh
ansible-playbook aslib.infra.claude_vm_overview --ask-become-pass       # changes nothing
ansible-playbook aslib.infra.claude_vm_boot_trial --ask-become-pass \
  -e claude_vm_trial_firmware=plain                                     # one boot, changed
```

The overview shows the host (model, kernel, virtualization packages) and the
VM: its state, firmware, TPM, disks, DHCP leases and its console's last lines.
A boot trial stops the VM, changes it as asked (other UEFI firmware, no TPM, no
CD drive), boots it from fresh UEFI variables with its console recorded in
`/var/log/libvirt/qemu/claude-dev-console.log`, and says how far it got: a
login prompt, a crash, or nothing to boot. Its changes stay:
`aslib.infra.claude_vm_remove`, then `aslib.infra.claude_vm`, bring back the
VM as it was made.

## Limitations

- A proof of concept: one VM per host, named `claude-dev`. Changing the network
  or the image needs a new VM.
- Runs on a Raspberry Pi 4 with 4 GB (Ubuntu 24.04, ARM64, KVM) with
  `-e claude_vm_memory=2560`. Its test needs KVM (`sudo make test-vm-2.14`):
  it ran on an Ubuntu 24.04 x86_64 host without KVM only in a changed form
  (QEMU's emulation, a stand-in for the cloud image, without the deadsnakes and
  Claude Code repositories); not yet on an x86_64 host with KVM, a RHEL host or
  in CI.
- An ARM64 VM boots without Secure Boot. Enforced, as libvirt would have it,
  Ubuntu's boot loader crashes on a Raspberry Pi 4; in a VM where Claude has
  root, it would protect nothing.
- The firewall blocks the private address ranges. A local network on public
  addresses, or IPv6 global addresses, is not blocked.
- Claude's login stays in the VM: a prompt injection could take it. Use an
  account with a spending limit.

## Options

`ansible-doc -t role aslib.infra.claude_vm` (entry points `main`, `guest`,
`remove`, and for debugging `overview` and `boot_trial`).
