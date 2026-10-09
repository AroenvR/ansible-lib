# Developer and CI entry points for the aslib.infra collection. Run `make help`.
# The CI pipelines (.github/, .gitlab-ci.yml) only call these targets, so a local
# run and a pipeline do exactly the same thing. None of this is needed to *use*
# the collection; see README.md for that.

# Every role is tested with the ansible-core versions the oldest supported OSes
# ship: 2.14 (RHEL 9.6) and 2.16 (Ubuntu 24.04). Each gets a venv, pinned in
# dev/requirements-ansible-<version>.txt, on the Python its OS's package uses.
ANSIBLE_VERSIONS := 2.14 2.16
PYTHON_2.14   ?= python3.11
PYTHON_2.16   ?= python3.12
# ansible-lint needs Python 3.10+.
PYTHON_LINT   ?= python3.12
# Test servers: containers that mimic default installs, see dev/images/.
SERVERS       := ubuntu2404 rhel9
ROLES         ?= $(notdir $(wildcard roles/*))
# Roles that support Ubuntu. Only these run in the native test.
UBUNTU_ROLES  := sudoers node_image node_setup claude_code
VENV          := .venv
VERSION       := $(shell sed -n 's/^version: *//p' galaxy.yml)
# Python leaves no __pycache__ in the checkout when Ansible loads its plugins.
export PYTHONDONTWRITEBYTECODE := 1
TARBALL       := dist/aslib-infra-$(VERSION).tar.gz

# Ansible loads aslib.infra straight from this checkout, which is why it must live
# at <dir>/ansible_collections/aslib/infra.
ifeq ($(filter %/ansible_collections/aslib/infra,$(CURDIR)),)
$(error Clone this repository into <dir>/ansible_collections/aslib/infra, see CONTRIBUTING.md)
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

.PHONY: help setup images lint test test-native dist dist-release version build clean

help: ## List the targets
	@grep -E '^[a-z0-9%.-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-26s %s\n", $$1, $$2}'

setup: $(VENV)/lint $(addprefix $(VENV)/ansible-,$(ANSIBLE_VERSIONS)) $(VENV)/collections ## Create all venvs, install test-only collections

# Each venv is created once and rebuilt when its pinned requirements change,
# with a current pip (--upgrade-deps) rather than the one Python bundles.
$(VENV)/lint: dev/requirements-lint.txt
	$(PYTHON_LINT) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

$(addprefix $(VENV)/ansible-,$(ANSIBLE_VERSIONS)): $(VENV)/ansible-%: dev/requirements-ansible-%.txt
	$(PYTHON_$*) -m venv --upgrade-deps $@
	$@/bin/pip install -r $<
	touch $@

# Installed with the oldest ansible-core's ansible-galaxy, proven against today's Galaxy server.
$(VENV)/collections: dev/collections.yml | $(VENV)/ansible-2.14
	$(VENV)/ansible-2.14/bin/ansible-galaxy collection install -r $< -p $@
	touch $@

images: $(addprefix image-,$(SERVERS)) ## Build the test server containers

image-%: ## Build one test container, e.g. make image-rhel9
	podman build -t localhost/aslib-test/$* dev/images/$*

# ansible-lint resolves aslib.infra (used by playbooks/) from this checkout. It
# skips plugins: ansible-doc loads each one (plugins/<type>/<name>.py) and its
# documentation instead.
lint: $(VENV)/lint ## Lint all content and check every role's documented interface
	ANSIBLE_COLLECTIONS_PATH="$(abspath $(CURDIR)/../../..)" $(VENV)/lint/bin/ansible-lint
	$(VENV)/lint/bin/python dev/check_role_docs.py
	$(VENV)/lint/bin/python dev/check_conditions.py
	$(VENV)/lint/bin/python dev/check_shell.py
	@for plugin in plugins/*/*.py; do \
	  type=$$(basename $$(dirname $$plugin)); name=$$(basename $$plugin .py); \
	  echo "ansible-doc -t $$type aslib.infra.$$name"; \
	  ANSIBLE_COLLECTIONS_PATH="$(abspath $(CURDIR)/../../..)" $(VENV)/lint/bin/ansible-doc -t $$type aslib.infra.$$name >/dev/null || exit 1; \
	done

test: $(foreach v,$(ANSIBLE_VERSIONS),test-servers-$(v) test-build-machine-$(v) test-dist-$(v)) ## Run every test with every ansible-core version

test-servers-%: $(VENV)/ansible-% $(VENV)/collections ## Test the server roles on the test servers, e.g. make test-servers-2.14 ROLES=sudoers
	$(call molecule,$*,server)

test-build-machine-%: $(VENV)/ansible-% $(VENV)/collections ## Test the build-machine roles on this machine, e.g. make test-build-machine-2.14
	$(call molecule,$*,build_machine)

# build.yml on copies of this checkout: in a git repository, and outside one.
test-dist-%: $(VENV)/ansible-% ## Test build.yml, in a git checkout and without git, e.g. make test-dist-2.14
	PATH="$(CURDIR)/$(VENV)/ansible-$*/bin:$$PATH" ansible-playbook dev/test-build.yml

test-native: dist image-ubuntu2404 image-ubuntu2404-native ## Test with the ansible-core and Podman packages Ubuntu 24.04 itself ships
	dev/native-test.sh localhost/aslib-test/ubuntu2404-native $(TARBALL) $(filter $(UBUNTU_ROLES),$(ROLES))

# Both run build.yml, which also works without make (see its header). CI passes
# BRANCH, as its checkout may not be on a branch.
dist: $(VENV)/lint ## Build a tarball to try out: dist/aslib-infra.<branch>.<commit>.<UTC time>.tgz
	PATH="$(CURDIR)/$(VENV)/lint/bin:$$PATH" ansible-playbook build.yml $(if $(BRANCH),-e branch=$(BRANCH))

# Writes the version into galaxy.yml first, so only CI should run this.
dist-release: $(VENV)/lint ## Build a release, as CI does from main: dist/aslib-infra-<next version>.tar.gz
	PATH="$(CURDIR)/$(VENV)/lint/bin:$$PATH" ansible-playbook build.yml -e release=true

version: ## Print the collection's version (from galaxy.yml)
	@echo $(VERSION)

build: lint test test-native ## Everything CI runs before a release

clean: ## Remove venvs and build output
	rm -rf $(VENV) dist
