# acme.infra.node_image

Builds a production container image of a Node.js project, such as a NestJS
backend, with Podman. No Ansible knowledge needed: run one command from the
project root.

The image is built in two stages on Red Hat UBI 9. Native npm modules compile in
the build stage, which has gcc, g++, make and Python 3. The final image has no
compilers, runs as an unprivileged user (1001) and starts the server as soon as
the container starts.

## What your project needs

- `package.json` with a `name`, a `version` and the scripts `build` and
  `start:prod`, as every NestJS project has. The image is tagged
  `<name>:<version>` (a leading `@` is dropped) and starts with `npm run start:prod`.
- Optional, recommended: `package-lock.json`. With it dependencies are installed
  with `npm ci`, exactly as locked; without it `npm install` resolves them anew
  on every build, so two builds of the same code can differ.
- Optional: `.nvmrc` with the Node.js version, e.g. `22` or `v24.3.0`. Without it
  the build uses Node.js 24. Only the major version counts: Red Hat's image
  brings its own latest patch release.
- The server listens on port 3000 (or `process.env.PORT`) on all interfaces, as
  NestJS does by default. An app listening only on `localhost` is unreachable
  from outside the container.
- `.image/` in your `.gitignore`: that is where the result goes.

## What the build machine needs

- Podman 3.4 or newer, ansible-core and this collection. RHEL 9
  (`dnf install podman ansible-core`) and Ubuntu 22.04
  (`apt install podman ansible-core`) both work. Then install the collection as
  described in the [collection README](../../README.md#use-it-in-your-project).
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
generated `Containerfile` for reference. Load and try it, with environment
variables from a file and a host directory mounted at `/data`:

```sh
podman load --input .image/orders-api-1.4.0.tar
podman run --rm --publish 3000:3000 --env-file container.env \
  --volume /srv/orders/data:/data:Z,U orders-api:1.4.0
```

Keep `container.env` out of git: it is where settings and secrets go, and they
never become part of the image. `:Z,U` lets the app's user (1001) write to the
directory, also under SELinux on RHEL.

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
- The project's `.npmrc` applies to the install (private registries, or settings
  such as `legacy-peer-deps=true`) but is not in the final image.
- Base images are refreshed whenever the registry has newer ones (security
  fixes); with no registry access the build uses the cached ones.
- Running the image as a service that starts at boot is not part of this role.
