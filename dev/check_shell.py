"""Run ShellCheck on every shell script of the collection.

A shell script is a file whose first line is a shell's #! line. Templates of
shell scripts (*.j2) are rendered first, with every variable set to a
placeholder, so ShellCheck sees the script as the server gets it. The
maintainer's own tooling (.tools/, libs/) is theirs to check.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import jinja2

SKIP = {".git", ".venv", "dist", "tmp", ".tools", "libs"}
SHEBANG = re.compile(r"^#!\s*/(usr/)?bin/(env\s+)?(ba|da|k)?sh\b")


class Placeholder(jinja2.ChainableUndefined):
    """Any variable a template uses, rendered as a plain word."""

    def __str__(self) -> str:
        return "placeholder"


def dict2items(value) -> list:
    """Ansible's filter: a placeholder has no items."""
    return [{"key": k, "value": v} for k, v in value.items()] if isinstance(value, dict) else []


# The Ansible filters the shell templates use.
FILTERS = {"quote": lambda value: shlex.quote(str(value)), "dict2items": dict2items}


def scripts() -> list:
    found = []
    for root, dirs, files in os.walk("."):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files):
            path = Path(root, name)
            try:
                with path.open(encoding="utf-8") as f:
                    first = f.readline()
            except (UnicodeDecodeError, OSError):
                continue
            if SHEBANG.match(first):
                found.append(path)
    return found


shellcheck = shutil.which("shellcheck", path=f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}")
if not shellcheck:
    sys.exit("shellcheck not found: make setup installs it into the lint venv (shellcheck-py).")

failed = []
with tempfile.TemporaryDirectory() as tmp:
    for path in scripts():
        target = path
        if path.suffix == ".j2":
            target = Path(tmp, path.name[: -len(".j2")])
            # As Ansible renders templates: a block tag takes its newline along.
            environment = jinja2.Environment(undefined=Placeholder, trim_blocks=True)
            environment.filters.update(FILTERS)
            template = environment.from_string(path.read_text(encoding="utf-8"))
            target.write_text(template.render(), encoding="utf-8")
        result = subprocess.run([shellcheck, str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            failed.append(path)
            print(f"== {path}\n{result.stdout}{result.stderr}")
        else:
            print(f"ShellCheck: {path}")

if failed:
    sys.exit(f"ShellCheck found problems in {len(failed)} script(s).")
print("Every shell script passes ShellCheck.")
