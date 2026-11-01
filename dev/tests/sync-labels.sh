#!/bin/sh
# Tests dev/ci/sync-labels.sh, which makes the forge's labels match the labels
# file: it creates the missing ones, corrects a changed color or description,
# and reports a label the file doesn't list without deleting it. On GitHub with
# gh, on GitLab with glab: the stand-ins in bin/ take the place of both and keep
# the forge's labels and every call in a scratch directory.
# Run: sh dev/tests/sync-labels.sh (make test-scripts runs every test here).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$here/.." && pwd)/ci/sync-labels.sh
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
escape=$(printf '\033')

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

# The forge's labels before the sync, one per argument: name, color and
# description separated by "|".
forge_labels() {
  printf '%s\n' "$@" | tr '|' '\t' >"$STUB_DIR/labels"
}

# The forge of the main cases. Against the file: core and plan are equal,
# parked differs only in the case of its color; tools and agents has an old
# description, finished an old color, epic item no description; in work and
# documentation are missing; wontfix and a name with an escape sequence are not
# in the file.
board() {
  forge_labels \
    "core|1d76db|Shared code, the build and the release." \
    "tools and agents|5319e7|Development tools." \
    "parked|C5DEF5|Not now: do not claim it." \
    "finished|000000|Merged into develop; it closes when the change reaches the default branch." \
    "epic item|3e4b9e|" \
    "plan|d4c5f9|Lists the issues of a larger piece of work as a task list." \
    "wontfix|ffffff|This will not be worked on" \
    "bad${escape}[31mname|ededed|Made by hand."
}

# run <argument>...: the script, with fresh call logs.
run() {
  : >"$STUB_DIR/calls"
  : >"$STUB_DIR/writes"
  sh "$script" "$@" </dev/null >"$tmp/out" 2>"$tmp/err"
  rc=$?
}

# sync <github|gitlab> [<labels file>]: the script on that forge.
sync() {
  run "$1" "${2:-$labels}"
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

# expect_forge_label <name> <color> <description>: the label on the forge, its
# color compared in lower case.
expect_forge_label() {
  row=$(name=$1 awk -F'\t' '$1 == ENVIRON["name"]' "$STUB_DIR/labels")
  if [ -z "$row" ]; then
    fail "no label \"$1\" on the forge"
    return
  fi
  [ "$(printf '%s\n' "$row" | wc -l)" -eq 1 ] || fail "the forge has \"$1\" more than once"
  color=$(printf '%s\n' "$row" | cut -f 2 | tr 'A-F' 'a-f')
  description=$(printf '%s\n' "$row" | cut -f 3)
  [ "$color" = "$2" ] || fail "\"$1\" has the color $color on the forge, expected $2"
  [ "$description" = "$3" ] || fail "\"$1\" has the description \"$description\" on the forge, expected \"$3\""
}

# Every label of the file is on the forge as the file says.
expect_forge_matches_file() {
  tail -n +2 "$1" >"$tmp/rows"
  while IFS="$tab" read -r file_name file_color file_kanban file_description; do
    : "$file_kanban"
    expect_forge_label "$file_name" "$file_color" "$file_description"
  done <"$tmp/rows"
}

for forge in github gitlab; do
  case $forge in
    github)
      fail_list="gh label list *"
      fail_create="gh label create *"
      fail_update="gh label edit finished *"
      ;;
    gitlab)
      fail_list="glab GET projects/42/labels*"
      fail_create="glab POST projects/42/labels"
      # finished is the fourth label on the forge.
      fail_update="glab PUT projects/42/labels/104"
      ;;
  esac

  start "$forge: missing labels are created, a changed color or description corrected, others reported and left; a second run writes nothing"
  board
  sync "$forge"
  expect_rc 0
  expect_line out "Created label \"in work\"."
  expect_line out "Created label \"documentation\"."
  expect_line out "Updated label \"tools and agents\"."
  expect_line out "Updated label \"finished\"."
  expect_line out "Updated label \"epic item\"."
  expect_line out "Label \"wontfix\" is not in $labels: left alone."
  expect_line out "Label \"bad[31mname\" is not in $labels: left alone."
  if grep -q "$escape" "$tmp/out" "$tmp/err"; then
    fail "a control character from the forge was printed"
  fi
  expect_writes 5
  expect_forge_matches_file "$labels"
  expect_forge_label wontfix ffffff "This will not be worked on"
  # The case of a color does not count.
  grep -q "^parked${tab}C5DEF5$tab" "$STUB_DIR/labels" || fail "parked's color was rewritten"
  sync "$forge"
  expect_rc 0
  expect_line out "The labels match $labels."
  expect_line out "Label \"wontfix\" is not in $labels: left alone."
  expect_no_writes

  start "$forge: labels that cannot be listed change nothing and fail the run"
  board
  echo "$fail_list" >"$STUB_DIR/fail"
  sync "$forge"
  expect_rc 1
  expect_line err "Could not list the labels."
  expect_no_writes

  start "$forge: labels that cannot be created fail the run, the others are still corrected"
  board
  echo "$fail_create" >"$STUB_DIR/fail"
  sync "$forge"
  expect_rc 1
  expect_line err "Could not create label \"in work\"."
  expect_line err "Could not create label \"documentation\"."
  expect_forge_label finished 0e8a16 "Merged into develop; it closes when the change reaches the default branch."
  expect_forge_label "tools and agents" 5319e7 "Development tools and the agents that use them."

  start "$forge: a label that cannot be corrected fails the run, the others are still synced"
  board
  echo "$fail_update" >"$STUB_DIR/fail"
  sync "$forge"
  expect_rc 1
  expect_line err "Could not update label \"finished\"."
  expect_forge_label finished 000000 "Merged into develop; it closes when the change reaches the default branch."
  expect_forge_label "in work" fbca04 "Someone works on it: a branch issue/<N> exists. Set and removed by CI."
  expect_forge_label "epic item" 3e4b9e "An open plan issue lists it as a task."
