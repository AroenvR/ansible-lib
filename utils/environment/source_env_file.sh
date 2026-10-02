#!/bin/bash
#
# Exposes one of the environment's utility functions

#######################################
# Safely source an environment file into the current shell, exporting
# every variable it defines.
#
# Sourcing executes arbitrary shell code, so as a guardrail this only
# accepts files whose final path component starts with ".env" (for
# example ".env", ".env.example", ...); anything after the
# ".env" prefix is allowed. The path is sourced exactly as provided --
# it is not rewritten, resolved, or relocated. A missing file is not an
# error: the caller simply proceeds with its defaults.
#
# Example sourcing with environment variable, .env fallback and .env.example as final fallback:
# ```bash
#   ENV_FILE_LOCATION="$(resolve_env_file "${ENV_FILE:-}" "${SCRIPT_DIR}/.env" "${SCRIPT_DIR}/.env.example")"
#   source_env_file "${ENV_FILE_LOCATION}"
# ```
#
# Globals:
#   LOG_PREFIX
# Arguments:
#   $1: Path to the environment file to source.
# Outputs:
#   Writes status messages to STDOUT (via log); writes misuse messages
#   to STDERR (via error).
# Returns:
#   0 if the file was sourced, or was absent and defaults are used.
#   Exits 1 (via error) if no path is supplied, or the final path
#   component does not start with ".env".
#######################################
source_env_file() {
  local env_file="${1:-}"

  info "Sourcing environment variables from: $env_file"
  require_arguments 1 "$@"

  # Guardrail: refuse to source anything whose filename does not start
  # with ".env", since sourcing runs arbitrary code.
  local filename="${env_file##*/}"
  if [[ "${filename}" != .env* ]]; then
    error "Refusing to source '${env_file}'; filename must start with '.env'"
  fi

  if [[ ! -f "${env_file}" ]]; then
    warn "No env file found at ${env_file}"
    return 0
  fi

  set -a
  # shellcheck source=/dev/null
  source "${env_file}"
  set +a
}