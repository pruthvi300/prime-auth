# Prime Auth - Makefile
# Simple commands for development

.PHONY: help dev test lint clean

help:
	@echo "Prime Auth - Commands"
	@echo ""
	@echo "  make dev       Start development server"
	@echo "  make test      Run tests"
	@echo "  make test-cov  Run tests with coverage"
	@echo "  make lint      Run linter"
	@echo "  make clean     Remove cache files"

# Development
dev:
	uvicorn app.main:app --reload

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Code Quality
lint:
	ruff check app/

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage
