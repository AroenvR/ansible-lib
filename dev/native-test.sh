#!/bin/sh
# Runs every role's test scenario with the ansible-core package an OS ships,
# after installing the release tarball the way README.md tells consumers to.
# Usage: dev/native-test.sh <image> <release tarball> <role>...
set -eu
image=$1
tarball=$2
shift 2

container=$(podman run --detach --rm --systemd=always --volume "$PWD:/src:ro" "$image" /sbin/init)
trap 'podman stop "$container" >/dev/null' EXIT
podman exec "$container" systemctl is-system-running --wait >/dev/null || true

podman exec "$container" sh -c "
  mkdir -p /work/collections/ansible_collections/acme/infra &&
  tar -xzf /src/$tarball -C /work/collections/ansible_collections/acme/infra"

playbook() {
  podman exec --env ANSIBLE_COLLECTIONS_PATH=/work/collections \
    "$container" ansible-playbook -i localhost, -c local "$1"
}

for role in "$@"; do
  scenario=/src/roles/$role/molecule/default
  echo "=== $role: prepare, converge, idempotence, verify"
  if podman exec "$container" test -f "$scenario/prepare.yml"; then playbook "$scenario/prepare.yml"; fi
  playbook "$scenario/converge.yml"
  second_run=$(playbook "$scenario/converge.yml")
  echo "$second_run"
  echo "$second_run" | grep 'changed=0 .*failed=0' >/dev/null \
    || { echo "FAIL: $role changed something on its second run"; exit 1; }
  playbook "$scenario/verify.yml"
done
