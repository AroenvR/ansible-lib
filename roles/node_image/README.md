# acme.infra.node_image

Builds a production container image of a Node.js project with Podman. No
Ansible knowledge needed: run one command from the project root.

The image is built in two stages on Red Hat UBI 9. Native npm modules compile in
the build stage, which has gcc, g++, make and Python 3. The final image has no
compilers, runs as an unprivileged user (1001) and starts the server as soon as
the container starts.

## What your project needs

- `package.json` with a `name` and a `version`. The image is tagged
  `<name>:<version>`; a leading `@` of a scoped name is dropped.
- `package-lock.json`. Dependencies are installed with `npm ci`.
- `.nvmrc` with the Node.js version, e.g. `24` or `v24.3.0`. Only the major
  version counts: Red Hat's image brings its own latest patch release.
- A `start` script in `package.json` (or set `node_image_command`). If there is a
  `build` script, it runs during the build.
- The server listens on `process.env.PORT` (3000 by default) on all interfaces
  (`0.0.0.0`). An app listening on `localhost` is unreachable from outside the container.
- `.image/` in your `.gitignore`: that is where the result goes.

## What the build machine needs

- Podman 4 or newer, ansible-core and this collection. On RHEL 9:
  `dnf install podman ansible-core`, then install the collection as described in
  the [collection README](../../README.md#use-it-in-your-project).
- Network access during the build to `registry.access.redhat.com` (base images),
  the npm registry, `nodejs.org` (node-gyp downloads the Node.js headers for
  native modules) and anything your dependencies download in their install
  scripts. The first two can point at internal mirrors, see Options.

## Build

From the project root:

```sh
ansible-playbook acme.infra.node_image
```

The result lands in `.image/`: the image as `<name>-<version>.tar`, plus the
generated `Containerfile` for reference. Load and try it:

```sh
podman load --input .image/orders-api-1.4.0.tar
podman run --rm --publish 3000:3000 orders-api:1.4.0
```

Running it again without changes reuses the cached build and leaves the archive alone.

## Options

The defaults fit most projects. To change one, put it in a file and pass it in:

```yaml
# image.yml
node_image_port: 3100
node_image_build_packages: [libpq-devel]   # a native module needs PostgreSQL headers
node_image_runtime_packages: [libpq]       # and the library itself at runtime
```

```sh
ansible-playbook acme.infra.node_image -e @image.yml
```

All options, with their defaults: `ansible-doc -t role acme.infra.node_image`.

## Good to know

- Never sent to the build: `.git`, `node_modules`, `.env`, `.env.*`, `*.log` and
  the output directory. Add patterns with `node_image_ignore`. The project's own
  `.dockerignore` or `.containerignore` is not used.
- `.npmrc` is available to `npm ci` (private registries) but is not in the final image.
- Base images are refreshed whenever the registry has newer ones (security
  fixes); with no registry access the build uses the cached ones.
- Running the image as a service that starts at boot is not part of this role.
