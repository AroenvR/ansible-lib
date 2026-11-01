#!/bin/sh
# Tests dev/ci/mark-done.sh, which marks done the issues named by the "Closes #N"
# lines at the end of a commit message (given on stdin): each open one gets the
# done label, loses in progress and gets a comment naming the commit, and stays
# open, as the forge closes it when the commit reaches the default branch. On
# GitHub with gh, on GitLab with glab: the stand-ins in bin/ take the place of
# both and keep the issues, their labels, the comments and every call in a
# scratch directory. The labels file of the tests calls done "finished" and in
# progress "in work", unlike the project's own, so a label name written into the
# script shows.
# Run: sh dev/tests/mark-done.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/ci/mark-done.sh
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
sha=0123456789abcdef0123456789abcdef01234567
with_pull_request="Done by commit $sha (pull request #54); the issue closes when the commit reaches the default branch."
without_pull_request="Done by commit $sha; the issue closes when the commit reaches the default branch."
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
  rm -rf "$STUB_DIR" "$tmp/message"
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

# The commit message, one argument per line.
message() {
  printf '%s\n' "$@" >"$tmp/message"
}

# run <argument>...: the script, with the message on stdin and fresh call logs.
run() {
  : >"$STUB_DIR/calls"
  : >"$STUB_DIR/writes"
  sh "$script" "$@" <"$tmp/message" >"$tmp/out" 2>"$tmp/err"
  rc=$?
}

# mark <github|gitlab>: the script on that forge, for $sha, with the labels file.
mark() {
  run "$1" "$sha" "$labels"
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

expect_state() {
  state=$(cat "$STUB_DIR/issues/$1/state")
  [ "$state" = "$2" ] || fail "#$1 is $state, expected $2"
}

# expect_comment <N> <text>: the issue has exactly this one comment.
expect_comment() {
  if [ ! -s "$STUB_DIR/issues/$1/comments" ]; then
    fail "no comment on #$1"
  elif [ "$(cat "$STUB_DIR/issues/$1/comments")" != "$2" ]; then
    fail "the comments on #$1 are \"$(cat "$STUB_DIR/issues/$1/comments")\", expected one: \"$2\""
  fi
}

expect_no_comment() {
  [ ! -s "$STUB_DIR/issues/$1/comments" ] || fail "a comment on #$1: $(cat "$STUB_DIR/issues/$1/comments")"
}

expect_no_calls() {
  [ ! -s "$STUB_DIR/calls" ] || fail "gh or glab was called: $(cat "$STUB_DIR/calls")"
}

expect_no_writes() {
  [ ! -s "$STUB_DIR/writes" ] || fail "calls that write: $(cat "$STUB_DIR/writes")"
}

for forge in github gitlab; do
  case $forge in
    github)
      fail_label_write="gh issue edit 12 *"
      fail_comment="gh issue comment 12 *"
      ;;
    gitlab)
      fail_label_write="glab PUT projects/42/issues/12"
      fail_comment="glab POST projects/42/issues/12/notes"
      ;;
  esac

  start "$forge: a trailing Closes line marks the issue done, names the commit and the pull request, and leaves it open"
  issue 12 open "in work" core
  message "Add the claim command (#54)" "" "What it does." "" "Closes #12"
  mark "$forge"
  expect_rc 0
  expect_line out "Marked #12 done."
  expect_labels 12 finished core
  expect_state 12 open
  expect_comment 12 "$with_pull_request"
  # A second run on the same commit writes nothing.
  mark "$forge"
  expect_rc 0
  expect_line out "#12 is done already: left alone."
  expect_no_writes
  expect_labels 12 finished core
  expect_comment 12 "$with_pull_request"

  start "$forge: two trailing Closes lines mark both, top to bottom, each once; no pull request in the subject"
  issue 12 open "in work"
  issue 13 open
  message "Fix two things on develop" "" "Closes #12" "Closes #13" "Closes #12"
  mark "$forge"
  expect_rc 0
  [ "$(grep '^Marked #' "$tmp/out")" = "$(printf 'Marked #12 done.\nMarked #13 done.')" ] ||
    fail "expected \"Marked #12 done.\" then \"Marked #13 done.\" on stdout, which has: $(cat "$tmp/out")"
  [ "$(grep -c '#12[^0-9]' "$tmp/out")" -eq 1 ] || fail "#12 handled more than once: $(cat "$tmp/out")"
  expect_labels 12 finished
  expect_labels 13 finished
  expect_state 12 open
  expect_state 13 open
  expect_comment 12 "$without_pull_request"
  expect_comment 13 "$without_pull_request"

  start "$forge: a closed issue is left alone, the open one is marked"
  issue 12 closed "in work"
  issue 13 open
  message "Subject (#54)" "" "Closes #12" "Closes #13"
  mark "$forge"
  expect_rc 0
  expect_line out "#12 is not open: left alone."
  expect_line out "Marked #13 done."
  expect_labels 12 "in work"
  expect_no_comment 12
  expect_labels 13 finished

  start "$forge: an issue whose label cannot be changed fails the run, the others are still marked"
  issue 12 open "in work"
  issue 13 open "in work"
  echo "$fail_label_write" >"$STUB_DIR/fail"
  message "Subject (#54)" "" "Closes #12" "Closes #13"
  mark "$forge"
  expect_rc 1
  expect_line err "Could not mark #12 done."
  expect_line out "Marked #13 done."
  expect_labels 12 "in work"
  expect_no_comment 12
  expect_labels 13 finished
  expect_comment 13 "$with_pull_request"

  start "$forge: a comment that fails after the label fails the run; the next run leaves the issue alone"
  issue 12 open "in work"
  echo "$fail_comment" >"$STUB_DIR/fail"
  message "Subject (#54)" "" "Closes #12"
  mark "$forge"
  expect_rc 1
  expect_line err "Could not mark #12 done."
  expect_labels 12 finished
  rm "$STUB_DIR/fail"
  mark "$forge"
  expect_rc 0
  expect_line out "#12 is done already: left alone."
  expect_no_writes
  expect_state 12 open
