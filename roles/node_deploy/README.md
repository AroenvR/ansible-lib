# acme.infra.node_deploy

Deploys a Node.js project's image to servers as a rootless Podman service that
starts at boot. No Ansible knowledge needed: run one command from the project
root, after [node_setup](../node_setup/README.md) and [node_image](../node_image/README.md):

```sh
ansible-playbook acme.infra.node_deploy -i deploy/inventory.yml
```

On every server in the inventory, as the account Ansible connects with, it:

1. lets the account run services while nobody is logged in (`loginctl enable-linger`),
   so the service starts at boot;
2. copies the image archive of the version in package.json
   (`.image/<name>-<version>.tar`) and loads it into Podman;
3. copies `deploy/container.env` to `~/<name>/container.env`;
4. installs `deploy/<name>.container` as `~/.config/containers/systemd/<name>.container`,
   with `Image=` set to that version;
5. starts the service `<name>`, or restarts it when the image, the settings or
   the Quadlet file changed. Running it again without changes changes nothing.

## What a server needs

Set up once by an administrator:

- RHEL 9.2 or newer with Podman 4.4 or newer, which brings Quadlet: `sudo dnf install podman`.
- The account the service runs as: an ordinary user, no sudo needed.
- polkit, which lets that account enable lingering for itself. Without it, an
  administrator runs `sudo loginctl enable-linger <account>` once.
- SSH access for that account (not needed when deploying to `localhost`).
- For other machines to reach the service, its port (`PublishPort=` in the
  Quadlet file) open in the firewall: `sudo firewall-cmd --permanent --add-port=3000/tcp && sudo firewall-cmd --reload`.

No network access: the image comes from the project, not from a registry.

## Options

`ansible-doc -t role acme.infra.node_deploy`.
