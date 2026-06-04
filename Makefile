.PHONY: help install smoke dev seed reset clean fixtures snapshot

help:
	@echo "Authmatic — common commands"
	@echo ""
	@echo "  make install   — install web + agent dependencies"
	@echo "  make smoke     — hello-world each sponsor (preflight)"
	@echo "  make snapshot  — pre-bake the Daytona snapshot"
	@echo "  make seed      — populate Postgres with demo patients"
	@echo "  make dev       — run web (3000) + agent (8000) concurrently"
	@echo "  make reset     — wipe + re-seed Postgres (clean demo run)"
	@echo "  make clean     — remove build artifacts and caches"
	@echo ""

install:
	pnpm install
	pip install -r apps/agent/requirements.txt

smoke:
	bash scripts/smoke.sh

snapshot:
	daytona snapshot create authmatic-v1 \
		--image python:3.12-slim \
		--setup "pip install pdfplumber pydantic icd10-cm"

seed:
	bash scripts/seed.sh

dev:
	pnpm dev

reset:
	bash scripts/reset.sh

clean:
	rm -rf node_modules apps/*/node_modules apps/*/.next packages/*/node_modules .pnpm-store
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