done

start "github: an issue gh cannot look up fails the run, the others are still marked"
issue 13 open
# There is no issue 99.
message "Subject (#54)" "" "Closes #99" "Closes #13"
mark github
expect_rc 1
expect_line err "Could not mark #99 done."
expect_line out "Marked #13 done."
expect_labels 13 finished

start "gitlab: an issue GitLab does not list is not open: left alone"
issue 13 open
# There is no issue 77.
message "Subject (#5)" "" "Closes #77" "Closes #13"
mark gitlab
expect_rc 0
expect_line out "#77 is not open: left alone."
expect_line out "Marked #13 done."
grep -q "^glab api .*projects/42/issues" "$STUB_DIR/calls" || fail "no glab api call for project 42"

start "a message without Closes lines marks nothing"
issue 12 open "in work"
message "Refactor the tests (#54)" "" "Mentions #12, closes nothing."
mark github
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to mark done."
expect_labels 12 "in work"
expect_no_calls

start "a Closes line followed by other text marks nothing"
issue 12 open
message "Subject (#54)" "" "Closes #12" "" "More text after it."
mark github
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to mark done."
expect_no_calls

start "a last line that says more than Closes #N marks nothing"
issue 12 open
issue 13 open
message "Subject (#54)" "" "Closes #12 and #13"
mark github
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to mark done."
expect_no_calls

start "only the trailing run of Closes lines counts"
issue 12 open
issue 13 open
issue 14 open
message "Subject (#54)" "" "Closes #12" "See #14 for the rest." "Closes #13"
mark github
expect_rc 0
expect_line out "Marked #13 done."
expect_labels 13 finished
expect_labels 12
expect_labels 14

start "trailing spaces, a carriage return and blank lines at the end still count"
issue 12 open
issue 13 open
message "Subject (#54)" "" "Closes #12  " "$(printf 'Closes #13\r')" "" ""
mark github
expect_rc 0
expect_labels 12 finished
expect_labels 13 finished

for forge in github gitlab; do
  start "$forge: the message's text reaches neither a command nor the comment"
  issue 12 open
  # The dollar sign and the backticks are meant literally: they are the attack.
  # shellcheck disable=SC2016
  message 'Fix $(touch pwned) `touch pwned` "quoted" (#54)' "" "Closes #12"
  mark "$forge"
  expect_rc 0
  if [ -e "$tmp/pwned" ]; then
    fail "the message's text was run as a command"
  fi
  expect_comment 12 "$with_pull_request"
done

for arguments in "" "bitbucket $sha $labels" "github" "github $sha" "github not-a-commit $labels" \
  "github 123456 $labels" "github $sha $labels extra"; do
  start "usage error: mark-done.sh $arguments"
  issue 12 open
  message "Subject (#54)" "" "Closes #12"
  # The arguments are split on purpose.
  # shellcheck disable=SC2086
  run $arguments
  expect_rc 2
  grep -q '^usage: mark-done.sh ' "$tmp/err" || fail "no usage line on stderr, which has: $(cat "$tmp/err")"
  expect_labels 12
  expect_no_calls
done

start "a labels file that cannot be read stops the run before any call"
issue 12 open
message "Subject (#54)" "" "Closes #12"
run github "$sha" "$tmp/no-such-labels.tsv"
expect_rc 2
expect_line err "$tmp/no-such-labels.tsv: cannot read."
expect_no_calls

for kanban in "done" in-progress; do
  start "a labels file that lacks the $kanban label stops the run before any call, on GitLab without its token too"
  grep -v "$tab$kanban$tab" "$labels" >"$tmp/labels.tsv"
  issue 12 open
  message "Subject (#54)" "" "Closes #12"
  run github "$sha" "$tmp/labels.tsv"
  expect_rc 2
  expect_line err "$tmp/labels.tsv: no label with kanban \"$kanban\"."
  expect_no_calls
  unset GITLAB_TOKEN
  run gitlab "$sha" "$tmp/labels.tsv"
  GITLAB_TOKEN=test-token
  export GITLAB_TOKEN
  expect_rc 2
  expect_line err "$tmp/labels.tsv: no label with kanban \"$kanban\"."
  expect_no_calls
done

start "gitlab without its token says so, marks nothing and passes"
issue 12 open "in work"
issue 13 open
message "Subject (#5)" "" "Closes #12" "Closes #13"
unset GITLAB_TOKEN
mark gitlab
GITLAB_TOKEN=test-token
export GITLAB_TOKEN
expect_rc 0
expect_line out "GITLAB_TOKEN is not set (a project access token that may edit issues and labels): not marking #12, #13 done."
expect_labels 12 "in work"
expect_labels 13
expect_no_calls

start ""
if [ "$failures" -gt 0 ]; then
  echo "mark-done.sh: $failures check(s) failed."
  exit 1
fi
echo "mark-done.sh: every case passes."
