# aslib.infra.claude_code_vm

A VM where Claude Code may do anything, including root: `claude-dev`, on a
Linux host with KVM, such as a spare laptop. The VM is the boundary, so Claude
can run what needs root inside it, like aslib.infra's own tests (Podman,
Molecule), while the host and your network stay out of reach. A proof of concept.

```sh
ansible-playbook aslib.infra.claude_code_vm --ask-become-pass   # on the host; it ends with how to log in
ssh claude-dev                                             # with the block below; then, in the VM:
claude                                                     # signed in with your token, or sign in once
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
| **Network** | It reaches the internet, but not the local network (the private address ranges) nor the host's own services, except the ports you name (`claude_code_vm_host_ports`, such as GitLab's, below). The rules live on the host, out of the VM's reach |
| **Secrets** | Claude's own login (a token you give it, below, or a sign-in by hand), and a git credential of Claude's own that pushes its branches to your repository (below). Protect the branches you merge from (such as `main` and `accept`), so that only you push or merge there. No keys to servers, and none of yours |
| **Reset** | `ansible-playbook aslib.infra.claude_code_vm_remove`, then `aslib.infra.claude_code_vm` again: a fresh VM |

## The host

Ubuntu 24.04 (or newer) on x86_64 or ARM64 (aarch64, such as a Raspberry Pi
4), with virtualization enabled in the firmware (`/dev/kvm`), headless is fine.
The machine that runs the playbook needs ansible-core 2.16 or newer (Ubuntu
24.04's): the host and the VM have Python 3.12, which 2.14 does not support on
managed machines. The playbook installs QEMU/KVM, libvirt, virt-install,
xorriso (for the cloud-init CD) and nftables where missing (on ARM64 also the
UEFI firmware the VM boots with, without Secure Boot), and downloads Ubuntu
24.04's cloud image for the host's architecture once, checked against its
published checksums. The VM has the host's architecture: on a Raspberry Pi,
Claude works on ARM64, and the test images it builds are ARM64's.
Mind the memory: the VM takes 4 GiB (`claude_code_vm_memory`) of the host's, all of
it from the start. The playbook checks it fits with 1 GiB left for the host and
says what does; on a Raspberry Pi with 4 GB, `-e claude_code_vm_memory=2560`.

Run it on the host itself, where it needs no inventory, or from another machine
with the host in an inventory; the VM is then reached through the host (SSH's
`ProxyJump`). The machine that runs it gets the key `~/.ssh/claude-dev`, which
logs in as `claude`; `claude_code_vm_authorized_keys` lets more keys in. Run it as
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
Anthropic's signed apt repository. Every run of the playbook brings all of the
VM's packages up to date, Claude Code's included, and restarts the VM when
they need it ([Resizing, updates and restarts](#resizing-updates-and-restarts)).

Claude Code starts ready to work: in bypassPermissions mode, without
permission prompts (the VM is what that mode needs), without asking to trust a
folder or to confirm the mode, without its first-run setup, and signed in with
your token, if you gave one. Its policy, `/etc/claude-code/managed-settings.json`,
is [claude_code_settings](../claude_code_settings/README.md)'s, which Claude
Code's container starts from too: the permission mode, model, effort, theme,
agent teams and ultracode come from the `claude_code_settings_*` settings,
below. Claude can change it with sudo, so here it sets defaults; the VM is the
boundary. The VM's `claude` command (`/usr/local/bin/claude`, before Ubuntu's
`/usr/bin/claude`) starts Claude Code with the token and the environment
claude_code_settings asks for.

Its instructions, `/etc/claude-code/CLAUDE.md`, are aslib.infra's too
([files/CLAUDE.md](files/CLAUDE.md)), rewritten with every run: work so that an
interrupted session loses nothing (commits, a handoff file per task, memory),
and `/tmp` empties at every boot. Claude Code also reads `~/.claude/CLAUDE.md`
and each project's `CLAUDE.md`, which are yours and Claude's.

With `claude_code_skills_qa: true`, change requests go through the [qa skill
and its five expert subagents](../claude_code_skills/README.md#the-qa-skill-and-its-five-experts),
which every run installs in `/etc/claude-code/.claude/`; with `false` (the
default), a run removes them and leaves any other file there alone. With
`claude_code_skills_loop_to_delivery: true`, Claude keeps long work going by
itself until it is delivered: [loop-to-delivery](../claude_code_skills/README.md#the-loop-to-delivery-skill),
installed the same way, with its hooks in the policy. Both are off by default.

aslib.infra's tests run there as in CI (`<repository>` is the URL of the
aslib.infra repository you use):

```sh
git clone <repository> ~/src/aslib && cd $_
make setup
sudo make images test-servers-2.14
```

**Getting Claude's work out:** Claude pushes its branches to your repository
with a credential of its own (an account or a key just for Claude), and you
review them in pull or merge requests. Or, without any credential in the VM,
fetch them from the host:

```sh
git remote add claude-dev claude-dev:src/aslib
git fetch claude-dev
```

**Or a GitLab on the host** ([gitlab](../gitlab/README.md)), where Claude has
an account of its own and you review its pushes. The VM reaches only the ports
you name, at the host's address, by the names you give the host:

```yaml
claude_code_vm_host_ports: [8929, 2224]       # GitLab's HTTP and SSH
claude_code_vm_host_names: [gitlab.home.arpa]
```

Whichever server Claude pushes to, its credential belongs to an account of
Claude's own, never yours, and the branches you merge from are protected.

## Settings

What you choose for the VM lives on the host, in `/etc/claude-vm/settings.yml`
(root's, mode 0600, as it may hold Claude's token): the VM's size, network,
authorized keys, host ports and names, the token, and how Claude Code's
sessions start. The first run writes it, with each setting at the value that
run uses (its default, or what the inventory or `-e` gives) and a comment of
one line. Later runs add the settings it lacks, the same way, and never change,
remove or reorder a line that is there, your comments included.

Every run then reads it from the host, also when Ansible runs on another
machine, and checks its values as the role's options: a wrong one stops the
run, naming the setting. Its values win over the inventory's; `-e` still wins
for one run. So change a setting in the file, then run the playbook again:

```yaml
claude_code_vm_memory: 6144
claude_code_settings_theme: light
claude_code_settings_permission_mode: default   # with permission prompts
claude_code_skills_qa: true                      # the qa skill and its experts
claude_code_skills_loop_to_delivery: true        # Claude keeps long work going until it is delivered
```

The download sources (image, repositories, keys) and the debugging options
are not in it: they stay aslib.infra's, so that an update can change them. A
removal (`aslib.infra.claude_code_vm_remove`) keeps the file, so a reset keeps
your settings; to start from the defaults again, delete it first:
`sudo rm /etc/claude-vm/settings.yml`. The disk size and the network are for a
new VM, as the file's comments say; the memory and the vCPUs apply to the VM
you have, below. A setting of before 0.8.2 named `claude_code_settings_qa` in
the file, the inventory or `-e` stops the run, naming `claude_code_skills_qa`:
rename it (a run never changes a line of the file).

## Resizing, updates and restarts

A run restarts the VM in two cases. A restart ends every session in it and what
runs there, so run the playbook when that suits.

- **New memory or vCPUs.** Change `claude_code_vm_memory` or
  `claude_code_vm_vcpus` in the settings file, higher or lower, and run the
  playbook: after the check that the memory fits the host, it shuts the VM
  down cleanly, as its power button would, gives it the new values and starts
  it again. A VM that is shut off just starts with them. A VM that does not
  shut down within 5 minutes is never forced off: the run stops, says the VM
  still runs with its old values, and how to go on (shut it down from inside
  with `sudo poweroff`, then run again). Values that match change nothing and
  do not restart it.
- **Updates.** Every run brings all of the VM's packages up to date from its
  repositories (Ubuntu's, and Anthropic's for Claude Code) as `apt upgrade`
  does, so it takes as long as apt needs: new dependencies such as a new kernel
  come in, nothing is removed. When Ubuntu says the VM needs a restart (its own
  marker, `/var/run/reboot-required`, also one that unattended-upgrades left
  between runs), the run restarts it cleanly and goes on once it is back; one
  that does not come back within 15 minutes stops the run, pointing at
  `claude_code_vm_overview`. A run with nothing to upgrade and no restart
  pending changes nothing.

## Signing in

Claude Code in the VM signs in with the token you set as
`claude_code_vm_oauth_token`. Without one, you sign in by hand in the first
session. The token is what `claude setup-token` prints, on any machine with a
browser: valid for a year, for a Pro, Max, Team or Enterprise subscription. It
makes model requests on that subscription, spending its usage, and nothing
more: no Remote Control, no claude.ai connectors. Whoever has it can do the
same, so treat it as a password. Keep it in Ansible Vault:

```sh
ansible-vault encrypt_string --name claude_code_vm_oauth_token   # paste the token, then Ctrl-D twice
```

Put the output in the inventory's variables for the host (or a vars file) and
run the playbook with `--ask-vault-pass`. The first run copies it into the
settings file, where it then stays, root's only.

- No output of the run shows it, the collection's run log included
  (`no_log`). On the host it lives only where it comes from and in the
  settings file; never in the VM's cloud-init data or its CD.
- In the VM it is `/etc/claude-vm/oauth-token`: claude and root read it,
  only root changes it (claude with sudo). It is never in the policy, which
  everyone in the VM may read.
- To replace it, put the new token in the settings file (or `-e` once) and run
  the playbook again; to remove it from the VM, empty it there
  (`claude_code_vm_oauth_token: ""`). `claude setup-token` makes a new one when
  it expires.

## When the VM does not come up

Two playbooks find out why, run like the others:

```sh
ansible-playbook aslib.infra.claude_code_vm_overview --ask-become-pass       # changes nothing
ansible-playbook aslib.infra.claude_code_vm_boot_trial --ask-become-pass \
  -e claude_code_vm_trial_firmware=plain                                     # one boot, changed
