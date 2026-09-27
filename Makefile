.PHONY: help build up down logs test migrate shell clean

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start services"
	@echo "  make down     - Stop services"
	@echo "  make logs     - View logs"
	@echo "  make test     - Run tests"
	@echo "  make migrate  - Run database migrations"
	@echo "  make shell    - Open shell in API container"
	@echo "  make clean    - Clean up containers and volumes"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Services started. API available at http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose exec api pytest -v

test-coverage:
	docker-compose exec api pytest --cov=src --cov-report=term-missing

migrate:
	docker-compose exec api alembic upgrade head

shell:
	docker-compose exec api /bin/bash

clean:
	docker-compose down -v
	rm -rf raw_files/*
