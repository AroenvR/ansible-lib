#!/bin/bash
#
# Exposes one of the environment's utility functions

#######################################
# Require a command to be available on PATH.
#
# Calls error and exits if the command cannot be found. Silently continues when
# the command exists.
#
# Globals:
#   None
# Arguments:
#   $1: Command name to require.
# Outputs:
#   Writes an error message via error() when the command is missing.
# Returns:
#   0 if the command exists.
#   Exits via error() if the command is missing or no command name is provided.
#######################################
require_command() {
  local command_name="${1:-}"

  verbose "Checking if command is available: $command_name"
  require_arguments 1 "$@"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    error "Required command not found: $command_name"
  fi

  return 0
}