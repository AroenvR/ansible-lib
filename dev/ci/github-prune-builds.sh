#!/bin/sh
# Deletes this branch's earlier build artifacts on GitHub, so only the newest
# build is kept (each also expires after 7 days on its own).
# Usage: dev/ci/github-prune-builds.sh <id of the artifact to keep>
# Needs GH_TOKEN with "actions: write", plus GitHub's GITHUB_REPOSITORY and GITHUB_REF_NAME.
set -eu
prefix="aslib-infra.$(echo "$GITHUB_REF_NAME" | tr / .)."
gh api --paginate "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=100" \
  --jq ".artifacts[] | select(.name | startswith(\"$prefix\")) | select(.id != $1) | .id" \
  | while read -r id; do
      echo "Deleting this branch's older build (artifact $id)"
      gh api --method DELETE "repos/$GITHUB_REPOSITORY/actions/artifacts/$id"
    done
