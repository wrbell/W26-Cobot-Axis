.PHONY: lint fmt test typecheck spellcheck yamllint check install clean ci-local

lint:
	ruff check src/bridge/

fmt:
	ruff check --fix src/bridge/

test:
	python -m pytest src/bridge/tests/ -v --cov=src/bridge --cov-report=term-missing

typecheck:
	mypy src/bridge/ --exclude tests/

spellcheck:
	codespell --skip="vendor,*.json,.git,.coverage,*.xml" -L "ot"

yamllint:
	yamllint .github/workflows/

check: lint test typecheck yamllint spellcheck

install:
	pip install -r requirements.txt
	pre-commit install

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .coverage htmlcov .pytest_cache coverage.xml
	find . -name '*.pyc' -delete 2>/dev/null || true

ci-local:
	act -j lint-and-test --matrix python-version:3.11
