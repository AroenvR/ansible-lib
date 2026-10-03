#!/bin/bash
#
# Exposes one of the git utility functions

#######################################
# Capture the current git branch's name
#
# TODO: Improve docs
#
# Globals:
#   None
# Arguments:
#   $1: Whether the output should replace slashes with another symbol
#   $2: Replacement symbol if replacement is enabled, defaults to `.`
# Outputs:
#   TODO: document
# Returns:
#   TODO: document
#######################################
git_branch() {
    local replace="${1:-0}"
    local replace_with="${2:-.}"

    verbose "Capturing current git branch"
    require_command "git"

    local branch
    branch=$(git branch --show-current)
    
    if [[ "$replace" == "1" || "$replace" == "true" ]]; then
        branch="${branch//\//$replace_with}"
    fi

    printf '%s\n' "$branch"
}