done

start "github: a name that differs from the forge's only in case cannot be created and fails the run"
board
sed "s/^finished$tab/Finished$tab/" "$labels" >"$tmp/labels.tsv"
sync github "$tmp/labels.tsv"
expect_rc 1
expect_line err "Could not create label \"Finished\"."
expect_line out "Label \"finished\" is not in $tmp/labels.tsv: left alone."

start "gitlab without its token says so, syncs nothing and passes"
board
unset GITLAB_TOKEN
sync gitlab
GITLAB_TOKEN=test-token
export GITLAB_TOKEN
expect_rc 0
expect_line out "GITLAB_TOKEN is not set (a project access token that may edit issues and labels): not syncing the labels."
expect_no_calls

# Each in place of the fourth line, in work's.
for bad_line in "in work${tab}fbca04${tab}in-progress" "in work${tab}fbca04${tab}in-progress${tab}Taken.${tab}more" \
  "in work${tab}#fbca04${tab}in-progress${tab}Taken." "in work${tab}fbca0${tab}in-progress${tab}Taken." \
  "in work${tab}fbca0g${tab}in-progress${tab}Taken."; do
  start "a labels file with the line \"$(printf '%s' "$bad_line" | tr '\t' ' ')\" stops the run before any call, on GitLab without its token too"
  board
  {
    head -n 3 "$labels"
    printf '%s\n' "$bad_line"
    tail -n +5 "$labels"
  } >"$tmp/labels.tsv"
  sync github "$tmp/labels.tsv"
  expect_rc 2
  expect_line err "$tmp/labels.tsv:4: not \"name<TAB>color<TAB>kanban<TAB>description\"."
  expect_no_calls
  unset GITLAB_TOKEN
  sync gitlab "$tmp/labels.tsv"
  GITLAB_TOKEN=test-token
  export GITLAB_TOKEN
  expect_rc 2
  expect_line err "$tmp/labels.tsv:4: not \"name<TAB>color<TAB>kanban<TAB>description\"."
  expect_no_calls
done

start "a labels file that cannot be read stops the run before any call"
board
sync github "$tmp/no-such-labels.tsv"
expect_rc 2
expect_line err "$tmp/no-such-labels.tsv: cannot read."
expect_no_calls

for arguments in "" "bitbucket $labels" "github" "github $labels extra"; do
  start "usage error: sync-labels.sh $arguments"
  board
  # The arguments are split on purpose.
  # shellcheck disable=SC2086
  run $arguments
  expect_rc 2
  grep -q '^usage: sync-labels.sh ' "$tmp/err" || fail "no usage line on stderr, which has: $(cat "$tmp/err")"
  expect_no_calls
done

start ""
if [ "$failures" -gt 0 ]; then
  echo "sync-labels.sh: $failures check(s) failed."
  exit 1
fi
echo "sync-labels.sh: every case passes."
