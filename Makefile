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
# at <dir>/ansible_collections/acme/infra. Test-only collections live in the venv.
ifeq ($(filter %/ansible_collections/acme/infra,$(CURDIR)),)
$(error Clone this repository into <dir>/ansible_collections/acme/infra, see CONTRIBUTING.md)
endif
export ANSIBLE_COLLECTIONS_PATH := $(CURDIR)/$(VENV)/collections

.PHONY: help setup images lint test native dist build check-tag clean

help: ## List the targets
	@grep -E '^[a-z0-9%-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-18s %s\n", $$1, $$2}'

setup: $(VENV)/lint $(addprefix $(VENV)/,$(TOOLCHAINS)) $(VENV)/collections ## Create all venvs, install test-only collections

# Each venv is created once and rebuilt when its pinned requirements change.
$(VENV)/lint: dev/requirements-lint.txt
	$(PYTHON_LINT) -m venv $@
	$@/bin/pip install -r $<
	touch $@

$(addprefix $(VENV)/,$(TOOLCHAINS)): $(VENV)/%: dev/requirements-%.txt
	$(PYTHON_COMPAT) -m venv $@
	$@/bin/pip install -r $<
	touch $@

$(VENV)/collections: dev/collections.yml | $(VENV)/rhel9
	$(VENV)/rhel9/bin/ansible-galaxy collection install -r $< -p $@
	touch $@

images: $(addprefix image-,$(PLATFORMS)) ## Build all Podman test containers

image-%: ## Build one test container, e.g. make image-rhel9
	podman build -t localhost/acme-test/$* dev/images/$*

lint: $(VENV)/lint ## Lint all content and check every role's documented interface
	$(VENV)/lint/bin/ansible-lint
	$(VENV)/lint/bin/python dev/check_role_docs.py

test: $(addprefix test-,$(TOOLCHAINS)) ## Test every role with both toolchains

test-%: $(VENV)/% $(VENV)/collections ## Test every role with one toolchain, e.g. make test-rhel9 PLATFORM=ubuntu2204
	for r in $(ROLES); do \
	  (cd roles/$$r && PATH="$(CURDIR)/$(VENV)/$*/bin:$$PATH" \
	    molecule test --all $(if $(PLATFORM),--platform-name $(PLATFORM))) || exit 1; \
	done

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
