# Developer and CI entry points for the acme.infra collection. Run `make help`.
# The CI pipelines (.github/, .gitlab-ci.yml) only call these targets, so a local
# run and a pipeline do exactly the same thing. None of this is needed to *use*
# the collection; see README.md for that.

# Every role is tested with the ansible-core versions the supported OSes ship:
# 2.12 (Ubuntu 22.04) and 2.14 (RHEL 9.6). Each gets a venv, pinned in
# dev/requirements-ansible-<version>.txt.
ANSIBLE_VERSIONS := 2.12 2.14
# Those venvs need Python 3.9 or 3.10: the default python3 on RHEL 9 and Ubuntu 22.04.
PYTHON_COMPAT ?= python3
# ansible-lint needs Python 3.10+. On Ubuntu 22.04, python3 works too.
PYTHON_LINT   ?= python3.12
# Test servers: containers that mimic default installs, see dev/images/.
SERVERS       := ubuntu2204 rhel9
ROLES         ?= $(notdir $(wildcard roles/*))
# Roles that support Ubuntu 22.04. Only these run in the native test.
UBUNTU_ROLES  := sudoers node_image node_setup
VENV          := .venv
VERSION       := $(shell sed -n 's/^version: *//p' galaxy.yml)
TARBALL       := dist/acme-infra-$(VERSION).tar.gz
BRANCH        ?= $(shell git rev-parse --abbrev-ref HEAD)

# Ansible loads acme.infra straight from this checkout, which is why it must live
# at <dir>/ansible_collections/acme/infra.
ifeq ($(filter %/ansible_collections/acme/infra,$(CURDIR)),)
$(error Clone this repository into <dir>/ansible_collections/acme/infra, see CONTRIBUTING.md)
endif

# Runs Molecule scenario $2 with ansible-core $1 for every role that has it. The
# banner tells which role's tests the log lines below it belong to.
define molecule
	@for r in $(ROLES); do \
	  [ -d roles/$$r/molecule/$2 ] || continue; \
	  printf '\n##### %s: %s tests, ansible-core %s #####\n\n' $$r $2 $1; \
	  (cd roles/$$r && PATH="$(CURDIR)/$(VENV)/ansible-$1/bin:$$PATH" \
	    ANSIBLE_COLLECTIONS_PATH="$(CURDIR)/$(VENV)/collections" \
	    molecule test --scenario-name $2) || exit 1; \
	done
endef

.PHONY: help setup images lint test test-native dist dist-branch dist-release version build clean

help: ## List the targets
	@grep -E '^[a-z0-9%.-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-26s %s\n", $$1, $$2}'

setup: $(VENV)/lint $(addprefix $(VENV)/ansible-,$(ANSIBLE_VERSIONS)) $(VENV)/collections ## Create all venvs, install test-only collections

# Each venv is created once and rebuilt when its pinned requirements change.
# --upgrade-deps: the pip bundled with Python 3.9/3.10 installs ansible-core 2.12
# (published as source only) the legacy way, which leaves its commands with a
# broken '#!python' line. A current pip builds it properly.
$(VENV)/lint: dev/requirements-lint.txt
	$(PYTHON_LINT) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

$(addprefix $(VENV)/ansible-,$(ANSIBLE_VERSIONS)): $(VENV)/ansible-%: dev/requirements-ansible-%.txt
	$(PYTHON_COMPAT) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

# Installed with ansible-core 2.14: its ansible-galaxy is proven against today's
# Galaxy server; 2.12's has not been tested there.
$(VENV)/collections: dev/collections.yml | $(VENV)/ansible-2.14
	$(VENV)/ansible-2.14/bin/ansible-galaxy collection install -r $< -p $@
	touch $@

images: $(addprefix image-,$(SERVERS)) ## Build the test server containers

image-%: ## Build one test container, e.g. make image-rhel9
	podman build -t localhost/acme-test/$* dev/images/$*

# ansible-lint resolves acme.infra (used by playbooks/) from this checkout.
lint: $(VENV)/lint ## Lint all content and check every role's documented interface
	ANSIBLE_COLLECTIONS_PATH="$(abspath $(CURDIR)/../../..)" $(VENV)/lint/bin/ansible-lint
	$(VENV)/lint/bin/python dev/check_role_docs.py

test: $(foreach v,$(ANSIBLE_VERSIONS),test-servers-$(v) test-build-machine-$(v)) ## Run every Molecule test with every ansible-core version

test-servers-%: $(VENV)/ansible-% $(VENV)/collections ## Test the server roles on the test servers, e.g. make test-servers-2.12 ROLES=sudoers
	$(call molecule,$*,server)

test-build-machine-%: $(VENV)/ansible-% $(VENV)/collections ## Test the build-machine roles on this machine, e.g. make test-build-machine-2.14
	$(call molecule,$*,build_machine)

test-native: dist image-ubuntu2204 image-ubuntu2204-native ## Test with the ansible-core and Podman packages Ubuntu 22.04 itself ships
	dev/native-test.sh localhost/acme-test/ubuntu2204-native $(TARBALL) $(filter $(UBUNTU_ROLES),$(ROLES))

dist: $(VENV)/lint ## Build the release tarball (runtime files only) into dist/
	$(VENV)/lint/bin/ansible-galaxy collection build --output-path dist --force

# The two release builds CI makes once every test has passed (see CONTRIBUTING.md).
dist-branch: dist ## Branch build: dist/acme-infra.<branch>.<commit>.<UTC time>.tgz
	cp $(TARBALL) dist/acme-infra.$(subst /,.,$(BRANCH)).$(shell git rev-parse HEAD).$(shell date -u +%Y%m%d%H%M).tgz

# Sets the version in galaxy.yml first, so only CI should run this.
dist-release: ## Release build from main: next version (dev/ci/next-version.sh) into dist/
	sed -i "s/^version: .*/version: $$(sh dev/ci/next-version.sh)/" galaxy.yml
	$(MAKE) dist

version: ## Print the collection's version (from galaxy.yml)
	@echo $(VERSION)

build: lint test test-native ## Everything CI runs before a release

clean: ## Remove venvs and build output
	rm -rf $(VENV) dist
