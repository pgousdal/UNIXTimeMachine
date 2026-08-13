PYTHON ?= python3
.PHONY: check test catalog validate ansible-syntax syntax provision operator-add qualify
ANSIBLE_CONFIG_FILE := $(CURDIR)/ansible/ansible.cfg
ANSIBLE_INVENTORY := $(CURDIR)/ansible/inventory/localhost.yml
ANSIBLE_PLAYBOOK := $(CURDIR)/ansible/playbooks/site.yml
check: syntax validate test
syntax:
	$(PYTHON) -m compileall -q broker scripts tests
validate:
	$(PYTHON) scripts/validate_manifests.py
test:
	$(PYTHON) -m unittest discover -s tests -v
catalog:
	$(PYTHON) scripts/utm.py catalog
ansible-syntax:
	ANSIBLE_LOCAL_TEMP=/tmp/utm-ansible-local ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook --syntax-check -i $(ANSIBLE_INVENTORY) $(ANSIBLE_PLAYBOOK)
	ANSIBLE_LOCAL_TEMP=/tmp/utm-ansible-local ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook --syntax-check -i $(ANSIBLE_INVENTORY) $(CURDIR)/ansible/playbooks/operator-add.yml
provision:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook -i $(ANSIBLE_INVENTORY) $(ANSIBLE_PLAYBOOK) --ask-become-pass
operator-add:
	@test -n "$(USER)" || (echo "ERROR: USER is required (make operator-add USER=<account>)" >&2; exit 2)
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook -i $(ANSIBLE_INVENTORY) $(CURDIR)/ansible/playbooks/operator-add.yml --ask-become-pass -e "utm_operator_user=$(USER)"
qualify: check
	$(PYTHON) scripts/utm.py doctor
	$(PYTHON) scripts/utm.py media verify unix-v7-pdp11
	$(PYTHON) scripts/utm.py media verify 43bsd-vax
	@echo "HUMAN_REQUIRED: perform both real-host session boots in systems/unix-v7-pdp11/README.md"
	@echo "HUMAN_REQUIRED: perform the M3 evidence gate in systems/43bsd-vax/README.md"
