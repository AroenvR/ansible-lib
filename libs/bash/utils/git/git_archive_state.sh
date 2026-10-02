#!/bin/bash
#
# Exposes one of the git utility functions

#######################################
# Archive the git repository's current state.
#
# Globals:
#   None
# Arguments:
#   $1: The .git directory's absoltue (input) path
#   $2: The archive's absolute output (output) path
# Outputs:
#   TODO: document
# Returns:
#   TODO: document
#######################################
git_archive_state() {
    local git_dir="$1"
    local out_dir="$2"

    require_command "tar"
    require_arguments 2 "$@"
    require_dir "$git_dir"
    require_dir "$out_dir"

    local git_parent
    local git_name

    git_parent=$(dirname "$git_dir")
    git_name=$(basename "$git_dir")

    local branch
    local commit
    local datetime
    local archive_name
    local archive_path

    branch=$(git_branch "true")
    commit=$(git_commit_checksum)
    datetime=$(date +%Y%m%d%H%M)
    archive_name=".git.$branch.$commit.$datetime.tgz" # TODO: Support .tar.gz and .zip
    archive_path="$out_dir/$archive_name"

    info "Creating tarball of '$git_dir' at '$out_dir/' named '$archive_name'"
    tar -C "$git_parent" -czf "$archive_path" "$git_name"
}