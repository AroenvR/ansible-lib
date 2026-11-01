#!/bin/sh
# Tests dev/ci/mark-in-progress.sh, which labels an open issue N in progress
# exactly while a branch issue/<N> exists on the remote and the issue is not
# done, from the branches and labels as they are (so a missed run heals at the
# next). On GitHub with gh, on GitLab with glab: the stand-ins in bin/ take the
# place of both and keep the branches, the issues and their labels and every
# call in a scratch directory. The labels file of the tests calls in progress
# "in work", done "finished" and backlog "parked", unlike the project's own, so
# a label name written into the script shows.
# Run: sh dev/tests/mark-in-progress.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/ci/mark-in-progress.sh
if [ ! -f "$script" ]; then
  echo "FAIL: $script does not exist: nothing to test yet."
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
unset GH_REPO GH_TOKEN GH_HOST GITHUB_TOKEN GITLAB_TOKEN GITLAB_HOST CI_PROJECT_ID
# What the GitHub and the GitLab job give the script.
GH_TOKEN=test-token
GH_REPO=example/project
GITLAB_TOKEN=test-token
GITLAB_HOST=https://gitlab.example.invalid
CI_PROJECT_ID=42
PATH=$here/bin:$PATH
STUB_DIR=$tmp/stubs
export GH_TOKEN GH_REPO GITLAB_TOKEN GITLAB_HOST CI_PROJECT_ID PATH STUB_DIR
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

# The branches on the remote.
branches() {
  printf '%s\n' "$@" >"$STUB_DIR/branches"
}

# run <argument>...: the script, with fresh call logs.
run() {
  : >"$STUB_DIR/calls"
  : >"$STUB_DIR/writes"
  sh "$script" "$@" </dev/null >"$tmp/out" 2>"$tmp/err"
  rc=$?
}

# label <github|gitlab>: the script on that forge, with the labels file.
label() {
  run "$1" "$labels"
  case $1 in
    github) other=glab ;;
    gitlab) other=gh ;;
  esac
  if grep -q "^$other " "$STUB_DIR/calls"; then
    fail "$other was called on $1"
  fi
}

expect_rc() {
  [ "$rc" -eq "$1" ] || fail "exit code $rc, expected $1; stdout: $(cat "$tmp/out"); stderr: $(cat "$tmp/err")"
}

# expect_line <out|err> <line>: the line, exactly, on stdout or stderr.
expect_line() {
  grep -Fxq -e "$2" "$tmp/$1" || fail "no line \"$2\" on std$1, which has: $(cat "$tmp/$1")"
}

# expect_labels <N> [<label>...]: the issue's labels, in any order, each once.
expect_labels() {
  number=$1
  shift
  actual=$(sort "$STUB_DIR/issues/$number/labels" | tr '\n' ',')
  expected=$(printf '%s\n' "$@" | sed '/^$/d' | sort | tr '\n' ',')
  [ "$actual" = "$expected" ] || fail "#$number has the labels \"$actual\", expected \"$expected\""
}

expect_no_calls() {
  [ ! -s "$STUB_DIR/calls" ] || fail "gh or glab was called: $(cat "$STUB_DIR/calls")"
}

expect_no_writes() {
  [ ! -s "$STUB_DIR/writes" ] || fail "calls that write: $(cat "$STUB_DIR/writes")"
}

expect_writes() {
  count=$(wc -l <"$STUB_DIR/writes")
  [ "$count" -eq "$1" ] || fail "$count calls that write, expected $1: $(cat "$STUB_DIR/writes")"
}

# The board of the main case: what each issue is, and what becomes of it.
board() {
  # Only exact issue/<N> branches count, N without a leading zero.
  branches develop main issue/4 issue/6 issue/7 issue/9 issue/11 issue/13 issue/14 issue/50 \
    issue/07 issue/8-old issue/x issue/0 issue/12/sub issues/10
  issue 3 open "in work"          # its branch was deleted without a merge: loses it
  issue 4 closed "in work"        # closed, its branch still there: loses it
  issue 5 open "in work" finished # done, no branch: loses it
  issue 6 open parked "in work"   # in the backlog while someone holds it: keeps both
  issue 7 open                    # claimed: gets it
  issue 8 open                    # issue/8-old is not its branch
  issue 9 open finished           # done, its branch not deleted yet: does not get it
  issue 10 open                   # issues/10 is not its branch
  issue 11 open core              # claimed: gets it, keeps its area label
  issue 12 open                   # issue/12/sub is not its branch
  issue 13 open "in work"         # claimed and labelled: stays
  issue 14 closed                 # closed with a branch: does not get it
  # issue/50 is a pull request's number, not an issue's.
}

