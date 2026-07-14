.PHONY: help install test lint api infra-up infra-down migrate doctor

help:
	@echo "AION commands"
	@echo "  make install"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make infra-up"
	@echo "  make infra-down"
	@echo "  make migrate"
	@echo "  make doctor"

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	PYTHONPATH=apps/api:apps/worker .venv/bin/pytest

lint:
	.venv/bin/ruff check apps

api:
	PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --reload

infra-up:
	docker compose up -d --build

infra-down:
	docker compose down

migrate:
	PYTHONPATH=apps/api .venv/bin/alembic upgrade head

doctor:
	./tools/aion/aion doctor
	python3 --version
	docker --version
	docker compose version
