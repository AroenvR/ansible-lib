#!/bin/bash
#
# File management utility functions for shell scripts.

#######################################
# Ensure a directory exists before continuing.
# Globals:
#   None
# Arguments:
#   $1: Directory path to check.
# Outputs:
#   None
# Returns:
#   0 if the directory exists.
#   1 if the directory is not found.
#######################################
require_dir() {
  local dir="${1:-}"

  verbose "Checking if required directory exists: $dir"
  require_arguments 1 "$@"

  if [[ ! -d "$dir" ]]; then
    error "Expected directory not found: $dir"
  fi
}

#######################################
# Ensure a directory exists, creating it if necessary.
# Globals:
#   None
# Arguments:
#   $1: Directory path to check/create.
# Outputs:
#   Writes log messages to stdout.
# Returns:
#   0 on success.
#   1 if path exists but is not a directory.
#######################################
ensure_dir() {
  local dir="${1:-}"

  verbose "Ensuring directory: $dir"
  require_arguments 1 "$@"


  if [[ -d "$dir" ]]; then
    return 0
  fi

  if [[ -e "$dir" ]]; then
    error "Path exists but is not a directory: $dir"
  fi

  mkdir -p "$dir"
}

#######################################
# Print a tree view of a directory.
# Globals:
#   None
# Arguments:
#   $1: Directory path to display.
#   $2: Depth of tree to display.
# Outputs:
#   Writes directory tree to stdout.
# Returns:
#   0 on success or if tree command not found.
#   1 if invalid number of arguments provided.
#######################################
print_dir_tree() {
  local dir="${1:-}"
  local depth="${2:-}"

  verbose "Printing directory tree for: $dir"

  require_arguments 2 "$@"

  require_command "tree"
  tree -a -L "$depth" "$dir"
}

#######################################
# Ensure a file exists before continuing.
# Globals:
#   None
# Arguments:
#   $1: File path to check.
# Outputs:
#   None
# Returns:
#   0 if the file exists.
#   1 if the file is not found.
#######################################
require_file() {
  local file="${1:-}"

  verbose "Checking for required file: $file"
  require_arguments 1 "$@"

  if [[ ! -f "$file" ]]; then
    error "Expected file not found: $file"
  fi
}

#######################################
# Copy a file from source to destination if destination doesn't exist.
# Globals:
#   None
# Arguments:
#   $1: Source file path.
#   $2: Destination file path.
# Outputs:
#   Writes log messages to stdout.
# Returns:
#   0 on success.
#   1 if source is missing or destination path is taken by non-regular file.
#######################################
copy_file_if_missing() {
  local src="${1:-}"
  local dest="${2:-}"

  verbose "Copying file if missing from $src to $dest"
  require_arguments 2 "$@"

  [[ -f "$src" ]] || error "Source file is missing: $src"

  if [[ -f "$dest" ]]; then
    debug "File exists, leaving unchanged: $dest"
    return 0
  fi

  if [[ -e "$dest" ]]; then
    error "Path exists but is not a regular file: $dest"
  fi

  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
}