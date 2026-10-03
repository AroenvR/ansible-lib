#!/bin/bash
#
# This script makes a tarball archive of the current `.git` directory

#######################################
#            Script setup             #
#######################################

# Useful globals
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="${LOG_PREFIX:-archive_git}"

# !!! Edit path to bash library !!!
BASH_LIB_SRC="$SCRIPT_DIR/../libs/bash/source.sh";
if [[ ! -f "$BASH_LIB_SRC" ]]; then
  echo "Failed to find bash library at: $BASH_LIB_SRC"
  exit 1
fi

# Source the library.
source "$BASH_LIB_SRC"
source_default_environment "$SCRIPT_DIR/../.env.example"

# Log setup success
log "Executing the $LOG_PREFIX script in directory: $SCRIPT_DIR"

#######################################
#           Setup complete!           #
#######################################

# Create an archive of the git repository's current state
GIT_DIR="$SCRIPT_DIR/../.git"
OUT_DIR="$SCRIPT_DIR/.."
git_archive_state "$GIT_DIR" "$OUT_DIR"
