#!/bin/sh
# Checks that a branch on its way to accept raises the collection's version:
# galaxy.yml's version must be higher than on <base> (accept's), and CHANGELOG.md
# must have a section for it ("## <version>"). CI runs it on every branch but
# main and accept; make version-raised runs it (BASE=<ref>, origin/accept by default).
set -eu
base=${1:?usage: version-raised.sh <base ref, such as origin/accept>}
new=$(sed -n 's/^version: *//p' galaxy.yml)
# On its own line, so that set -e stops on a base that does not exist.
old_file=$(git show "$base:galaxy.yml")
old=$(printf '%s\n' "$old_file" | sed -n 's/^version: *//p')
if [ -z "$old" ]; then
  echo "No version in $base:galaxy.yml." >&2
  exit 1
fi
higher=$(printf '%s\n%s\n' "$old" "$new" | sort -V | tail -n 1)
if [ "$new" = "$old" ] || [ "$higher" != "$new" ]; then
  echo "galaxy.yml's version is $new, $base's is $old: raise it, with a CHANGELOG.md section (CONTRIBUTING.md, Releases)." >&2
  exit 1
fi
if ! grep -q -x -F "## $new" CHANGELOG.md; then
  echo "CHANGELOG.md has no section for $new: add \"## $new\" with the changes (CONTRIBUTING.md, Releases)." >&2
  exit 1
fi
echo "galaxy.yml raises the version from $old ($base) to $new, and CHANGELOG.md has its section."
