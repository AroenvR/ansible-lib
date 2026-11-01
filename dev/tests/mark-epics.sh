#!/bin/sh
# Tests dev/ci/mark-epics.sh, which labels an open issue epic exactly while an
# open index issue lists it as a task-list item that starts with its reference
# ("- [ ] #5", "1. [x] #6"); other mentions in an index don't count, and closed
# issues are never touched. On GitHub with gh, on GitLab with glab: the
# stand-ins in bin/ take the place of both and keep the issues, their labels
# and bodies and every call in a scratch directory. The labels file of the
# tests calls epic "epic item" and index "plan", unlike the project's own, so a
# label name written into the script shows.
# Run: sh dev/tests/mark-epics.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/ci/mark-epics.sh
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
cr=$(printf '\r')

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

# issue <N> <open|closed> [<label>...]: an issue on the forge, without a body.
issue() {
  issue_dir=$STUB_DIR/issues/$1
  mkdir -p "$issue_dir"
  echo "$2" >"$issue_dir/state"
  shift 2
  : >"$issue_dir/labels"
  : >"$issue_dir/body"
  for label in "$@"; do
    printf '%s\n' "$label" >>"$issue_dir/labels"
  done
}

# body <N> <line>...: the issue's body, one argument per line.
body() {
  number=$1
  shift
  printf '%s\n' "$@" >"$STUB_DIR/issues/$number/body"
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

# Two open indexes and a closed one, and what becomes of the issues they name.
board() {
  issue 1 open plan
  body 1 "The plan for the next release." "" "- [ ] #5" "1. [x] #6" "" \
    "Note: #7 was split off from #5, see the history."
  issue 2 open plan
  body 2 "Another plan." "" "- [ ] #5" "- [ ] #20"
  issue 3 closed plan
  body 3 "An old plan." "" "- [ ] #21"
  issue 5 open                # listed by both open indexes: gets it once
  issue 6 open                # listed as a done task: gets it
  issue 7 open                # only mentioned in a note: does not get it
  issue 20 open "epic item"   # listed, labelled already: stays
  issue 21 open "epic item"   # listed by the closed index only: loses it
  issue 22 open "epic item"   # listed by no index: loses it
  issue 23 closed "epic item" # closed: never touched
  issue 24 open               # not an index, so its task list does not count
  body 24 "- [ ] #25"
  issue 25 open
}

for forge in github gitlab; do
  case $forge in
    github)
      fail_snapshot="gh issue list *"
      fail_bodies="gh issue list *--label*"
      fail_label_5="gh issue edit 5 *"
      fail_unlabel_22="gh issue edit 22 *"
      ;;
    gitlab)
      fail_snapshot="glab GET projects/42/issues*"
      fail_bodies=$fail_snapshot
      fail_label_5="glab PUT projects/42/issues/5"
      fail_unlabel_22="glab PUT projects/42/issues/22"
      ;;
  esac

  start "$forge: issues an open index lists as tasks get epic, others lose it, closed ones are left; a second run writes nothing"
  board
  label "$forge"
  expect_rc 0
  [ "$(grep '^Labelled #' "$tmp/out")" = "$(printf '%s\n' \
    'Labelled #5 "epic item": an open index lists it.' \
    'Labelled #6 "epic item": an open index lists it.')" ] ||
    fail "expected #5 then #6 labelled on stdout, which has: $(cat "$tmp/out")"
  [ "$(grep '^Removed ' "$tmp/out")" = "$(printf '%s\n' \
    'Removed "epic item" from #21: no open index lists it.' \
    'Removed "epic item" from #22: no open index lists it.')" ] ||
    fail "expected \"epic item\" removed from #21 then #22 on stdout, which has: $(cat "$tmp/out")"
  expect_writes 4
  expect_labels 5 "epic item"
  expect_labels 6 "epic item"
  expect_labels 7
  expect_labels 20 "epic item"
  expect_labels 21
  expect_labels 22
  expect_labels 23 "epic item"
  expect_labels 25
  expect_labels 1 plan
  expect_labels 2 plan
  label "$forge"
  expect_rc 0
  expect_line out "\"epic item\" matches the open indexes: nothing to change."
  expect_no_writes

  start "$forge: which lines of an index list an issue"
  issue 1 open plan
  # Numbered like the issues they name: 8 to 11, 29 and 30 count; the others
  # don't. 26 is closed, 99 and 190 do not exist.
  # The dollar sign and the backticks are meant literally: they are the attack.
  # shellcheck disable=SC2016
  body 1 "Items:" \
    "${tab}- [ ] #8: indented with a tab" \
    "  * [X] #9 nested" \
    "+ [ ] #10$cr" \
    "2) [ ] #11" \
    "10. [ ] #29" \
    '- [ ] #30 $(touch pwned) `touch pwned`' \
    "- [ ] see #12" \
    "- #13" \
    "> - [ ] #14" \
    "- [ ] o/r#15" \
    "- [~] #16" \
    "- [ ] https://forge.example.invalid/o/r/issues/17" \
    "- [ ] #190" \
    "-[ ] #27" \
    "- [ ]#28" \
    "- [ ] #26" \
    "- [ ] #99"
  for number in 8 9 10 11 12 13 14 15 16 17 19 27 28 29 30; do
    issue "$number" open
  done
  issue 26 closed
  label "$forge"
  expect_rc 0
  for number in 8 9 10 11 29 30; do
    expect_labels "$number" "epic item"
  done
  for number in 12 13 14 15 16 17 19 26 27 28; do
    expect_labels "$number"
  done
  expect_writes 6
  if [ -e "$STUB_DIR/issues/99" ] || [ -e "$STUB_DIR/issues/190" ]; then
    fail "an issue that does not exist was made"
  fi
  if [ -e "$tmp/pwned" ]; then
    fail "an index's text was run as a command"
  fi

  start "$forge: issues that cannot be listed change nothing and fail the run"
  board
  echo "$fail_snapshot" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not list the issues: nothing changed."
  expect_no_writes

  start "$forge: index bodies that cannot be read change nothing and fail the run"
  board
  echo "$fail_bodies" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not list the issues: nothing changed."
  expect_no_writes

  start "$forge: an issue that cannot be labelled or unlabelled fails the run, the others are still handled"
  board
  printf '%s\n' "$fail_label_5" "$fail_unlabel_22" >"$STUB_DIR/fail"
  label "$forge"
  expect_rc 1
  expect_line err "Could not label #5."
  expect_line err "Could not unlabel #22."
  expect_labels 5
  expect_labels 22 "epic item"
  expect_labels 6 "epic item"
  expect_labels 21
done

start "gitlab without its token says so, changes nothing and passes"
board
unset GITLAB_TOKEN
label gitlab
GITLAB_TOKEN=test-token
export GITLAB_TOKEN
expect_rc 0
expect_line out "GITLAB_TOKEN is not set (a project access token that may edit issues and labels): not labelling the epics."
expect_labels 5
expect_labels 22 "epic item"
expect_no_calls

start "a labels file that cannot be read stops the run before any call"
board
run github "$tmp/no-such-labels.tsv"
expect_rc 2
expect_line err "$tmp/no-such-labels.tsv: cannot read."
expect_no_calls

for kanban in epic index; do
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
  start "usage error: mark-epics.sh $arguments"
  board
  # The arguments are split on purpose.
  # shellcheck disable=SC2086
  run $arguments
  expect_rc 2
  grep -q '^usage: mark-epics.sh ' "$tmp/err" || fail "no usage line on stderr, which has: $(cat "$tmp/err")"
  expect_no_calls
done

start ""
if [ "$failures" -gt 0 ]; then
  echo "mark-epics.sh: $failures check(s) failed."
  exit 1
fi
echo "mark-epics.sh: every case passes."
