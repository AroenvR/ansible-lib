# aslib.infra.systemd_timer

Run commands on a schedule with systemd's own timers, as root or as an
account, on the host or in a rootless container of that account. A job is a
service that runs its command once and a timer that starts it on its schedule,
both named `aslib-<name>`. A job is known by its name and its user. The role
touches only the jobs it is given.

## What a server needs

- Nothing beyond the [baseline](../../docs/servers.md#what-a-managed-server-needs).
- For an account's job: the account, with its home directory. The role
  creates none.

## Interface

`ansible-doc -t role aslib.infra.systemd_timer` shows every option (source:
[meta/argument_specs.yml](meta/argument_specs.yml)). There is one,
`systemd_timer_jobs`, a list of jobs (default `[]`):

| Field | Default | What it is |
|---|---|---|
| `name` | required | Lowercase letters, digits and `-`, 64 at most |
| `command` | required to install | A line of systemd's `ExecStart`, see [The command](#the-command) |
| `schedule` | required to install | systemd's calendar syntax (`OnCalendar`), such as `hourly` or `*-*-* 04:30:00` |
| `user` | `root` | `root` (a system unit) or an existing account (a unit of the account's own systemd) |
| `container` | `""` | Run the command in this container of `user` with `podman exec`; not with `root`. The role checks only that it is a container's name, not that the container exists: a missing one makes each run fail, which the journal shows |
| `state` | `present` | `absent` removes the job |

Ansible must act as root (`become: true`). It checks every job before it changes
anything, `systemd-analyze calendar` for each schedule included, and fails
naming each wrong job and its user.

## Example

```yaml
- name: Schedule jobs
  hosts: servers
  become: true
  roles:
    - role: aslib.infra.systemd_timer
      vars:
        systemd_timer_jobs:
          - name: fstrim                 # root's, on the host
            command: /usr/sbin/fstrim --all
            schedule: weekly
          - name: dates                  # the account myapp's
            user: myapp
            command: "sh -c 'date +%%F >> $$HOME/dates.log'"
            schedule: "*-*-* 04:30:00"
          - name: old-report             # removed, if it is there
            user: myapp
            state: absent
```

## A job's life

- **Present:** the role installs or replaces both units, then starts the timer
  and enables it at boot. A new schedule restarts the timer, which runs the
  job only to catch up on a run missed while it was stopped
  (`Persistent=true`). A new command applies from the next run; a job running
  at the time finishes with the old one. A second run changes nothing.
- **Absent:** the role stops the timer and the job and removes both units, the
  link that enabled the timer and its record of the last run. A job whose
  account is gone is skipped.
- **Not listed:** left as it is, as root's systemd is shared by every playbook
  that schedules jobs. List a job as `absent` once to remove it.
- **Where:** root's units are in `/etc/systemd/system/`, an account's in
  `~/.config/systemd/user/` of its home, written, enabled and removed as the
  account. Each starts with a comment: the next run replaces it.
- **Lingering:** an account with a job gets lingering (`loginctl
  enable-linger`), so its systemd runs from boot without a login. The role
  never turns it off, also when the last job goes: the account's other
  services, such as its containers, may need it.

## The command

- It is systemd's `ExecStart` syntax, not a shell's: write `%%` for a `%` and
  `$$` for a `$`; for pipes or redirection run a shell, `sh -c '...'`.
- With `container`, the job runs `podman exec <container> <command>` as the
  account. At boot it waits for the container's service, but does not start
  it.
- A `%` systemd does not know as a specifier is a bad setting: a new job's
  timer refuses to start, so the run fails; when only the command of an
  existing job changed, the timer stays active, `verify` passes and each run
  fails. `systemd-analyze verify <unit file>` finds it.
- Unit files are readable by every account: a command must not hold a secret.
  Let it read one from a file.
- systemd never starts a job that is still running, and does not retry one
  that failed.

## A job's runs

As root (`id -u <user>` gives the UID):

```sh
journalctl _UID=<uid> -t aslib-<name>                  # what the job printed, every run; root's jobs: _UID=0
journalctl _UID=<uid> USER_UNIT=aslib-<name>.service   # systemd's own messages about an account's job
journalctl --unit aslib-<name>.service                 # root's job: systemd's messages and its output
```

Lines that a job's program sends to syslog itself (`logger`, for one) carry
their own identifier, not `aslib-<name>`.

## Entry points

- `main`: installs, changes and removes the jobs, then runs `verify`'s checks.
- `verify`: changes nothing. Checks that each job listed as present has an
  active timer with a next run, and that its account, if not root, lingers.
  Fails naming each job, what is wrong and its `journalctl` command; otherwise
  names each job's next run.

```yaml
- ansible.builtin.include_role:
    name: aslib.infra.systemd_timer
    tasks_from: verify
  vars:
    systemd_timer_jobs: "{{ my_jobs }}"
```
