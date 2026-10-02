#!/bin/sh
# Runs every role's test scenarios with the ansible-core package an OS ships,
# after installing the release tarball the way README.md tells consumers to.
# The container plays both parts: a server (default scenarios) and a build
# machine (local scenarios, which start containers of their own, hence
# --privileged and a separate volume for Podman's storage).
# Usage: dev/native-test.sh <image> <release tarball> <role>...
set -eu
image=$1
tarball=$2
shift 2

container=$(podman run --detach --rm --privileged --systemd=always \
  --volume "$PWD:/src:ro" --volume /var/lib/containers "$image" /sbin/init)
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
  for scenario in default local; do
    [ -d "roles/$role/molecule/$scenario" ] || continue
    dir=/src/roles/$role/molecule/$scenario
    echo "=== $role ($scenario): prepare, converge, idempotence, verify"
    if [ -f "roles/$role/molecule/$scenario/prepare.yml" ]; then playbook "$dir/prepare.yml"; fi
    playbook "$dir/converge.yml"
    second_run=$(playbook "$dir/converge.yml")
    echo "$second_run"
    echo "$second_run" | grep 'changed=0 .*failed=0' >/dev/null \
      || { echo "FAIL: $role ($scenario) changed something on its second run"; exit 1; }
    playbook "$dir/verify.yml"
  done
done
