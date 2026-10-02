#!/bin/bash
#
# Environment variable utility functions for shell scripts.

#######################################
# Source all of this package's functions
#######################################
source_environment_utilities() {
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  source "$script_dir/require_env_var.sh"
  source "$script_dir/source_default_environment.sh"
  source "$script_dir/resolve_env_candidate.sh"
  source "$script_dir/source_env_file.sh"
  source "$script_dir/require_command.sh"
}
source_environment_utilities
