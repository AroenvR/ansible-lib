# TODO

Docs: todo

## Set up as subtree

This library is easily consumed as a git subtree.

Add new subtree:
```bash
git subtree add --prefix=lib/ansible git@github.com:AroenvR/ansible-lib.git main --squash
```

Pull subtree changes:
```bash
git subtree pull --prefix=lib/ansible git@github.com:AroenvR/ansible-lib.git main --squash
```