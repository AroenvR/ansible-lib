#!/bin/bash
#
# Library for common shell utilities and shared functions.

set -Eeuo pipefail

#######################################
# Source the bash libs from this file's own directory.
#
# Uses ${BASH_SOURCE[0]} to determine the runtime location of this script.
#
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   Writes a verbose message when the library is sourced.
# Returns:
#   0 if the library is sourced successfully.
#######################################
source_bash_lib() {
    local lib_root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Down-source utilities
    . "$lib_root_dir/utils/utils.sh"

    verbose "Sourced bash libs from $lib_root_dir"
}
source_bash_lib