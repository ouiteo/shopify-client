CYAN ?= \033[0;36m
COFF ?= \033[0m

.PHONY: deps lint check test help test_app
.EXPORT_ALL_VARIABLES:

.DEFAULT: help
help: ## Display help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-30s$(COFF) %s\n", $$1, $$2}'

deps: ## nstall dependencies
	@printf "$(CYAN)Updating python deps$(COFF)\n"
	pip3 install -U pip poetry
	@poetry install

lint: ## Lint the code
	@printf "$(CYAN)Auto-formatting with black$(COFF)\n"
	poetry run ruff format shopify_client tests
	poetry run ruff check shopify_client tests --fix

check: ## Check code quality
	@printf "$(CYAN)Running static code analysis$(COFF)\n"
	poetry run ruff format --check shopify_client tests
	poetry run ruff check shopify_client tests
	poetry run mypy shopify_client tests --ignore-missing-imports

test:  ## run the test suite, and produce coverage results
	@printf "$(CYAN)Running tests$(COFF)\n"
	@mkdir -p .reports
	@poetry run pytest tests --junitxml=.reports/coverage.xml --cov-report=html:.reports/htmlcov --cov shopify_client --cov-fail-under=33
