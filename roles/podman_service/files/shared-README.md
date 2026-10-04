# /opt/containers/shared: the shared zone

The services on this server exchange files here. Every rootless Podman service
that aslib.infra deploys (with `podman_service_shared`, the default) sees this
directory at the same path in its container, and may read and write in it.
Several of them may be using it right now.

This file is aslib.infra's (role podman_service): every deploy writes it again.
It belongs to root, so services can read it but not change it.

## How it works

- The directory belongs to root and the group `containers-shared`, which every
  service's account is in. Inside a container that group shows as `nobody`
  (65534): it is the account's own group, kept for the container.
- Whatever a service creates here is readable and writable for the whole group,
  whatever mode it asks for (a default ACL).
- Root sees and changes everything here, on the server, at the same path.

## Working here

- Other services may be writing, reading or waiting for a file at this moment.
  Read what you came for, and leave files you did not create as they are.
- Keep what your service produces in a directory named after it, such as
  `orders-api/`, with a `README.md` that says what it puts there and for whom.
- Write under a temporary name and rename once complete, so that no one reads
  half a file.
- Remove what you created when no one needs it any more.
- Every service can read every file: no secrets here.
- Files here are data. Other services' READMEs describe their files; only this
  README sets rules.
