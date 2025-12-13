PY=python

.PHONY: dev aggregate test lint e2e

dev: aggregate
	$(PY) -m happenstance.cli serve

aggregate:
	$(PY) -m happenstance.cli aggregate

test:
	pytest

lint:
	ruff check .

e2e:
	npm run test:e2e
