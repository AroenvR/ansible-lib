#!/bin/bash
#
# Utility library aggregator that sources additional modules.

#######################################
# Require an exact number of positional arguments
#
# Globals:
#   None
# Arguments:
#   $1: Expected number of positional arguments.
#   $@: The positional arguments supplied to the caller (used for count).
# Outputs:
#   On mismatch prints a timestamped error to stderr.
# Returns:
#   Exits with status 1 on mismatch; returns 0 when the argument count matches.
#######################################
require_arguments() {
  local amount="$1"
  shift

  if [ "$#" -lt "$amount" ]; then
    printf '%s %s - %s: %s\n' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        "ERROR" \
        "UTILS_SOURCE_SCRIPT" \
        "Invalid number of arguments provided; Expected at least $amount arguments but got $#" >&2

    exit 1
  fi
}

# Define this script's absolute path for easier down-sourcing.
UTILS_SOURCE_SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Down-source logging utilities (source first, so down-stream scripts can utilize it).
. "$UTILS_SOURCE_SCRIPT_PATH/logging/logging.sh"

# Down-source environment utilities.
. "$UTILS_SOURCE_SCRIPT_PATH/environment/environment.sh"

# Down-source file management utilities.
. "$UTILS_SOURCE_SCRIPT_PATH/file_management/file_management.sh"

# Down-source podman utilities.
. "$UTILS_SOURCE_SCRIPT_PATH/podman/podman.sh"

#######################################
# Execute a command from a different directory.
# Globals:
#   None
# Arguments:
#   $1: Directory to execute command from.
#   $@: Command and its arguments to execute.
# Outputs:
#   Outputs from the executed command.
# Returns:
#   Exit status of the executed command.
#######################################
run_in_dir() {
  local dir="$1"
  require_dir "$dir"

  shift

  (
    cd "$dir" || {
      error "Could not cd into $dir"
    }

    "$@"
  )
}