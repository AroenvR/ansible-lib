#!/bin/sh
# Reports what this CI runner offers and fails unless a job can start the Podman
# containers that the Molecule tests need. Read its log before asking an admin
# for runner changes.
set -u

echo "== Job container"
grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null || echo "unknown OS"
echo "user:   $(id)"
echo "image:  ${CI_JOB_IMAGE:-unknown}"
echo "runner: ${CI_RUNNER_DESCRIPTION:-unknown}, version ${CI_RUNNER_VERSION:-unknown}"
for tool in podman make python3 python3.10 git curl; do
  printf '  %-11s %s\n' "$tool" "$(command -v "$tool" || echo missing)"
done
grep '^CapEff' /proc/self/status
for device in /dev/fuse /dev/net/tun /run/podman/podman.sock /var/run/docker.sock; do
  if [ -e "$device" ]; then echo "  present: $device"; fi
done

echo "== Can this job start containers?"
if ! command -v podman >/dev/null 2>&1; then
  echo "FAIL: the job image has no podman. Set PODMAN_IMAGE to an image that has it."
  exit 1
fi
podman --version
podman info --format 'rootless={{.Host.Security.Rootless}} cgroup-manager={{.Host.CgroupManager}} storage={{.Store.GraphDriverName}}' || true
# Starts the job's own image (or PROBE_IMAGE), which also proves the registry is reachable.
probe_image=${PROBE_IMAGE:-${CI_JOB_IMAGE:-}}
if podman run --rm "$probe_image" true; then
  echo "OK: containers start here, so the Molecule tests can run."
else
  echo "FAIL: podman cannot start containers inside this job."
  echo "The runner has to allow nested containers, usually 'privileged = true' in its [runners.docker] section."
  exit 1
fi
