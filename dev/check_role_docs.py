"""Fail when a role's documented interface and its real defaults disagree.

Ansible applies defaults only from defaults/main.yml; the defaults written in
meta/argument_specs.yml are documentation. This keeps the two identical and
makes sure every role documents every variable it exposes.
"""

import sys
from pathlib import Path

import yaml


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


errors = []
for role in sorted(p for p in Path("roles").iterdir() if p.is_dir()):
    specs = load(role / "meta/argument_specs.yml").get("argument_specs", {})
    if "main" not in specs:
        errors.append(f"{role.name}: meta/argument_specs.yml has no 'main' entry point")
        continue
    options = specs["main"].get("options", {})
    defaults = load(role / "defaults/main.yml")

    for name in sorted(set(defaults) - set(options)):
        errors.append(f"{role.name}: '{name}' is in defaults/main.yml but not documented")
    for name, spec in sorted(options.items()):
        if name in defaults and spec.get("default") != defaults[name]:
            errors.append(f"{role.name}: '{name}' default differs between the two files")
        if name not in defaults and not spec.get("required"):
            errors.append(f"{role.name}: optional '{name}' needs a value in defaults/main.yml")

print("\n".join(errors) or "Role interfaces and defaults match.")
sys.exit(1 if errors else 0)
