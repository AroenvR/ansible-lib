#!/bin/sh
# Closes the issues that a commit on the base branch names in the "Closes #N"
# lines at the end of its message, with a comment naming the commit (and its
# pull request, when the subject ends in " (#M)"). Issues already closed are
# left alone, so a second run on the same commit changes nothing. CI runs it on
# every push to the base branch.
#   usage: close-issues.sh <github|gitlab> <commit sha> < message
# github: gh, with GH_TOKEN (a token that may write issues) and GH_REPO (owner/name).
# gitlab: glab, with GITLAB_TOKEN (a project access token that may close
#   issues), GITLAB_HOST (the server's URL) and CI_PROJECT_ID. Without
#   GITLAB_TOKEN it says so and closes nothing.
# Only digits are taken from the message: its text never reaches a command or
# the comment. Exit 0: done, or nothing to do; 1: an issue could not be checked
# or closed (the others are still handled); 2: usage.
set -eu

usage() {
  echo "usage: close-issues.sh <github|gitlab> <commit sha> < message" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
forge=$1
sha=$2
case $forge in
  github | gitlab) ;;
  *) usage ;;
esac
case $sha in
  *[!0-9a-fA-F]*) usage ;;
esac
if [ "${#sha}" -lt 7 ] || [ "${#sha}" -gt 64 ]; then
  usage
fi

message=$(cat)

# The trailing run of "Closes #N" lines (after trailing blank lines), top to
# bottom, each issue once.
issues=$(printf '%s\n' "$message" | awk '
  { line[NR] = $0 }
  END {
    last = NR
    while (last > 0 && line[last] ~ /^[ \t\r]*$/) last--
    first = last + 1
    while (first > 1 && line[first - 1] ~ /^Closes #[1-9][0-9]*[ \r]*$/) first--
    for (i = first; i <= last; i++) {
      n = line[i]
      sub(/^Closes #/, "", n)
      sub(/[ \r]*$/, "", n)
      if (!(n in seen)) { seen[n] = 1; print n }
    }
  }')

if [ -z "$issues" ]; then
  echo "No \"Closes #N\" lines at the end of $sha's message: nothing to close."
  exit 0
fi

# The pull request's number, when the subject ends in " (#M)".
pull_request=$(printf '%s\n' "$message" | awk '
  NR == 1 {
    sub(/[ \r]*$/, "")
    if (match($0, / \(#[1-9][0-9]*\)$/)) print substr($0, RSTART + 3, RLENGTH - 4)
    exit
  }')
if [ -n "$pull_request" ]; then
  comment="Closed by commit $sha (pull request #$pull_request)."
else
  comment="Closed by commit $sha."
fi

if [ "$forge" = gitlab ] && [ -z "${GITLAB_TOKEN:-}" ]; then
  list=
  for issue in $issues; do
    list="${list:+$list, }#$issue"
  done
  echo "GITLAB_TOKEN is not set (a project access token that may close issues): not closing $list."
  exit 0
fi

# Prints "open" or "closed" for issue $1; fails when the forge cannot tell.
issue_state() {
  if [ "$forge" = github ]; then
    answer=$(gh issue view "$1" --json state --jq .state) || return 1
    if [ "$answer" = OPEN ]; then echo open; else echo closed; fi
  else
    # GitLab answers [] when no open issue has this number.
    found=$(glab api "projects/$CI_PROJECT_ID/issues?iids[]=$1&state=opened") || return 1
    if [ "$(printf '%s' "$found" | tr -d ' \t\r\n')" = "[]" ]; then echo closed; else echo open; fi
  fi
}

# Comments on issue $1 and closes it.
close_issue() {
  if [ "$forge" = github ]; then
    gh issue close "$1" --reason completed --comment "$comment" >/dev/null
  else
    glab api --method POST "projects/$CI_PROJECT_ID/issues/$1/notes" --raw-field "body=$comment" >/dev/null &&
      glab api --method PUT "projects/$CI_PROJECT_ID/issues/$1" --raw-field state_event=close >/dev/null
  fi
}

failed=0
for issue in $issues; do
  if ! state=$(issue_state "$issue"); then
    echo "Could not close #$issue." >&2
    failed=1
  elif [ "$state" != open ]; then
    echo "#$issue is not open: left alone."
  elif close_issue "$issue"; then
    echo "Closed #$issue."
  else
    echo "Could not close #$issue." >&2
    failed=1
  fi
done
exit "$failed"
