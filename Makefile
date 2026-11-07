.PHONY: help install dev migrate test test-cov lint clean

help:
	@echo "make install   Install runtime + dev dependencies"
	@echo "make dev       Run the API with auto-reload"
	@echo "make migrate   Apply database migrations"
	@echo "make test      Run tests"
	@echo "make test-cov  Run tests with an HTML coverage report"
	@echo "make lint      Run ruff"
	@echo "make clean     Remove caches"

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

test:
	pytest

test-cov:
	pytest --cov=app --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

lint:
	ruff check app tests alembic

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
