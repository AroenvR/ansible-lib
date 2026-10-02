# Developer and CI entry points for the acme.infra collection. Run `make help`.
# The CI pipelines (.github/, .gitlab-ci.yml) only call these targets, so a local
# run and a pipeline do exactly the same thing. None of this is needed to *use*
# the collection; see README.md for that.

# Toolchains need Python 3.9 or 3.10: the default python3 on RHEL 9 and Ubuntu 22.04.
PYTHON_COMPAT ?= python3
# ansible-lint needs Python 3.10+. On Ubuntu 22.04, python3 works too.
PYTHON_LINT   ?= python3.12
TOOLCHAINS    := ubuntu2204 rhel9
PLATFORMS     := ubuntu2204 rhel9
ROLES         ?= $(notdir $(wildcard roles/*))
# Test on one OS container only, e.g. PLATFORM=rhel9. Empty means all.
PLATFORM      ?=
VENV          := .venv
VERSION       := $(shell sed -n 's/^version: *//p' galaxy.yml)
TARBALL       := dist/acme-infra-$(VERSION).tar.gz

# Ansible loads acme.infra straight from this checkout, which is why it must live
# at <dir>/ansible_collections/acme/infra.
ifeq ($(filter %/ansible_collections/acme/infra,$(CURDIR)),)
$(error Clone this repository into <dir>/ansible_collections/acme/infra, see CONTRIBUTING.md)
endif

# Runs Molecule with toolchain $1 for every role that has scenario $2.
define molecule
	for r in $(ROLES); do \
	  [ -d roles/$$r/molecule/$2 ] || continue; \
	  (cd roles/$$r && PATH="$(CURDIR)/$(VENV)/$1/bin:$$PATH" \
	    ANSIBLE_COLLECTIONS_PATH="$(CURDIR)/$(VENV)/collections" \
	    molecule test --scenario-name $2 $3) || exit 1; \
	done
endef

.PHONY: help setup images lint test native dist build check-tag clean

help: ## List the targets
	@grep -E '^[a-z0-9%-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-18s %s\n", $$1, $$2}'

setup: $(VENV)/lint $(addprefix $(VENV)/,$(TOOLCHAINS)) $(VENV)/collections ## Create all venvs, install test-only collections

# Each venv is created once and rebuilt when its pinned requirements change.
# --upgrade-deps: the pip bundled with Python 3.9/3.10 installs ansible-core 2.12
# (published as source only) the legacy way, which leaves its commands with a
# broken '#!python' line. A current pip builds it properly.
$(VENV)/lint: dev/requirements-lint.txt
	$(PYTHON_LINT) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

$(addprefix $(VENV)/,$(TOOLCHAINS)): $(VENV)/%: dev/requirements-%.txt
	$(PYTHON_COMPAT) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

# Installed with the rhel9 toolchain: its ansible-galaxy (2.14) is proven against
# today's Galaxy server; 2.12's has not been tested there.
$(VENV)/collections: dev/collections.yml | $(VENV)/rhel9
	$(VENV)/rhel9/bin/ansible-galaxy collection install -r $< -p $@
	touch $@

images: $(addprefix image-,$(PLATFORMS)) ## Build all Podman test containers

image-%: ## Build one test container, e.g. make image-rhel9
	podman build -t localhost/acme-test/$* dev/images/$*

# ansible-lint resolves acme.infra (used by playbooks/) from this checkout.
lint: $(VENV)/lint ## Lint all content and check every role's documented interface
	ANSIBLE_COLLECTIONS_PATH="$(abspath $(CURDIR)/../../..)" $(VENV)/lint/bin/ansible-lint
	$(VENV)/lint/bin/python dev/check_role_docs.py

test: $(addprefix test-,$(TOOLCHAINS)) $(addprefix test-local-,$(TOOLCHAINS)) ## Run all Molecule tests with both toolchains

test-%: $(VENV)/% $(VENV)/collections ## Test the server roles in the OS containers, e.g. make test-rhel9 PLATFORM=ubuntu2204
	$(call molecule,$*,default,$(if $(PLATFORM),--platform-name $(PLATFORM)))

test-local-%: $(VENV)/% $(VENV)/collections ## Test the roles that run on the build machine itself, e.g. make test-local-rhel9
	$(call molecule,$*,local,)

native: native-ubuntu2204 ## Run every role with the ansible-core package the OS itself ships

native-%: dist image-% image-%-native ## Same, for one OS, e.g. make native-ubuntu2204
	dev/native-test.sh localhost/acme-test/$*-native $(TARBALL) $(ROLES)

dist: $(VENV)/lint ## Build the release tarball (runtime files only) into dist/
	$(VENV)/lint/bin/ansible-galaxy collection build --output-path dist --force

build: lint test native ## Everything CI runs before a release

check-tag: ## Fail unless TAG (e.g. v1.2.0) matches the version in galaxy.yml
	@test "$(TAG)" = "v$(VERSION)" || { echo "Tag '$(TAG)' does not match galaxy.yml version $(VERSION)"; exit 1; }

clean: ## Remove venvs and build output
	rm -rf $(VENV) dist
