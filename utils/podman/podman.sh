#!/bin/bash
#
# Podman container utility functions for shell scripts.

#######################################
# Ensure a Podman image exists locally
#
# Globals:
#   None
# Arguments:
#   $1: image reference string (e.g. "myimage:latest")
# Outputs:
#   Uses `verbose` for informational output and `error` on failure.
# Returns:
#   Exits or returns non-zero via helpers if requirements are not met.
#######################################
require_podman_image() {
  local image="${1:-}"

  verbose "Checking for required podman image: $image"
  require_arguments 1 "$@"

  require_command "podman"

  if ! podman image exists "$image" 2>/dev/null; then
    error "Required image not found: $image. Run: $0 build"
  fi
}

#######################################
# Run a command inside a temporary Podman container as privileged
#
# Globals (required environment variables):
#   IMAGE_REF           - Image reference to run (e.g. myorg/myimage:latest)
#   HOST_SHARED_DIR- Host directory to bind-mount into the container
#   CONTAINER_MOUNT_DIR - Target path inside the container for the mount
#   CONTAINER_LOCALE     - Locale string to pass into the container env
#
# Arguments:
#   Any additional arguments are treated as the command and its args to run
#   inside the container (they are forwarded to `podman run ... "$@"`).
#
# Behavior:
#   - Validates required env vars and host directory.
#   - Ensures the requested image exists locally (calls `require_podman_image`).
#   - Runs `podman run --rm` with the mount and locale env set.
#######################################
execute_podman_command() {
  verbose "Executing command in podman container"
  require_arguments 1 "$@"

  require_env_var "IMAGE_REF"
  debug "Executing command in podman container: $IMAGE_REF"

  require_env_var "HOST_SHARED_DIR"
  require_env_var "CONTAINER_LOCALE"
  require_env_var "CONTAINER_MOUNT_DIR"

  require_dir "$HOST_SHARED_DIR"
  require_podman_image "$IMAGE_REF"

  podman run --rm \
    --privileged \
    --env "CONTAINER_LOCALE=$CONTAINER_LOCALE" \
    -v "$HOST_SHARED_DIR:$CONTAINER_MOUNT_DIR:Z" \
    "$IMAGE_REF" \
    "$@"
}