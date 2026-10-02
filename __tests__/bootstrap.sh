#!/bin/bash
#
# This script bootstraps everything a test suite will need.

bootstrap_tests() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local bash_lib_src="$script_dir/../source.sh"

    if [[ ! -f "$bash_lib_src" ]]; then
        echo "Failed to find bash library at: $bash_lib_src"
        exit 1
    fi

    source "$bash_lib_src"
    source "$script_dir/assert.sh"
    source_env_file "$script_dir/../.env.test"

    verbose "Finished setting up test environment"

}
bootstrap_tests