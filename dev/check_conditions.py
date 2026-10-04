"""Fail when a condition in a playbook or task file is not text.

YAML reads a plain list item that contains ': ' as a mapping, so an assert like
  - lookup('file', f) is search('key: value')
becomes {"lookup(...) is search('key": "value')"}, which ansible-core 2.12 and 2.14
accept and treat as true: the check silently checks nothing. ansible-lint does not
notice. Quote such conditions: - "lookup('file', f) is search('key: value')"
"""

import sys
from pathlib import Path

import yaml

CONDITION_KEYS = ("when", "failed_when", "changed_when", "until")
NESTED_KEYS = ("block", "rescue", "always", "tasks", "pre_tasks", "post_tasks", "handlers")


def conditions(task: dict) -> list:
    found = []
    check = task.get("ansible.builtin.assert")
    if isinstance(check, dict) and "that" in check:
        found += check["that"] if isinstance(check["that"], list) else [check["that"]]
    for key in CONDITION_KEYS:
        if key in task:
            found += task[key] if isinstance(task[key], list) else [task[key]]
    return found


def walk(items, path: Path, errors: list) -> None:
    for task in items or []:
        if not isinstance(task, dict):
            continue
        for key in NESTED_KEYS:
            if isinstance(task.get(key), list):
                walk(task[key], path, errors)
        for condition in conditions(task):
            if not isinstance(condition, (str, bool)):
                errors.append(f"{path}: task '{task.get('name')}': condition is not text: {condition!r}")


errors: list = []
for path in sorted([*Path("roles").glob("**/*.yml"), *Path("playbooks").glob("*.yml"), *Path(".").glob("*.yml")]):
    content = yaml.safe_load(path.read_text())
    if isinstance(content, list):
        walk(content, path, errors)

print("\n".join(errors) or "Every condition is text.")
sys.exit(1 if errors else 0)
