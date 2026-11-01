#!/bin/sh
# Tests dev/claim-issue.sh, which claims an issue by pushing a branch issue/<N>
# with one empty commit, against a scratch bare repository and clones of it.
# The stand-in for gh in bin/ answers whether an issue is open, which labels it
# has and which pull requests are open; one case runs without any gh. The labels
# file of the tests names its labels unlike the project's own (backlog is
# "parked", done is "finished"), so a label name written into the script shows.
# Run: sh dev/tests/claim-issue.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/claim-issue.sh
if [ ! -f "$script" ]; then
  echo "FAIL: $script does not exist: nothing to test yet."
  exit 1
fi
if [ ! -x "$script" ]; then
  echo "FAIL: $script is not executable (it needs mode 755)."
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "FAIL: jq not found: the stand-ins for gh and glab need it."
  exit 1
fi
labels=$here/fixtures/labels.tsv
tab=$(printf '\t')

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
cd "$tmp"

# Only the settings the cases give count: no agent name, git configuration or
# gh repository from outside.
unset AGENT_NAME CLAIM_REMOTE CLAIM_BASE CLAIM_STALE_DAYS CLAIM_LABELS_FILE GH_REPO GH_HOST GH_TOKEN GITHUB_TOKEN \
  GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE \
  GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_COMMITTER_DATE EMAIL XDG_CONFIG_HOME \
  GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
HOME=$tmp/home
GIT_CONFIG_NOSYSTEM=1
GIT_TERMINAL_PROMPT=0
export HOME GIT_CONFIG_NOSYSTEM GIT_TERMINAL_PROMPT
mkdir "$HOME"
# No user.name here: each clone has its own, and one has none.
git config --global user.email agent@example.invalid
git config --global init.defaultBranch develop

# The remote, with develop and trunk (a second base), and three clones.
origin=$tmp/origin.git
git init -q --bare "$origin"
git init -q "$tmp/seed"
git -C "$tmp/seed" config user.name Seed
git -C "$tmp/seed" remote add origin "$origin"
echo "A project" >"$tmp/seed/README"
mkdir "$tmp/seed/dev"
cp "$labels" "$tmp/seed/dev/labels.tsv"
git -C "$tmp/seed" add README dev/labels.tsv
git -C "$tmp/seed" commit -q -m "Start the project"
git -C "$tmp/seed" push -q origin develop
git -C "$tmp/seed" checkout -q -b trunk
echo "More" >"$tmp/seed/more.txt"
git -C "$tmp/seed" add more.txt
git -C "$tmp/seed" commit -q -m "Work on trunk"
git -C "$tmp/seed" push -q origin trunk
develop=$(git -C "$origin" rev-parse refs/heads/develop)
trunk=$(git -C "$origin" rev-parse refs/heads/trunk)
for clone in A B C D E; do
  git clone -q "$origin" "$tmp/$clone"
done
git -C "$tmp/A" config user.name Alice
git -C "$tmp/B" config user.name Bob
# C has no user.name, and git may not guess one: with a HOME without
# configuration it has no identity at all.
git -C "$tmp/C" config user.useConfigOnly true
mkdir "$tmp/no-identity"
# D and E are two agents with the same name and identity.
git -C "$tmp/D" config user.name "Same Agent"
git -C "$tmp/E" config user.name "Same Agent"
# Work in progress in A, which a claim must not touch: staged, changed, untracked.
echo "staged" >"$tmp/A/staged.txt"
git -C "$tmp/A" add staged.txt
echo "changed" >>"$tmp/A/README"
echo "untracked" >"$tmp/A/untracked.txt"

# An old claim of #8 with work on top, pushed after the clones were made.
git -C "$tmp/seed" checkout -q -b issue/8 develop
GIT_AUTHOR_DATE="2001-01-01 00:00:00 +0000" GIT_COMMITTER_DATE="2001-01-01 00:00:00 +0000" \
  git -C "$tmp/seed" commit -q --allow-empty -m "Claim #8: Agent Old, 2001-01-01T00:00Z [skip ci]"
