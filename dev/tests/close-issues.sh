#!/bin/sh
# Tests dev/ci/close-issues.sh, which closes the issues named by the "Closes #N"
# lines at the end of a commit message (given on stdin), on GitHub with gh or on
# GitLab with glab. The stand-ins in bin/ take the place of both tools and keep
# each issue's state, the comments and every call in a scratch directory.
# Run: sh dev/tests/close-issues.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/ci/close-issues.sh
if [ ! -f "$script" ]; then
  echo "FAIL: $script does not exist: nothing to test yet."
  exit 1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
cd "$tmp"
unset GH_REPO GH_TOKEN GH_HOST GITHUB_TOKEN GITLAB_TOKEN GITLAB_HOST CI_PROJECT_ID
# What the GitHub job gives the script; the GitLab cases set their own.
GH_TOKEN=test-token
GH_REPO=example/project
PATH=$here/bin:$PATH
STUB_DIR=$tmp/stubs
export GH_TOKEN GH_REPO PATH STUB_DIR
sha=0123456789abcdef0123456789abcdef01234567
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

set_open() {
  for number in "$@"; do echo OPEN >"$STUB_DIR/issue-$number"; done
}

set_closed() {
  for number in "$@"; do echo CLOSED >"$STUB_DIR/issue-$number"; done
}

# The commit message, one argument per line.
message() {
  printf '%s\n' "$@" >"$tmp/message"
}

run_close() {
  sh "$script" "$@" <"$tmp/message" >"$tmp/out" 2>"$tmp/err"
  rc=$?
}

expect_rc() {
  [ "$rc" -eq "$1" ] || fail "exit code $rc, expected $1; stdout: $(cat "$tmp/out"); stderr: $(cat "$tmp/err")"
}

# expect_line <out|err> <line>: the line, exactly, on stdout or stderr.
expect_line() {
  grep -Fxq -e "$2" "$tmp/$1" || fail "no line \"$2\" on std$1, which has: $(cat "$tmp/$1")"
}

expect_state() {
  state=$(cat "$STUB_DIR/issue-$1")
  [ "$state" = "$2" ] || fail "#$1 is $state, expected $2"
}

expect_comment() {
  if [ ! -f "$STUB_DIR/comment-$1" ]; then
    fail "no comment on #$1"
  elif [ "$(cat "$STUB_DIR/comment-$1")" != "$2" ]; then
    fail "comment on #$1 is \"$(cat "$STUB_DIR/comment-$1")\", expected \"$2\""
  fi
}

expect_no_comment() {
  [ ! -f "$STUB_DIR/comment-$1" ] || fail "a comment on #$1: $(cat "$STUB_DIR/comment-$1")"
}

expect_no_calls() {
  [ ! -s "$STUB_DIR/calls" ] || fail "gh or glab was called: $(cat "$STUB_DIR/calls")"
}

# How many calls of the stand-ins begin with the given words.
calls() {
  grep -c "^$1" "$STUB_DIR/calls"
}

start "one trailing Closes line closes the issue, naming the commit and the pull request"
set_open 12
message "Add the claim command (#54)" "" "What it does." "" "Closes #12"
run_close github "$sha"
expect_rc 0
expect_line out "Closed #12."
expect_state 12 CLOSED
expect_comment 12 "Closed by commit $sha (pull request #54)."
[ "$(calls "gh issue close 12 ")" -eq 1 ] || fail "gh issue close 12 was not called once"
grep -q '^gh issue close 12 .*--reason completed' "$STUB_DIR/calls" || fail "not closed as completed"

start "a second run on the same commit leaves the closed issue alone"
set_closed 12
run_close github "$sha"
expect_rc 0
expect_line out "#12 is not open: left alone."
expect_no_comment 12
[ "$(calls "gh issue close")" -eq 0 ] || fail "gh issue close was called"

start "two trailing Closes lines close both, top to bottom, each once; no pull request in the subject"
set_open 12 13
message "Fix two things on develop" "" "Closes #12" "Closes #13" "Closes #12"
run_close github "$sha"
expect_rc 0
[ "$(grep '^Closed #' "$tmp/out")" = "$(printf 'Closed #12.\nClosed #13.')" ] ||
  fail "expected \"Closed #12.\" then \"Closed #13.\" on stdout, which has: $(cat "$tmp/out")"
[ "$(grep -c '#12[^0-9]' "$tmp/out")" -eq 1 ] || fail "#12 handled more than once: $(cat "$tmp/out")"
expect_state 12 CLOSED
expect_state 13 CLOSED
expect_comment 12 "Closed by commit $sha."
expect_comment 13 "Closed by commit $sha."

