PYTHON ?= python3

.PHONY: lint test repro verify

lint:
	$(PYTHON) harness/validate_entries.py

test:
	$(PYTHON) -m unittest discover -s tests -t .

repro:
	@test -n "$(ENTRY)" || { echo "ENTRY is required: make repro ENTRY=<slug> TAG=<tag>" >&2; exit 2; }
	@test -n "$(TAG)" || { echo "TAG is required: make repro ENTRY=<slug> TAG=<tag>" >&2; exit 2; }
	$(PYTHON) harness/run_repro.py --entry "$(ENTRY)" --tag "$(TAG)"

verify:
	@test -n "$(ENTRY)" || { echo "ENTRY is required: make verify ENTRY=<slug>" >&2; exit 2; }
	$(PYTHON) harness/run_repro.py --entry "$(ENTRY)" --all-tags
