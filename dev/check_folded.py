"""Fail when a folded YAML block (>) keeps a line break before a shell operator.

YAML joins the lines of a folded block with spaces, but keeps the line break
before a line indented further than the block's first line. In a shell command
such a line that starts with &&, ||, | or ; then starts a new line of the
script, which is a syntax error that shows only when the command runs:
  script: >-
    systemctl restart foo
      || echo failed
reaches bash as "systemctl restart foo\n  || echo failed". Indent every line of
the block the same. A block that is a Jinja expression ({{ ... }}) may keep its
line breaks: Jinja ignores them.
"""

import re
import sys
from pathlib import Path

import yaml

KEPT_OPERATOR = re.compile(r"\n[ \t]*(&&|\|\||\||;)")


def scalars(node):
    if isinstance(node, yaml.ScalarNode):
        yield node
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from scalars(item)
    elif isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            yield from scalars(key)
            yield from scalars(value)


errors: list = []
for path in sorted([*Path("roles").glob("**/*.yml"), *Path("playbooks").glob("*.yml"), *Path("dev").glob("**/*.yml"),
                    *Path(".").glob("*.yml")]):
    for document in yaml.compose_all(path.read_text()):
        for node in scalars(document) if document is not None else []:
            if node.style == ">" and not node.value.lstrip().startswith("{{") and KEPT_OPERATOR.search(node.value):
                errors.append(f"{path}:{node.start_mark.line + 1}: a folded block keeps a line break before a shell "
                              "operator; indent its lines the same")

print("\n".join(errors) or "No folded block keeps a line break before a shell operator.")
sys.exit(1 if errors else 0)
