.PHONY: up down logs ps psql shell test build initial-fetch alerts clean

# Default: show help
help:
	@echo "Available commands:"
	@echo "  make up              - Build and start all services"
	@echo "  make down            - Stop all services (data preserved)"
	@echo "  make clean           - Stop all services AND delete data (nuke)"
	@echo "  make logs            - Follow logs from all services"
	@echo "  make logs-scheduler  - Follow scheduler logs only"
	@echo "  make ps              - Show running containers"
	@echo "  make psql            - Open psql shell in postgres container"
	@echo "  make shell           - Open bash shell in dashboard container"
	@echo "  make initial-fetch   - Manually trigger pipeline run"
	@echo "  make alerts          - Manually trigger alert evaluation"
	@echo "  make test            - Run pytest in dashboard container"
	@echo "  make build           - Rebuild images without cache"

up:
	docker-compose up --build -d
	@echo "✓ Services up. Dashboard: http://localhost:8501"

down:
	docker-compose down

clean:
	docker-compose down -v
	@echo "✓ All data wiped."

logs:
	docker-compose logs -f

logs-scheduler:
	docker-compose logs -f scheduler

logs-dashboard:
	docker-compose logs -f dashboard

ps:
	docker-compose ps

psql:
	docker-compose exec postgres psql -U nbptracker -d nbptracker

shell:
	docker-compose exec dashboard bash

initial-fetch:
	docker-compose exec scheduler python -m src.main

alerts:
	docker-compose exec scheduler python -m src.scheduler.check_alerts

test:
	docker-compose exec dashboard pytest tests/ -v

build:
	docker-compose build --no-cache