# Use the roles in your own playbooks

For Ansible users who write playbooks of their own: aslib.infra's roles are a
library, called like any other role. Without playbooks of your own, the
[ready-made playbooks](reference.md#ready-made-playbooks) do the same jobs.

## Pin aslib.infra in a project

A project that writes its own playbooks pins aslib.infra in a `requirements.yml`
(`<repository>` is the URL of the aslib.infra repository you use):

```yaml
collections:
  # A release on GitHub. From GitLab's package registry it is:
  # https://<gitlab>/api/v4/projects/<id>/packages/generic/aslib-infra/<version>/aslib-infra-<version>.tar.gz
  - name: <repository>/releases/download/v<version>/aslib-infra-<version>.tar.gz
    type: url
```

`ansible-galaxy collection install -r requirements.yml` installs it. To use a
tarball file instead, such as a branch build or your own build, or a release
downloaded from a private repository (`gh release download v<version> --repo
<repository>`, or `curl --header "PRIVATE-TOKEN: ..."` on GitLab):

```yaml
collections:
  - name: ./aslib-infra-<version>.tar.gz
    type: file
```

Where each kind of tarball comes from: [Get it](install.md#get-it).

## Call a role

Call a role by its full name, `aslib.infra.<role>`: under `roles:`, or with
`ansible.builtin.import_role` in `tasks:`. A role with more than one entry point
takes the others with `tasks_from:`, such as podman_service's `restart`,
`remove` and `verify`. Plays to start from: the examples in the READMEs of
[sudoers](../roles/sudoers/README.md#example),
[podman_service](../roles/podman_service/README.md) and
[podman_overview](../roles/podman_overview/README.md#in-a-playbook), and the
ready-made playbooks in [playbooks/](../playbooks/), which only call roles,
such as [node_restart.yml](../playbooks/node_restart.yml). The list of
roles, and what each needs: [Reference](reference.md#roles).

## Options of a role

Every role documents its variables; read them offline with
`ansible-doc -t role aslib.infra.<role>`:

```sh
ansible-doc -t role -l aslib.infra                          # every role, with its entry points
ansible-doc -t role aslib.infra.podman_service              # one role, every entry point
ansible-doc -t role -e restart aslib.infra.podman_service   # one entry point
```

The same options are in each role's `meta/argument_specs.yml`, with the
defaults of its `defaults/main.yml`. They are aslib.infra's interface: a
breaking change to one means a new major version ([Versions](install.md#versions)).
