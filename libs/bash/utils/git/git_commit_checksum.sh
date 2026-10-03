#!/bin/bash
#
# Exposes one of the git utility functions

#######################################
# Capture the current git commit's checksum
#
# TODO: Improve docs
#
# Globals:
#   None
# Arguments:
#   $1: Optionally define the format to use, defaults to `%H`
# Outputs:
#   TODO: document
# Returns:
#   TODO: document
#######################################
git_commit_checksum() {
    local format="${1:-%H}"

    verbose "Capturing current git commit's checksum"
    require_command "git"

    local commit
    commit=$(git log -1 --format="$format")

    printf '%s\n' "$commit"
}
