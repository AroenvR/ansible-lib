#!/bin/bash
#
# Logging utility functions for shell scripts.

#######################################
# Log a critical message and exit.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes critical message to stderr.
# Returns:
#   Always exits with status 1.
#######################################
critical() {
  output_message CRITICAL STDERR "$@"
  exit 1
}

#######################################
# Log an error message and exit.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes error message to stderr.
# Returns:
#   Always exits with status 1.
#######################################
error() {
  output_message ERROR STDERR "$@"
  exit 1
}

#######################################
# Log a warning message.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes warning message to stderr.
#######################################
warn() {
  output_message WARN STDERR "$@"
}

#######################################
# Log a standard message.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes log message to stdout.
#######################################
log() {
  output_message LOG STDOUT "$@"
}

#######################################
# Log an informational message.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes info message to stdout.
#######################################
info() {
  output_message INFO STDOUT "$@"
}

#######################################
# Log a debug message.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes debug message to stdout.
#######################################
debug() {
  output_message DEBUG STDOUT "$@"
}

#######################################
# Log a verbose message.
# Globals:
#   LOG_PREFIX
#   VERBOSE
# Arguments:
#   $*: Message to log.
# Outputs:
#   Writes verbose message to stdout only if VERBOSE is exactly "1".
#######################################
verbose() {
  [[ "${VERBOSE:-}" == "1" ]] || return 0
  output_message VERBOSE STDOUT "$@"
}

#######################################
# Internal function to output formatted log messages.
# Globals:
#   LOG_PREFIX
# Arguments:
#   $1: Log level (VERBOSE, DEBUG, INFO, LOG, WARN, ERROR, CRITICAL).
#   $2: Output destination (STDOUT or STDERR).
#   $@: Message to log.
# Outputs:
#   Writes formatted log entry to specified stream if level & destination are valid.
#   Silently fails if level and/or destination are not valid.
#######################################
output_message() {
  local level="${1:-}"
  local destination="${2:-STDOUT}"
  local prefix="${LOG_PREFIX:-script}"
  local fd=1

  # Return silently if "$level" is not whitelisted.
  local -r valid_levels="VERBOSE DEBUG INFO LOG WARN ERROR CRITICAL"
  if [[ ! " ${valid_levels} " =~ \ ${level}\  ]]; then
    return 0
  fi

  # Return silently if "$destination" is not whitelisted.
  local -r valid_destinations="STDERR STDOUT"
  if [[ ! " ${valid_destinations} " =~ \ ${destination}\  ]]; then
    return 0
  fi

  shift 2

  [[ "${destination}" == "STDERR" ]] && fd=2

  printf '%s %s - %s: %s\n' \
    "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    "${level}" \
    "${prefix}" \
    "$*" >&${fd}
}