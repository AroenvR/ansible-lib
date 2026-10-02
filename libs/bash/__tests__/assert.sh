#!/bin/bash
#
# This script exposes test assertion helpers.

#######################################
# Assert that a command exit code matches an expected value.
#
# Globals:
#   None
# Arguments:
#   $1: Actual exit code.
#   $2: Expected exit code.
# Outputs:
#   Writes an error message to stderr when the exit codes do not match.
# Returns:
#   0 when the assertion passes.
#   1 when the assertion fails if error() exits, otherwise continues.
#######################################
assert_exit_code() {
  local actual="$1"
  local expected="$2"

  if [[ "$actual" -ne "$expected" ]]; then
    error "ASSERTION FAILED: expected exit code $expected but got $actual" >&2
  fi
}
