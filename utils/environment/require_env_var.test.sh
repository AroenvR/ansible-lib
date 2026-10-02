#!/bin/bash
#
# This script runs tests against the environment package's `require_env_var` function

# Before all "hook"
before_all() {
  LOG_PREFIX="test_require_env_var"

  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local bootstrap_src="$script_dir/../../__tests__/bootstrap.sh"

  if [[ ! -f "$bootstrap_src" ]]; then
      echo "Failed to bootstrap test from: $bootstrap_src"
      exit 1
  fi

  source "$bootstrap_src"
}

# 
test_require_env_var_without_args_err() {
  info "Testing without args"

  local status=0
  ( require_env_var ) >/dev/null 2>&1 || status=$?
  
  assert_exit_code "$status" 1
}

# 
test_without_env_var_err() {
  info "Testing without the environment variable existing"

  local status=0
  ( require_env_var "YOLO_FUBAR" ) >/dev/null 2>&1 || status=$?
  
  assert_exit_code "$status" 1
}

# 
test_with_env_var() {
  info "Testing with the expected variable existing"

  HAPPY_FLOW_ENV_VAR=1

  local status=0
  ( require_env_var "HAPPY_FLOW_ENV_VAR" ) >/dev/null 2>&1 || status=$?
  
  HAPPY_FLOW_ENV_VAR=""

  assert_exit_code "$status" 0
}

# The actual suite to run
test_suite() {
  before_all

  # --------------------------------------------------

  # Happy flow tests
  debug "Happy flow tests"

  # --------------------------------------------------

  # Test the function when the expected environment variable exists
  test_with_env_var

  # --------------------------------------------------

  # ERROR tests
  debug "Error tests"

  # --------------------------------------------------

  # Call require_env_var with no arguments
  test_require_env_var_without_args_err

  # --------------------------------------------------

  # Call require_env_var while missing the expecting environment variable
  test_without_env_var_err
}
test_suite