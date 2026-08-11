PYTHON ?= python3
.PHONY: check test catalog validate syntax
check: syntax validate test
syntax:
	$(PYTHON) -m compileall -q broker scripts tests
validate:
	$(PYTHON) scripts/validate_manifests.py
test:
	$(PYTHON) -m unittest discover -s tests -v
catalog:
	$(PYTHON) scripts/catalog.py
