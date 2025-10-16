# ============================================================================
# DEVELOPMENT COMMANDS - Testing, Linting, Formatting
# ============================================================================
## DEV

test: ## Run all tests
	$(PYTHON) -m pytest

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/ -k "not integration"

test-integration: ## Run integration tests only
	$(PYTHON) -m pytest tests/integration/

test-coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest --cov=cli_audit --cov-report=term --cov-report=html

test-coverage-xml: ## Run tests with XML coverage (for CI)
	$(PYTHON) -m pytest --cov=cli_audit --cov-report=xml --cov-report=term

test-watch: ## Run tests in watch mode (requires pytest-watch)
	$(PYTHON) -m pytest_watch

test-failed: ## Re-run only failed tests
	$(PYTHON) -m pytest --lf

test-verbose: ## Run tests with verbose output
	$(PYTHON) -m pytest -vv -s

test-parallel: ## Run tests in parallel (requires pytest-xdist)
	$(PYTHON) -m pytest -n auto

lint: lint-code lint-types lint-security ## Run all linting checks

lint-code: ## Run flake8 code linting
	@echo "→ Running flake8..."
	@$(PYTHON) -m flake8 cli_audit tests || echo "flake8 checks failed"

lint-types: ## Run mypy type checking
	@echo "→ Running mypy..."
	@$(PYTHON) -m mypy cli_audit || echo "mypy checks failed"

lint-security: ## Run bandit security checks
	@echo "→ Running bandit..."
	@$(PYTHON) -m bandit -r cli_audit -ll || echo "bandit checks failed"

format: ## Format code with black and isort
	@echo "→ Running black..."
	@$(PYTHON) -m black cli_audit tests
	@echo "→ Running isort..."
	@$(PYTHON) -m isort cli_audit tests

format-check: ## Check code formatting without changes
	@echo "→ Checking black..."
	@$(PYTHON) -m black --check cli_audit tests
	@echo "→ Checking isort..."
	@$(PYTHON) -m isort --check-only cli_audit tests

install: ## Install package in editable mode
	$(PYTHON) -m pip install -e .

install-dev: ## Install package with development dependencies
	$(PYTHON) -m pip install -e ".[dev]"
