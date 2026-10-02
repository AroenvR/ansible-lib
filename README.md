# Bash Library

A modular bash library providing useful functions.  
Adheres to [GitHub's shell styling guide](https://google.github.io/styleguide/shellguide.html) as much as possible.

## Overview

This library aggregates reusable shell functions organized into focused modules:

```plaintext
<bash_lib_root>/
├── __tests__/          # Helpers for this library's testing suites.
│   └── bootstrap.sh/   # Bootstrapper for test suites.
│
├── utils/              # Utility functions provided by this library.
│   ├── environment/    # Environment variable utility functions.
│   ├── file_management/# File management utility functions.
│   ├── logging/        # Logging utility functions.
│   └── podman/         # Utilities for the podman library.
│
└── source.sh           # This libary's entry point to source.
```

## Usage

Source this library's entry point in your own scripts.  
I took the liberty of making a little template:

```bash
#!/bin/bash
#
# This script does ...

#######################################
#            Script setup             #
#######################################

# Useful globals
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="${LOG_PREFIX:-script}"

# !!! Edit path to bash library !!!
BASH_LIB_SRC="$SCRIPT_DIR/../../lib/bash/source.sh";
if [[ ! -f "$BASH_LIB_SRC" ]]; then
  echo "Failed to find bash library at: $BASH_LIB_SRC"
  exit 1
fi

# Source the library.
source "$BASH_LIB_SRC"
source_default_environment "$SCRIPT_DIR/.env.example"

# Log setup success
log "Executing the $LOG_PREFIX script in directory: $SCRIPT_DIR"

#######################################
#           Setup complete!           #
#######################################
```

### Verbose-level Logging

Enable verbose logging by setting the `VERBOSE` environment variable (`.env` supported):

```bash
VERBOSE=1 /path/to/lib/consumer/foo.sh
```

## Set up as subtree

This library is easily consumed as a git subtree.

Add new subtree:
```bash
git subtree add --prefix=lib/bash git@github.com:AroenvR/bash-lib.git main --squash
```

Pull subtree changes:
```bash
git subtree pull --prefix=lib/bash git@github.com:AroenvR/bash-lib.git main --squash
```
