# acme.infra.node_image

Builds a production container image of a Node.js project, such as a NestJS
backend, with Podman. No Ansible knowledge needed: run one command from the
project's `ansible/` directory (see [node_setup](../node_setup/README.md)).

The image is built in two stages on Red Hat UBI 9. Native npm modules compile in
the build stage, which has gcc, g++, make and Python 3. The final image has no
compilers, runs as an unprivileged user (1001) that cannot change the app's
files, and starts the server as soon as the container starts. Inside it, the
app lives in `/opt/app-root/src`, where Red Hat's Node.js images keep it.

## What your project needs

- `package.json` with a `name`, a `version` and the scripts `build` and
  `start:prod`, as every NestJS project has. The image is tagged
  `<name>:<version>` (a leading `@` is dropped) and starts with `npm run start:prod`.
- Optional, recommended: `package-lock.json`. With it dependencies are installed
  with `npm ci`, exactly as locked; without it `npm install` resolves them anew
  on every build, so two builds of the same code can differ.
- Optional: `.nvmrc` with the Node.js version, e.g. `22`, `v24.3.0`, `lts/*` or
  `lts/krypton`. Without it, and for `lts/*`, the build uses Node.js 24, the
  newest LTS release Red Hat publishes images for. Only the major version counts:
  Red Hat's image brings its own latest patch release.
- The server listens on port 3000 (or `process.env.PORT`) on all interfaces, as
  NestJS does by default. An app listening only on `localhost` is unreachable
  from outside the container.
- Everything the app imports at runtime in `dependencies`. The build installs
  `devDependencies` too, for `npm run build`, then removes them; a module used
  at runtime but listed only there (or only installed as another package's
  dependency) makes the app fail with "Cannot find module". `npm ci --omit=dev
  && npm run start:prod` shows that on your own machine.

## What the build machine needs

- Podman 3.4 or newer, ansible-core and this collection. RHEL 9
  (`dnf install podman ansible-core`) and Ubuntu 22.04
  (`apt install podman ansible-core`) both work. Then install the collection as
  described in the [collection README](../../README.md#get-it).
- Network access during the build to `registry.access.redhat.com` (base images),
  the npm registry, `nodejs.org` (node-gyp downloads the Node.js headers for
  native modules) and anything your dependencies download in their install
  scripts. The first two can point at internal mirrors, see Options.

## Build

From the project's `ansible/` directory:

```sh
ansible-playbook image.yml    # or: ansible-playbook acme.infra.node_image
```

The result lands in `ansible/images/`, which keeps itself out of git: the image
as `<name>-<version>.tar`, plus the generated `Containerfile` for reference. The
image is labelled with the version and the git commit it was built from
(`org.opencontainers.image.version`, `org.opencontainers.image.revision`). To
deploy it, see [node_deploy](../node_deploy/README.md). To just try it, with
environment variables from a file, the production config and a host directory
mounted at `/data`:

```sh
podman load --input images/orders-api-1.4.0.tar
podman run --rm --publish 127.0.0.1:3000:3000 --env-file container.env \
  --volume ../config/production:/opt/app-root/src/config:ro,Z \
  --volume /tmp/orders-data:/data:Z,U orders-api:1.4.0
```

`:Z,U` lets the app's user (1001) write to the directory, also under SELinux on
RHEL; note that `U` changes the owner of everything in it.

Running it again without changes reuses the cached build and leaves the archive alone.

## Options

The defaults fit most projects. To change one, set it in the project's
`ansible/group_vars/all.yml`:

```yaml
node_image_build_packages: [libpq-devel]   # a native module needs PostgreSQL headers
node_image_runtime_packages: [libpq]       # and the library itself at runtime
```

All options, with their defaults: `ansible-doc -t role acme.infra.node_image`.

## Good to know

- Never sent to the build: `.git`, `node_modules`, `.env`, `.env.*`, `*.log`,
  the `ansible/` directory (so `container.env` can never end up in an image),
  `config/` (the deploy provides the production config, see
  [node_deploy](../node_deploy/README.md)) and the output directory. Add patterns with `node_image_ignore`. The role passes
  its own ignore file to Podman (`--ignorefile`); the project's `.dockerignore`
  or `.containerignore` is not used.
- The project's `.npmrc` applies to the install (private registries, or settings
  such as `legacy-peer-deps=true`) but is not in the final image, which holds
  only the runtime stage. The build stage stays in the build machine's Podman cache.
- The base images are referenced by tag, not by digest, and refreshed whenever
  the registry has newer ones, so every build picks up Red Hat's security fixes.
  With no registry access the build uses the cached ones.
- Running the image as a service that starts at boot: [node_deploy](../node_deploy/README.md).
