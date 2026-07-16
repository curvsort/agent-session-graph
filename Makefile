.PHONY: test test-v install

test:
	PYTHONPATH=src:$$PYTHONPATH pytest

test-v:
	PYTHONPATH=src:$$PYTHONPATH pytest -v

install:
	pip install -e .