```

The overview shows the host (model, kernel, virtualization packages) and the
VM: its state, firmware, TPM, disks, DHCP leases and its console's last lines.
A boot trial stops the VM, changes it as asked (other UEFI firmware, no TPM, no
CD drive), boots it from fresh UEFI variables with its console recorded in
`/var/log/libvirt/qemu/claude-dev-console.log`, and says how far it got: a
login prompt, a crash, or nothing to boot. Its changes stay:
`aslib.infra.claude_code_vm_remove`, then `aslib.infra.claude_code_vm`, bring back the
VM as it was made.

## Limitations

- A proof of concept: one VM per host, named `claude-dev`. Changing the disk
  size, the network or the image needs a new VM.
- Ubuntu hosts only. Its test (`sudo make test-vm-2.16`, which needs KVM) runs
  in CI on GitHub's x86_64 Ubuntu 24.04 runners, which have KVM. On ARM64 it
  runs on a Raspberry Pi 4 with 4 GB (Ubuntu 24.04) with
  `-e claude_code_vm_memory=2560`, checked by hand.
- An ARM64 VM boots without Secure Boot. Enforced, as libvirt would have it,
  Ubuntu's boot loader crashes on a Raspberry Pi 4; in a VM where Claude has
  root, it would protect nothing.
- The firewall blocks the private address ranges. A local network on public
  addresses, or IPv6 global addresses, is not blocked.
- Claude's login stays in the VM, the token included: a prompt injection could
  take it. Use an account with a spending limit.
- That no folder asks to be trusted rests on `CLAUDE_CODE_SANDBOXED`, which
  Claude Code reads but does not document (see
  [claude_code_settings](../claude_code_settings/README.md)): the VM's test
  starts the real Claude Code to catch a release that drops it.

## Options

`ansible-doc -t role aslib.infra.claude_code_vm` (entry points `main`, `guest`,
`remove`, and for debugging `overview` and `boot_trial`),
`ansible-doc -t role aslib.infra.claude_code_settings` for how sessions start and
`ansible-doc -t role aslib.infra.claude_code_skills` for the skills.
A setting of before 0.7.0 (`claude_vm_*`) stops the run, naming it: rename it
`claude_code_vm_*`.
