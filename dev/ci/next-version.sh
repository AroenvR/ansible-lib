#!/bin/sh
# Prints the version of the next release from main: one patch above the latest
# v<major>.<minor>.<patch> tag, or galaxy.yml's version when that is higher (raise
# it there to release a new minor or major version). No tags yet: galaxy.yml's.
set -eu
floor=$(sed -n 's/^version: *//p' galaxy.yml)
latest=$(git ls-remote --tags --refs origin 'v*' | sed -n 's#.*refs/tags/v##p' \
  | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1)
if [ -z "$latest" ]; then
  echo "$floor"
  exit
fi
next=$(echo "$latest" | awk -F. '{ print $1 "." $2 "." $3 + 1 }')
printf '%s\n%s\n' "$next" "$floor" | sort -V | tail -n 1
