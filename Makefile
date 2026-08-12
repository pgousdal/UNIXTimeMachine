PYTHON ?= python3
.PHONY: check test catalog validate ansible-syntax syntax provision qualify
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
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook --syntax-check -i $(ANSIBLE_INVENTORY) $(ANSIBLE_PLAYBOOK)
provision:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE) ansible-playbook -i $(ANSIBLE_INVENTORY) $(ANSIBLE_PLAYBOOK) --ask-become-pass
qualify: check
	$(PYTHON) scripts/utm.py doctor
	$(PYTHON) scripts/utm.py media verify unix-v7-pdp11
	@echo "HUMAN_REQUIRED: perform both real-host session boots in systems/unix-v7-pdp11/README.md"