echo "Work" >"$tmp/seed/work.txt"
git -C "$tmp/seed" add work.txt
GIT_AUTHOR_DATE="2001-01-02 00:00:00 +0000" GIT_COMMITTER_DATE="2001-01-02 00:00:00 +0000" \
  git -C "$tmp/seed" commit -q -m "Begin the work on the issue"
git -C "$tmp/seed" push -q origin issue/8
old_claim=$(git -C "$origin" rev-parse refs/heads/issue/8)

# A PATH with every command of this machine but gh (and without the stand-ins).
no_gh=$tmp/no-gh
mkdir "$no_gh"
plain_path=$PATH
IFS=:
for dir in $plain_path; do
  if [ -d "$dir" ]; then
    ln -s "$dir"/* "$no_gh"/ 2>/dev/null || true
  fi
done
unset IFS
rm -f "$no_gh/gh"

# A date that gives the claim's time as fixed at the start, so that two claims in
# the same second of git time make the same commit even when the minute changes.
same_time=$(date -u +%Y-%m-%dT%H:%MZ)
same_stamp=$(date -u '+%Y-%m-%d %H:%M:%S +0000')
real_date=$(command -v date)
fixed_date=$tmp/fixed-date
mkdir "$fixed_date"
cat >"$fixed_date/date" <<EOF
#!/bin/sh
if [ "\$*" = "-u +%Y-%m-%dT%H:%MZ" ]; then
  echo "$same_time"
else
  exec "$real_date" "\$@"
fi
EOF
chmod 755 "$fixed_date/date"
if (PATH=$no_gh && command -v gh >/dev/null) || ! (PATH=$no_gh && command -v git >/dev/null); then
  echo "FAIL: setup: could not make a PATH without gh."
  exit 1
fi

PATH=$here/bin:$plain_path
STUB_DIR=$tmp/stubs
export PATH STUB_DIR
set +e

failures=0
case_failures=0
name=

fail() {
  echo "FAIL: $name: $*"
  failures=$((failures + 1))
}

# Reports the case before, then starts the next with fresh stand-in state.
start() {
  if [ -n "$name" ] && [ "$failures" -eq "$case_failures" ]; then
    echo "ok: $name"
  fi
  name=$1
  case_failures=$failures
  rm -rf "$STUB_DIR"
  mkdir "$STUB_DIR"
  : >"$STUB_DIR/calls"
}

# issue <N> <open|closed> [<label>...]: an issue on the forge.
issue() {
  issue_dir=$STUB_DIR/issues/$1
  mkdir -p "$issue_dir"
  echo "$2" >"$issue_dir/state"
  shift 2
  : >"$issue_dir/labels"
  for label in "$@"; do
    printf '%s\n' "$label" >>"$issue_dir/labels"
  done
}

set_open() {
  for number in "$@"; do issue "$number" open; done
}

# claim <clone> <agent name, or "" to leave AGENT_NAME unset> [<arguments>]
claim() {
  claim_dir=$1
  claim_agent=$2
  shift 2
  if [ -n "$claim_agent" ]; then
    (cd "$claim_dir" && AGENT_NAME=$claim_agent "$script" "$@") </dev/null >"$tmp/out" 2>"$tmp/err"
  else
    (cd "$claim_dir" && "$script" "$@") </dev/null >"$tmp/out" 2>"$tmp/err"
  fi
  rc=$?
}

# A clone's branch, commit, index and working tree, to compare before and after.
snapshot() {
  (cd "$1" && git symbolic-ref HEAD && git rev-parse HEAD && git status --porcelain)
}

expect_rc() {
  [ "$rc" -eq "$1" ] || fail "exit code $rc, expected $1; stdout: $(cat "$tmp/out"); stderr: $(cat "$tmp/err")"
}

# expect_line <out|err> <line>: the line, exactly, on stdout or stderr.
expect_line() {
  grep -Fxq -e "$2" "$tmp/$1" || fail "no line \"$2\" on std$1, which has: $(cat "$tmp/$1")"
}

# expect_text <out|err> <text>: the text somewhere on stdout or stderr.
expect_text() {
  grep -Fq -e "$2" "$tmp/$1" || fail "no \"$2\" on std$1, which has: $(cat "$tmp/$1")"
}

expect_no_text() {
  if grep -Fq -e "$2" "$tmp/$1"; then
    fail "\"$2\" on std$1, which has: $(cat "$tmp/$1")"
  fi
}

# Nothing of a refused claim stays in the clone.
expect_nothing_left() {
  if git -C "$1" show-ref --verify -q "refs/heads/issue/$2"; then
    fail "the clone has a branch issue/$2"
  fi
  if git -C "$1" show-ref --verify -q "refs/remotes/origin/issue/$2"; then
    fail "the clone has a remote-tracking branch origin/issue/$2"
  fi
}

# The commit of origin's issue/<N>, or nothing.
origin_tip() {
  git -C "$origin" rev-parse -q --verify "refs/heads/issue/$1"
}

expect_not_on_origin() {
  if git -C "$origin" show-ref --verify -q "refs/heads/issue/$1"; then
    fail "origin has a branch issue/$1"
  fi
}

# expect_claim <clone> <N> <agent> <base commit>: origin's issue/<N> is one empty
# commit on the base with the claim's subject; the clone has it as a branch
# tracking it.
expect_claim() {
  tip=$(origin_tip "$2")
  if [ -z "$tip" ]; then
    fail "origin has no branch issue/$2"
    return
  fi
  subject=$(git -C "$origin" log -1 --format=%s "$tip")
  printf '%s\n' "$subject" | grep -Eqx "Claim #$2: $3, [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z \[skip ci\]" ||
    fail "the claim's subject is \"$subject\", expected \"Claim #$2: $3, <UTC time, minutes> [skip ci]\""
  [ "$(git -C "$origin" rev-parse "$tip^@")" = "$4" ] || fail "the claim's parent is not the base $4"
  [ "$(git -C "$origin" rev-parse "$tip^{tree}")" = "$(git -C "$origin" rev-parse "$4^{tree}")" ] ||
    fail "the claim commit is not empty"
  [ "$(git -C "$1" rev-parse -q --verify "refs/heads/issue/$2")" = "$tip" ] ||
    fail "the clone's branch issue/$2 is not origin's"
  [ "$(git -C "$1" rev-parse --abbrev-ref "issue/$2@{upstream}" 2>/dev/null)" = "origin/issue/$2" ] ||
    fail "the clone's branch issue/$2 does not track origin/issue/$2"
}

start "two agents claim the same issue from the same develop: the first gets it, the second is refused"
set_open 7
before_a=$(snapshot "$tmp/A")
before_b=$(snapshot "$tmp/B")
claim "$tmp/A" "Agent A" 7
expect_rc 0
expect_line out "Claimed #7 as Agent A: issue/7 is on origin. Next: git switch issue/7"
expect_claim "$tmp/A" 7 "Agent A" "$develop"
[ "$(snapshot "$tmp/A")" = "$before_a" ] || fail "the claim changed the clone's branch, index or working tree"
grep -q '^gh issue view 7' "$STUB_DIR/calls" || fail "gh was not asked whether #7 is open"
first=$(origin_tip 7)
first_subject=$(git -C "$origin" log -1 --format=%s "$first" 2>/dev/null)
claim "$tmp/B" "Agent B" 7
expect_rc 1
expect_text err "Issue #7 is claimed already: $first_subject (issue/7, last commit "
expect_text err "Take another issue."
expect_no_text err "No push for more than"
expect_nothing_left "$tmp/B" 7
[ "$(origin_tip 7)" = "$first" ] || fail "origin's issue/7 changed"
[ "$(snapshot "$tmp/B")" = "$before_b" ] || fail "the refusal changed the clone's branch, index or working tree"

start "a local branch issue/N stops the claim"
set_open 7
claim "$tmp/A" "Agent A" 7
expect_rc 2
expect_line err "A local branch issue/7 exists already: if the claim is yours, git switch issue/7; if not, delete it (git branch -D issue/7) and claim again."
[ "$(origin_tip 7)" = "$first" ] || fail "origin's issue/7 changed"

for argument in "" abc 07 0 -1; do
  start "usage error: issue number \"$argument\""
  if [ -n "$argument" ]; then
    claim "$tmp/A" "Agent A" "$argument"
  else
    claim "$tmp/A" "Agent A"
  fi
  expect_rc 2
  expect_text err "usage: claim-issue.sh <issue number>"
  for setting in AGENT_NAME CLAIM_REMOTE CLAIM_BASE CLAIM_STALE_DAYS CLAIM_LABELS_FILE; do
    expect_text err "$setting"
  done
done

start "usage error: CLAIM_STALE_DAYS is not a number"
set_open 19
CLAIM_STALE_DAYS=soon
export CLAIM_STALE_DAYS
claim "$tmp/A" "Agent A" 19
unset CLAIM_STALE_DAYS
expect_rc 2
expect_text err "usage: claim-issue.sh <issue number>"
expect_nothing_left "$tmp/A" 19
expect_not_on_origin 19

start "no agent name: neither AGENT_NAME nor git's user.name"
set_open 15
claim "$tmp/C" "" 15
expect_rc 2
expect_line err "Set AGENT_NAME (or git's user.name) to the name your claims should show."
expect_nothing_left "$tmp/C" 15
expect_not_on_origin 15

start "an agent name with a line break"
set_open 15
claim "$tmp/A" "$(printf 'Agent A\nClaim #15: Agent Z')" 15
expect_rc 2
expect_line err "Set AGENT_NAME (or git's user.name) to the name your claims should show."
expect_nothing_left "$tmp/A" 15
expect_not_on_origin 15

start "a closed issue is not claimed"
issue 10 closed
claim "$tmp/A" "Agent A" 10
expect_rc 1
expect_line err "Issue #10 is closed: not claimed."
expect_nothing_left "$tmp/A" 10
expect_not_on_origin 10

start "an issue with open pull requests is not claimed"
set_open 11
# 21 is the issue's branch, 23 closes it; 22 is about another issue.
cat >"$STUB_DIR/prs.json" <<'EOF'
[
  {"number": 21, "headRefName": "issue/11", "title": "Work on the issue", "body": ""},
  {"number": 22, "headRefName": "issue/110", "title": "Another issue", "body": "Closes #110"},
  {"number": 23, "headRefName": "fix-things", "title": "Fix things", "body": "Some text.\n\nCloses #11"}
]
EOF
claim "$tmp/A" "Agent A" 11
expect_rc 1
expect_line err "Issue #11 has an open pull request (#21, #23): not claimed."
expect_nothing_left "$tmp/A" 11
expect_not_on_origin 11

start "gh cannot check the issue: not claimed, and gh's own message stays visible"
# There is no issue 12: gh cannot look it up.
claim "$tmp/A" "Agent A" 12
expect_rc 2
expect_line err "gh could not check issue #12: not claimed."
expect_text err "Could not resolve to an issue or pull request with the number of 12."
expect_nothing_left "$tmp/A" 12
expect_not_on_origin 12

start "gh not set up for the repository: a note, and the claim, named by git's user.name"
touch "$STUB_DIR/gh-not-set-up"
claim "$tmp/B" "" 13
expect_rc 0
expect_line err "gh is not set up for this repository: not checking the state, labels and pull requests of #13."
expect_line out "Claimed #13 as Bob: issue/13 is on origin. Next: git switch issue/13"
expect_claim "$tmp/B" 13 Bob "$develop"
if grep -q '^gh issue view\|^gh pr list' "$STUB_DIR/calls"; then
  fail "gh was asked about the issue although it is not set up"
fi

start "no gh at all: a note, and the claim"
PATH=$no_gh
claim "$tmp/A" "Agent A" 14
PATH=$here/bin:$plain_path
expect_rc 0
expect_line err "gh is not set up for this repository: not checking the state, labels and pull requests of #14."
expect_claim "$tmp/A" 14 "Agent A" "$develop"

start "a claim without a push for more than 7 days: the refusal says how to take it over"
set_open 8
claim "$tmp/A" "Agent A" 8
expect_rc 1
expect_text err "Issue #8 is claimed already: Claim #8: Agent Old, 2001-01-01T00:00Z [skip ci] (issue/8, last commit 2001-01-02"
expect_text err "No push for more than 7 days: you may continue it on top of what is there, with a commit naming the takeover; never discard it."
expect_no_text err "Take another issue."
expect_nothing_left "$tmp/A" 8
[ "$(origin_tip 8)" = "$old_claim" ] || fail "origin's issue/8 changed"

start "CLAIM_STALE_DAYS sets when a claim is stale"
set_open 8
CLAIM_STALE_DAYS=30
export CLAIM_STALE_DAYS
claim "$tmp/A" "Agent A" 8
expect_rc 1
expect_text err "No push for more than 30 days: "
# 20000 days reach back before 2001: the old claim is not stale then.
CLAIM_STALE_DAYS=20000
claim "$tmp/A" "Agent A" 8
unset CLAIM_STALE_DAYS
expect_rc 1
expect_text err "Take another issue."
expect_no_text err "No push for more than"
expect_nothing_left "$tmp/A" 8

start "CLAIM_BASE sets the branch the claim starts from"
set_open 16
CLAIM_BASE=trunk
export CLAIM_BASE
claim "$tmp/A" "Agent A" 16
unset CLAIM_BASE
expect_rc 0
expect_claim "$tmp/A" 16 "Agent A" "$trunk"

start "CLAIM_REMOTE sets the remote: one that cannot be fetched stops the claim"
set_open 18
CLAIM_REMOTE=nowhere
export CLAIM_REMOTE
claim "$tmp/A" "Agent A" 18
unset CLAIM_REMOTE
expect_rc 2
expect_line err "Could not fetch develop from nowhere: not claimed."
expect_nothing_left "$tmp/A" 18
expect_not_on_origin 18

start "two agents with the same name and identity claim at the same time: only the first gets it"
set_open 20
before_e=$(snapshot "$tmp/E")
GIT_AUTHOR_DATE=$same_stamp
GIT_COMMITTER_DATE=$same_stamp
export GIT_AUTHOR_DATE GIT_COMMITTER_DATE
PATH=$fixed_date:$here/bin:$plain_path
claim "$tmp/D" "Agent Same" 20
expect_rc 0
expect_claim "$tmp/D" 20 "Agent Same" "$develop"
same=$(origin_tip 20)
same_subject=$(git -C "$origin" log -1 --format=%s "$same" 2>/dev/null)
claim "$tmp/E" "Agent Same" 20
PATH=$here/bin:$plain_path
unset GIT_AUTHOR_DATE GIT_COMMITTER_DATE
expect_rc 1
expect_text err "Issue #20 is claimed already: $same_subject (issue/20, last commit "
expect_text err "Take another issue."
expect_no_text out "Claimed #20"
expect_nothing_left "$tmp/E" 20
[ "$(origin_tip 20)" = "$same" ] || fail "origin's issue/20 changed"
[ "$(snapshot "$tmp/E")" = "$before_e" ] || fail "the refusal changed the clone's branch, index or working tree"

start "no git identity: the claim commit cannot be made"
set_open 21
HOME=$tmp/no-identity
claim "$tmp/C" "Agent C" 21
HOME=$tmp/home
expect_rc 2
expect_line err "Could not make the claim commit (git's user.name and user.email): not claimed."
expect_nothing_left "$tmp/C" 21
expect_not_on_origin 21

start "a push the remote refuses for another reason stops the claim"
set_open 17
cat >"$origin/hooks/pre-receive" <<'EOF'
#!/bin/sh
while read -r old new ref; do
  if [ "$ref" = refs/heads/issue/17 ]; then
    echo "issue/17 is not yours to push" >&2
    exit 1
  fi
done
EOF
chmod 755 "$origin/hooks/pre-receive"
claim "$tmp/A" "Agent A" 17
rm "$origin/hooks/pre-receive"
expect_rc 2
expect_line err "Could not push issue/17 to origin: not claimed."
expect_nothing_left "$tmp/A" 17
expect_not_on_origin 17

start "a backlog issue is not claimed, before its pull requests are asked for"
issue 30 open parked core
claim "$tmp/A" "Agent A" 30
expect_rc 1
expect_line err "Issue #30 is labelled \"parked\": not claimed. Take another issue."
expect_no_text out "Claimed #30"
expect_nothing_left "$tmp/A" 30
expect_not_on_origin 30
if grep -q '^gh pr list' "$STUB_DIR/calls"; then
  fail "gh was asked for pull requests of an issue it refuses"
fi

start "a done issue is not claimed"
issue 31 open finished
claim "$tmp/A" "Agent A" 31
expect_rc 1
expect_line err "Issue #31 is labelled \"finished\": not claimed. Take another issue."
expect_nothing_left "$tmp/A" 31
expect_not_on_origin 31

start "an issue both done and in the backlog: the refusal names done"
issue 32 open parked finished
claim "$tmp/A" "Agent A" 32
expect_rc 1
expect_line err "Issue #32 is labelled \"finished\": not claimed. Take another issue."
expect_no_text err "\"parked\""
expect_not_on_origin 32

start "a closed issue labelled done is refused as closed"
issue 33 closed finished
claim "$tmp/A" "Agent A" 33
expect_rc 1
expect_line err "Issue #33 is closed: not claimed."
expect_no_text err "labelled"
expect_not_on_origin 33

start "an issue with area labels only is claimed as before"
issue 34 open core "tools and agents"
claim "$tmp/A" "Agent A" 34
expect_rc 0
expect_line out "Claimed #34 as Agent A: issue/34 is on origin. Next: git switch issue/34"
expect_claim "$tmp/A" 34 "Agent A" "$develop"
expect_no_text err "label"

start "CLAIM_LABELS_FILE names the labels file"
# The same labels, but the backlog's label is called "someday".
sed "s/^parked$tab/someday$tab/" "$labels" >"$tmp/other-labels.tsv"
issue 35 open someday
CLAIM_LABELS_FILE=$tmp/other-labels.tsv
export CLAIM_LABELS_FILE
claim "$tmp/A" "Agent A" 35
unset CLAIM_LABELS_FILE
expect_rc 1
expect_line err "Issue #35 is labelled \"someday\": not claimed. Take another issue."
expect_not_on_origin 35
# With the file in the clone, dev/labels.tsv, "someday" is just a label.
issue 38 open someday
claim "$tmp/A" "Agent A" 38
expect_rc 0
expect_claim "$tmp/A" 38 "Agent A" "$develop"

start "a labels file that cannot be read: a note, and the claim"
issue 36 open parked
CLAIM_LABELS_FILE=$tmp/no-such-labels.tsv
export CLAIM_LABELS_FILE
claim "$tmp/A" "Agent A" 36
unset CLAIM_LABELS_FILE
expect_rc 0
expect_line err "$tmp/no-such-labels.tsv names no backlog or done label: not checking the labels of #36."
expect_claim "$tmp/A" 36 "Agent A" "$develop"

start "a labels file without backlog and done labels: a note, and the claim"
grep -v -e "${tab}backlog$tab" -e "${tab}done$tab" "$labels" >"$tmp/area-labels.tsv"
issue 37 open parked finished
CLAIM_LABELS_FILE=$tmp/area-labels.tsv
export CLAIM_LABELS_FILE
claim "$tmp/A" "Agent A" 37
unset CLAIM_LABELS_FILE
expect_rc 0
expect_line err "$tmp/area-labels.tsv names no backlog or done label: not checking the labels of #37."
expect_claim "$tmp/A" 37 "Agent A" "$develop"

start ""
if [ "$failures" -gt 0 ]; then
  echo "claim-issue.sh: $failures check(s) failed."
  exit 1
fi
echo "claim-issue.sh: every case passes."
