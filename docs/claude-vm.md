# A VM for Claude Code, for development

For development where Claude needs root (aslib.infra's own tests, for one:
Podman and Molecule), a VM of its own on a host with KVM, such as a spare
laptop, keeps that root away from the host and the local network. Claude has
sudo in the VM, `claude-dev`, and nowhere else; the VM reaches the internet,
but not the local network. A proof of concept. [How it keeps you
safe](../roles/claude_vm/README.md#how-it-keeps-you-safe).

## Before you start

- **A host**: Ubuntu 24.04 (or newer) on x86_64 or ARM64, such as a
  Raspberry Pi, with virtualization enabled in the firmware (`/dev/kvm`);
  headless is fine. The VM takes 4 GiB of the host's memory from the start
  ([The host](../roles/claude_vm/README.md#the-host)).
- **The machine that runs Ansible**: the host itself, or another machine with
  the host in an inventory. ansible-core 2.16 or newer (Ubuntu 24.04's; 2.14
  does not support the Python 3.12 of the host and the VM) and aslib.infra on it ([Install
  aslib.infra](install.md)), and sudo on the host.
- **Internet access** for the host and the VM: packages, Ubuntu's cloud image,
  Anthropic's and the deadsnakes repositories.
- **An account to sign in to Claude Code with**, best one with a spending
  limit: Claude's login stays in the VM
  ([Limitations](../roles/claude_vm/README.md#limitations)).

## Create the VM

On the host, or from the machine with the host in its inventory:

```sh
ansible-playbook aslib.infra.claude_vm --ask-become-pass   # ends with how to log in
```

Run it as yourself with `--ask-become-pass`, not with `sudo`: the key that
logs in to the VM, `~/.ssh/claude-dev`, goes into the home of whoever runs
`ansible-playbook`. It installs what the host lacks, creates the VM and sets it
up ([In the VM](../roles/claude_vm/README.md#in-the-vm)). It checks first that
the VM fits in the host's memory and says what does: on a Raspberry Pi with
4 GB, add `-e claude_vm_memory=2560`.

It ends with the command that logs in. For `ssh claude-dev`, add the `Host
claude-dev` block of [claude_vm](../roles/claude_vm/README.md) to the
`~/.ssh/config` of the machine that ran the playbook (on another machine than
the host, with `ProxyJump <the host>`).

## Work in it

```sh
ssh claude-dev
claude                                   # sign in once
claude --dangerously-skip-permissions    # without permission prompts: the VM is what that mode needs
```

To work on aslib.infra there, clone it in the VM (`<repository>` is the URL of
the aslib.infra repository you use) and run its tests as CI does; the rest is
in its CONTRIBUTING.md ([Setup](../CONTRIBUTING.md#setup), in the repository
only):

```sh
git clone <repository> ~/src/aslib && cd $_
make setup
sudo make images test-servers-2.14
```

Claude's work leaves the VM on branches. Give Claude a git credential of its
own (an account or a key just for Claude, never yours) to push them to your
repository, protect the branches you merge from, such as `main`, and review
Claude's in pull or merge requests. No keys to servers. Or, with no credential
in the VM, fetch them from the host:

```sh
git remote add claude-dev claude-dev:src/aslib
git fetch claude-dev
```

Or give Claude an account of its own on a GitLab on the host: [Run a GitLab of
your own](gitlab.md). For a fresh VM, `ansible-playbook
aslib.infra.claude_vm_remove --ask-become-pass`, then `aslib.infra.claude_vm`
again.

## When it does not come up

Two playbooks find out why, run like the others:

```sh
ansible-playbook aslib.infra.claude_vm_overview --ask-become-pass       # changes nothing
ansible-playbook aslib.infra.claude_vm_boot_trial --ask-become-pass \
  -e claude_vm_trial_firmware=plain                                     # one boot, changed
```

The overview shows the host and the VM, with its console's last lines; a boot
trial boots the VM once in a changed form and says how far it got. What each
shows and changes: [When the VM does not come
up](../roles/claude_vm/README.md#when-the-vm-does-not-come-up). A trial's
changes stay: remove the VM and create it again to get it as it was made.

## Next

- [claude_vm](../roles/claude_vm/README.md): the host, the VM, its network and
  firewall, its limitations and options.
- [Run a GitLab of your own](gitlab.md), on the VM's host, for Claude's
  pushes.
- [CONTRIBUTING.md](../CONTRIBUTING.md), in the repository only: developing
  aslib.infra.
- [Run Claude Code on a server](claude-code.md): an always-on agent for root on
  a server, in a container rather than a VM.