start "an issue already closed is left alone, the open one is closed"
set_closed 12
set_open 13
message "Subject (#54)" "" "Closes #12" "Closes #13"
run_close github "$sha"
expect_rc 0
expect_line out "#12 is not open: left alone."
expect_line out "Closed #13."
expect_no_comment 12
[ "$(calls "gh issue close 12 ")" -eq 0 ] || fail "gh issue close 12 was called"
expect_state 13 CLOSED

start "a message without Closes lines closes nothing"
set_open 12
message "Refactor the tests (#54)" "" "Mentions #12, closes nothing."
run_close github "$sha"
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to close."
expect_state 12 OPEN
expect_no_calls

start "a Closes line followed by other text closes nothing"
set_open 12
message "Subject (#54)" "" "Closes #12" "" "More text after it."
run_close github "$sha"
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to close."
expect_state 12 OPEN
expect_no_calls

start "a last line that says more than Closes #N closes nothing"
set_open 12 13
message "Subject (#54)" "" "Closes #12 and #13"
run_close github "$sha"
expect_rc 0
expect_line out "No \"Closes #N\" lines at the end of $sha's message: nothing to close."
expect_state 12 OPEN
expect_no_calls

start "only the trailing run of Closes lines counts"
set_open 12 13 14
message "Subject (#54)" "" "Closes #12" "See #14 for the rest." "Closes #13"
run_close github "$sha"
expect_rc 0
expect_line out "Closed #13."
expect_state 13 CLOSED
expect_state 12 OPEN
expect_state 14 OPEN

start "trailing spaces, a carriage return and blank lines at the end still count"
set_open 12 13
message "Subject (#54)" "" "Closes #12  " "$(printf 'Closes #13\r')" "" ""
run_close github "$sha"
expect_rc 0
expect_state 12 CLOSED
expect_state 13 CLOSED

start "the message's text reaches neither a command nor the comment"
set_open 12
# The dollar sign and the backticks are meant literally: they are the attack.
# shellcheck disable=SC2016
message 'Fix $(touch pwned) `touch pwned` "quoted" (#54)' "" "Closes #12"
run_close github "$sha"
expect_rc 0
if [ -e "$tmp/pwned" ]; then
  fail "the message's text was run as a command"
fi
expect_comment 12 "Closed by commit $sha (pull request #54)."

start "an issue that cannot be checked or closed fails the run, the others are still closed"
set_open 12 13
touch "$STUB_DIR/fail-close-12"
# There is no issue 99: gh cannot look it up.
message "Subject (#54)" "" "Closes #12" "Closes #99" "Closes #13"
run_close github "$sha"
expect_rc 1
expect_line err "Could not close #12."
expect_line err "Could not close #99."
expect_line out "Closed #13."
expect_state 13 CLOSED

for arguments in "" "bitbucket $sha" "github" "github not-a-commit" "github 123456"; do
  start "usage error: close-issues.sh $arguments"
  set_open 12
  message "Subject (#54)" "" "Closes #12"
  # The arguments are split on purpose.
  # shellcheck disable=SC2086
  run_close $arguments
  expect_rc 2
  expect_line err "usage: close-issues.sh <github|gitlab> <commit sha> < message"
  expect_state 12 OPEN
  expect_no_calls
done

GITLAB_HOST=https://gitlab.example.invalid
CI_PROJECT_ID=42
export GITLAB_HOST CI_PROJECT_ID

start "gitlab with its token closes the open issues; closed and missing ones are left alone"
GITLAB_TOKEN=test-token
export GITLAB_TOKEN
set_open 12
set_closed 13
# There is no issue 77.
message "Subject (#5)" "" "Closes #12" "Closes #13" "Closes #77"
run_close gitlab "$sha"
expect_rc 0
expect_line out "Closed #12."
expect_line out "#13 is not open: left alone."
expect_line out "#77 is not open: left alone."
expect_state 12 CLOSED
expect_state 13 CLOSED
expect_comment 12 "Closed by commit $sha (pull request #5)."
expect_no_comment 13
[ "$(calls gh)" -eq 0 ] || fail "gh was called on GitLab"
[ "$(calls "glab api .*projects/42/issues")" -gt 0 ] || fail "no glab api call for project 42"
unset GITLAB_TOKEN

start "gitlab without its token says so, closes nothing and passes"
set_open 12 13
message "Subject (#5)" "" "Closes #12" "Closes #13"
run_close gitlab "$sha"
expect_rc 0
expect_line out "GITLAB_TOKEN is not set (a project access token that may close issues): not closing #12, #13."
expect_state 12 OPEN
expect_state 13 OPEN
expect_no_calls

start ""
if [ "$failures" -gt 0 ]; then
  echo "close-issues.sh: $failures check(s) failed."
  exit 1
fi
echo "close-issues.sh: every case passes."
