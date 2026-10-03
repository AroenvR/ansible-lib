# aslib.infra.sudoers

Manage sudo rules as drop-in files in `/etc/sudoers.d/`. Every file is checked
with `visudo` before it goes live; `/etc/sudoers` itself is never edited.

## What a server needs

- Nothing beyond the [baseline](../../README.md#what-a-managed-server-needs).
- Package repository access **only** when `sudo` is not installed yet.

## Interface

`ansible-doc -t role aslib.infra.sudoers` shows every variable (source:
[meta/argument_specs.yml](meta/argument_specs.yml)).

## Example

```yaml
- name: Let the deploy user restart the app
  hosts: app_servers
  become: true
  roles:
    - role: aslib.infra.sudoers
      vars:
        sudoers_rules:
          - name: deploy_restart_app
            who: deploy
            commands:
              - /usr/bin/systemctl restart myapp
            nopasswd: true
          - name: legacy_rule
            state: absent
```
