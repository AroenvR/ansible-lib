#!/bin/bash
#
# Exposes one of the environment's utility functions

#######################################
# Require an environment variable to be set.
# Globals:
#   None
# Arguments:
#   $1: Environment variable name to check.
# Outputs:
#   None
# Returns:
#   0 if the environment variable is set.
#   1 if the environment variable is not set.
#######################################
require_env_var() {
  local var_name="${1:-}"

  verbose "Checking required environment variable: '$var_name'"
  require_arguments 1 "$@"

  if [[ -z "${!var_name:-}" ]]; then
    error "Environment variable '\$$var_name' must be set to continue"
  fi
}