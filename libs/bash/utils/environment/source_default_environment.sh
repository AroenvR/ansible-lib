#!/bin/bash
#
# Exposes one of the environment's utility functions

#######################################
# Safely source a dot env configuration file.
#
# If called with no argument, ENV_FILE is checked first. If ENV_FILE is not
# set or does not resolve to an existing env file, the function logs a
# verbose message and continues.
#
# If called with an argument, ENV_FILE is still checked first and the
# argument is used only if ENV_FILE does not resolve to a valid file.
#
# For either ENV_FILE or the provided argument:
#   * If the path is a directory, the function first tries
#     "<path>/.env" and then "<path>/.env.example".
#   * If the path is already a file, it is sourced directly.
#
# Globals:
#   ENV_FILE
# Arguments:
#   $1: Optional env file or directory path to source.
# Outputs:
#   Writes verbose or warning messages if no env file is found.
# Returns:
#   0 if a valid env file was sourced or no env file was usable.
#######################################
source_default_environment() {
  verbose "Sourcing default environment variables"

  local requested_env_file="${1:-}"
  local resolved_env_file=""

  if [[ -n "${ENV_FILE:-}" ]]; then
    if resolved_env_file="$(resolve_env_candidate "${ENV_FILE}")"; then
      source_env_file "${resolved_env_file}"
      return 0
    fi

    warn "ENV_FILE is set to '${ENV_FILE}', but no env file was found there"
  fi

  if [[ -n "${requested_env_file}" ]]; then
    if resolved_env_file="$(resolve_env_candidate "${requested_env_file}")"; then
      source_env_file "${resolved_env_file}"
      return 0
    fi

    warn "No env file found at provided path '${requested_env_file}'"
  fi

  verbose "No environments to source were found"
}