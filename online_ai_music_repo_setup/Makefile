.PHONY: help setup setup-macos install test lint api worker infra-up infra-down migrate doctor smoke reset-local

help:
	@echo "AION commands"
	@echo "  make setup-macos"
	@echo "  make setup"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make worker"
	@echo "  make infra-up"
	@echo "  make infra-down"
	@echo "  make migrate"
	@echo "  make doctor"
	@echo "  make smoke"
	@echo "  make reset-local"

setup-macos:
	./scripts/dev/install-python-312-macos.sh

setup:
	./scripts/dev/setup-python-env.sh

install: setup

test:
	@if [ ! -x .venv/bin/pytest ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/pytest

lint:
	@if [ ! -x .venv/bin/ruff ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	.venv/bin/ruff check apps

api:
	@if [ ! -x .venv/bin/uvicorn ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --reload

worker:
	@if [ ! -x .venv/bin/python ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/python apps/worker/app/main.py

infra-up:
	docker compose up -d --build

infra-down:
	docker compose down

migrate:
	@if [ ! -x .venv/bin/alembic ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/alembic upgrade head

doctor:
	./tools/aion/aion doctor
	./scripts/dev/doctor-local.sh

smoke:
	./scripts/dev/docker-smoke-test.sh

reset-local:
	./scripts/ops/docker-reset-local.sh