for forge in github gitlab; do
  case $forge in
    github)
      fail_branches="gh api *"
      fail_issues="gh issue list *"
      fail_label_7="gh issue edit 7 *"
      fail_unlabel_3="gh issue edit 3 *"
      ;;
    gitlab)
      fail_branches="glab GET projects/42/repository/branches*"
      fail_issues="glab GET projects/42/issues*"
      fail_label_7="glab PUT projects/42/issues/7"
      fail_unlabel_3="glab PUT projects/42/issues/3"
      ;;
  esac

  start "$forge: open issues with a branch get in progress, those without, closed or done lose it; a second run writes nothing"
  board
  label "$forge"
  expect_rc 0
  [ "$(grep '^Labelled #' "$tmp/out")" = "$(printf '%s\n' \
    'Labelled #7 "in work": its branch issue/7 exists.' \
    'Labelled #11 "in work": its branch issue/11 exists.')" ] ||
    fail "expected #7 then #11 labelled on stdout, which has: $(cat "$tmp/out")"
  [ "$(grep '^Removed ' "$tmp/out")" = "$(printf '%s\n' \
    'Removed "in work" from #3: no branch issue/3.' \
    'Removed "in work" from #4: it is closed.' \
    'Removed "in work" from #5: it is finished.')" ] ||
    fail "expected \"in work\" removed from #3, #4, #5, in this order, with their reasons; stdout has: $(cat "$tmp/out")"
  expect_writes 5
  expect_labels 3
  expect_labels 4
  expect_labels 5 finished
  expect_labels 6 parked "in work"
  expect_labels 7 "in work"
  expect_labels 8
  expect_labels 9 finished
  expect_labels 10
  expect_labels 11 core "in work"
  expect_labels 12
  expect_labels 13 "in work"
  expect_labels 14
  [ ! -e "$STUB_DIR/issues/50" ] || fail "an issue 50 was made"
  label "$forge"
  expect_rc 0
  expect_line out "\"in work\" matches the branches: nothing to change."
  expect_no_writes

  start "$forge: branches that cannot be listed change nothing and fail the run"
  board
  echo "$fail_branches" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not list the branches: nothing changed."
  expect_no_writes

  start "$forge: issues that cannot be listed change nothing and fail the run"
  board
  echo "$fail_issues" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not list the issues: nothing changed."
  expect_no_writes

  start "$forge: an issue that cannot be labelled or unlabelled fails the run, the others are still handled"
  board
  printf '%s\n' "$fail_label_7" "$fail_unlabel_3" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not label #7."
  expect_line err "Could not unlabel #3."
  expect_labels 7
  expect_labels 3 "in work"
  expect_labels 11 core "in work"
  expect_labels 4
  expect_labels 5 finished

  start "$forge: more issues than one page: the oldest are seen too"
  number=1
  while [ "$number" -le 35 ]; do
    issue "$number" open
    number=$((number + 1))
  done
  issue 2 open "in work"
  branches issue/1 issue/35
  label "$forge"
  expect_rc 0
  expect_labels 1 "in work"
  expect_labels 2
  expect_labels 35 "in work"
done

start "gitlab without its token says so, changes nothing and passes"
board
unset GITLAB_TOKEN
label gitlab
GITLAB_TOKEN=test-token
export GITLAB_TOKEN
expect_rc 0
expect_line out "GITLAB_TOKEN is not set (a project access token that may edit issues and labels): not labelling the issues \"in work\"."
expect_labels 7
expect_labels 3 "in work"
expect_no_calls

start "a labels file that cannot be read stops the run before any call"
board
run github "$tmp/no-such-labels.tsv"
expect_rc 2
expect_line err "$tmp/no-such-labels.tsv: cannot read."
expect_no_calls

for kanban in in-progress "done"; do
  start "a labels file that lacks the $kanban label stops the run before any call, on GitLab without its token too"
  grep -v "$tab$kanban$tab" "$labels" >"$tmp/labels.tsv"
  board
  run github "$tmp/labels.tsv"
  expect_rc 2
  expect_line err "$tmp/labels.tsv: no label with kanban \"$kanban\"."
  expect_no_calls
  unset GITLAB_TOKEN
  run gitlab "$tmp/labels.tsv"
  GITLAB_TOKEN=test-token
  export GITLAB_TOKEN
  expect_rc 2
  expect_line err "$tmp/labels.tsv: no label with kanban \"$kanban\"."
  expect_no_calls
done

for arguments in "" "bitbucket $labels" "github" "github $labels extra"; do
  start "usage error: mark-in-progress.sh $arguments"
  board
  # The arguments are split on purpose.
  # shellcheck disable=SC2086
  run $arguments
  expect_rc 2
  grep -q '^usage: mark-in-progress.sh ' "$tmp/err" || fail "no usage line on stderr, which has: $(cat "$tmp/err")"
  expect_no_calls
done

start ""
if [ "$failures" -gt 0 ]; then
  echo "mark-in-progress.sh: $failures check(s) failed."
  exit 1
fi
echo "mark-in-progress.sh: every case passes."
