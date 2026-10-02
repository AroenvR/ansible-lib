#!/bin/bash
#
# Git utility functions for shell scripts.

#######################################
# Source all of this package's functions
#######################################
source_git_utilities() {
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  source "$script_dir/git_branch.sh" 
  source "$script_dir/git_commit_checksum.sh"
  source "$script_dir/git_archive_state.sh"
}
source_git_utilities
