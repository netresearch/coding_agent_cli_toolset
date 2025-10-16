# ============================================================================
# MAINTENANCE COMMANDS - Build, Package, Deploy, Clean
# ============================================================================
## MAINT

build: clean-build ## Build source and wheel distributions
	$(PYTHON) -m build

build-dist: build ## Alias for build

build-wheel: clean-build ## Build wheel distribution only
	$(PYTHON) -m build --wheel

check-dist: build ## Check distribution for PyPI compatibility
	$(PYTHON) -m twine check dist/*

publish-test: check-dist ## Publish to TestPyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

publish-prod: check-dist ## Publish to production PyPI
	$(PYTHON) -m twine upload dist/*

clean: clean-build clean-test clean-pyc ## Remove all build, test, and Python artifacts

clean-build: ## Remove build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/

clean-test: ## Remove test and coverage artifacts
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf coverage.xml

clean-pyc: ## Remove Python file artifacts
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} + || true

clean-all: clean ## Remove all artifacts including virtual environments
	rm -rf .venv/
	rm -rf venv/
	rm -rf .tox/

scripts-perms: ## Ensure scripts are executable
	@chmod +x scripts/*.sh 2>/dev/null || true
	@chmod +x scripts/lib/*.sh 2>/dev/null || true
