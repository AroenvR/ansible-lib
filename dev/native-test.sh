#!/bin/sh
# Runs every role's test scenarios with the ansible-core package an OS ships,
# after installing the release tarball the way README.md tells consumers to.
# The container plays both parts: a server (server scenarios) and a build
# machine (build_machine scenarios, which start containers of their own, hence
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
  mkdir -p /work/collections/ansible_collections/aslib/infra &&
  tar -xzf /src/$tarball -C /work/collections/ansible_collections/aslib/infra"

playbook() {
  podman exec --env ANSIBLE_COLLECTIONS_PATH=/work/collections \
    "$container" ansible-playbook -i localhost, -c local "$1"
}

for role in "$@"; do
  for scenario in server build_machine; do
    [ -d "roles/$role/molecule/$scenario" ] || continue
    dir=/src/roles/$role/molecule/$scenario
    printf '\n##### %s: %s tests, with the ansible-core and Podman of Ubuntu 22.04 #####\n\n' "$role" "$scenario"
    if [ -f "roles/$role/molecule/$scenario/prepare.yml" ]; then playbook "$dir/prepare.yml"; fi
    playbook "$dir/converge.yml"
    second_run=$(playbook "$dir/converge.yml")
    echo "$second_run"
    echo "$second_run" | grep 'changed=0 .*failed=0' >/dev/null \
      || { echo "FAIL: $role ($scenario) changed something on its second run"; exit 1; }
    playbook "$dir/verify.yml"
  done
done
