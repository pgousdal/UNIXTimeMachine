PYTHON ?= python3
.PHONY: check test catalog validate syntax qualify
check: syntax validate test
syntax:
	$(PYTHON) -m compileall -q broker scripts tests
validate:
	$(PYTHON) scripts/validate_manifests.py
test:
	$(PYTHON) -m unittest discover -s tests -v
catalog:
	$(PYTHON) scripts/utm.py catalog
qualify: check
	$(PYTHON) scripts/utm.py doctor
	$(PYTHON) scripts/utm.py media verify unix-v7-pdp11
	@echo "HUMAN_REQUIRED: perform both real-host session boots in systems/unix-v7-pdp11/README.md"
