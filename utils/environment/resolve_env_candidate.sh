#!/bin/bash
#
# Exposes one of the environment's utility functions

#######################################
# Resolve an env file or directory candidate to an existing file path.
#
# If the candidate is a directory, tries "<dir>/.env" then
# "<dir>/.env.example".
# If the candidate is a file, returns it only when it exists.
#
# Globals:
#   None
# Arguments:
#   $1: Env file or directory path.
# Outputs:
#   Writes the resolved file path to stdout.
# Returns:
#   0 if a file was found.
#   1 otherwise.
#######################################
resolve_env_candidate() {
  local candidate="${1:-}"

  if [[ -z "${candidate}" ]]; then
    return 1
  fi

  if [[ -d "${candidate}" ]]; then
    local directory="${candidate%/}"

    if [[ -f "${directory}/.env" ]]; then
      printf '%s' "${directory}/.env"
      return 0
    elif [[ -f "${directory}/.env.example" ]]; then
      printf '%s' "${directory}/.env.example"
      return 0
    fi

    return 1
  fi

  if [[ -f "${candidate}" ]]; then
    printf '%s' "${candidate}"
    return 0
  fi

  return 1
}