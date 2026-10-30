#!/bin/sh
# Claims an issue for the agent that runs it, so that agents who do not know of
# each other never work on the same issue: it pushes a branch issue/<N> with one
# empty commit, "Claim #<N>: <agent>, <UTC time> [skip ci]", made on the base
# branch of the remote, without force. The remote creates a branch only once,
# so of two claims of one issue only the first gets it; the second is told who
# holds it. HEAD, the index and the working tree are never touched: the new
# branch waits for git switch.
#   usage: claim-issue.sh <issue number>
# Settings (environment):
#   AGENT_NAME        the name the claim shows (default: git's user.name)
#   CLAIM_REMOTE      the remote to claim on (default: origin)
#   CLAIM_BASE        the branch a claim starts from (default: develop)
#   CLAIM_STALE_DAYS  days without a push after which a claim may be taken over
#                     (default: 7)
# Where gh is set up for the repository, it first checks that the issue is open
# and has no open pull request; elsewhere it says so and claims with git alone.
# Exit 0: claimed; 1: not claimable, take another issue; 2: usage or
# environment, fix it and try again.
set -eu

remote=${CLAIM_REMOTE:-origin}
base=${CLAIM_BASE:-develop}
stale_days=${CLAIM_STALE_DAYS:-7}

usage() {
  cat >&2 <<'EOF'
usage: claim-issue.sh <issue number>
Settings (environment):
  AGENT_NAME        the name the claim shows (default: git's user.name)
  CLAIM_REMOTE      the remote to claim on (default: origin)
  CLAIM_BASE        the branch a claim starts from (default: develop)
  CLAIM_STALE_DAYS  days without a push after which a claim may be taken over (default: 7)
EOF
  exit 2
}

# stop <exit code> <message>
stop() {
  echo "$2" >&2
  exit "$1"
}

# A whole number from 1 up, without leading zeros.
is_number() {
  case $1 in
    '' | 0* | *[!0-9]*) return 1 ;;
  esac
}

if [ "$#" -ne 1 ] || ! is_number "$1" || ! is_number "$stale_days"; then
  usage
fi
issue=$1
branch=issue/$issue

agent=${AGENT_NAME:-$(git config user.name || true)}
case $agent in
  '' | *[[:cntrl:]]*) stop 2 "Set AGENT_NAME (or git's user.name) to the name your claims should show." ;;
esac

if git show-ref --verify --quiet "refs/heads/$branch"; then
  stop 2 "A local branch $branch exists already: if the claim is yours, git switch $branch; if not, delete it (git branch -D $branch) and claim again."
fi

# The forge's view: the issue is open and no open pull request is about it (its
# branch, or a closing keyword such as "Closes #<N>" in its title or body).
if command -v gh >/dev/null 2>&1 && gh repo view --json nameWithOwner --jq .nameWithOwner >/dev/null 2>&1; then
  state=$(gh issue view "$issue" --json state --jq .state) ||
    stop 2 "gh could not check issue #$issue: not claimed."
  if [ "$state" != OPEN ]; then
    stop 1 "Issue #$issue is $(printf '%s' "$state" | tr '[:upper:]' '[:lower:]'): not claimed."
  fi
  filter='.[] | select(.headRefName == "'"$branch"'" or ((.title + "\n" + (.body // ""))
    | test("(?i)\\b(close[sd]?|fix(e[sd])?|resolve[sd]?) #'"$issue"'([^0-9]|$)"))) | .number'
  pulls=$(gh pr list --state open --limit 100 --json number,headRefName,title,body --jq "$filter") ||
    stop 2 "gh could not check issue #$issue: not claimed."
  if [ -n "$pulls" ]; then
    list=
    for pull in $pulls; do
      list="${list:+$list, }#$pull"
    done
    stop 1 "Issue #$issue has an open pull request ($list): not claimed."
  fi
else
  echo "gh is not set up for this repository: not checking that #$issue is open and has no open pull request." >&2
fi

git fetch --quiet "$remote" "refs/heads/$base" ||
  stop 2 "Could not fetch $base from $remote: not claimed."
start=$(git rev-parse --verify --quiet 'FETCH_HEAD^{commit}') ||
  stop 2 "Could not fetch $base from $remote: not claimed."

now=$(date -u +%Y-%m-%dT%H:%MZ)
claim=$(git commit-tree -p "$start" -m "Claim #$issue: $agent, $now [skip ci]" "$start^{tree}") ||
  stop 2 "Could not make the claim commit (git's user.name and user.email): not claimed."

# The lock: the remote creates refs/heads/issue/<N> only if it does not exist.
# Only this push's creation of it ("*") is a claim; "=" (up to date) means an
# identical claim commit got there first.
tracking=refs/remotes/$remote/$branch
made_tracking=yes
if git show-ref --verify --quiet "$tracking"; then
  made_tracking=no
fi
push_rc=0
answer=$(git -c advice.pushUpdateRejected=false push --porcelain "$remote" "$claim:refs/heads/$branch") ||
  push_rc=$?
flag=$(printf '%s\n' "$answer" | awk -F '\t' -v ref=":refs/heads/$branch" '
  NF >= 2 && length($2) > length(ref) && substr($2, length($2) - length(ref) + 1) == ref { print $1; exit }')

if [ "$push_rc" -eq 0 ] && [ "$flag" = '*' ]; then
  git branch "$branch" "$claim"
  git config "branch.$branch.remote" "$remote"
  git config "branch.$branch.merge" "refs/heads/$branch"
  echo "Claimed #$issue as $agent: $branch is on $remote. Next: git switch $branch"
  exit 0
fi

# Refused: leave nothing behind, then say why.
if [ "$made_tracking" = yes ] && git show-ref --verify --quiet "$tracking"; then
  git update-ref -d "$tracking"
fi
if ! git ls-remote --exit-code "$remote" "refs/heads/$branch" >/dev/null; then
  stop 2 "Could not push $branch to $remote: not claimed."
fi
# Into FETCH_HEAD only: no remote-tracking branch is made.
if ! git fetch --quiet --refmap= "$remote" "refs/heads/$branch"; then
  stop 1 "Issue #$issue is claimed already ($branch exists on $remote). Take another issue."
fi
# Who: the newest claim on the branch, else its last commit. Remote text, so
# without control characters.
who=$(git log --format=%s "^$start" FETCH_HEAD | awk -v claim="Claim #$issue: " 'index($0, claim) == 1 { print; exit }')
if [ -z "$who" ]; then
  who=$(git log -1 --format=%s FETCH_HEAD)
fi
who=$(printf '%s' "$who" | tr -d '[:cntrl:]')
when=$(git log -1 --format=%cI FETCH_HEAD)
if [ -z "$(git log -1 --format=%H --since="$stale_days days ago" FETCH_HEAD)" ]; then
  next="No push for more than $stale_days days: you may continue it on top of what is there, with a commit naming the takeover; never discard it."
else
  next="Take another issue."
fi
stop 1 "Issue #$issue is claimed already: $who ($branch, last commit $when). $next"
