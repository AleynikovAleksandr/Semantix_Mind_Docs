.PHONY: help up down build restart test logs shell flower docs

help:
	@echo "Команды:"
	@echo "  make build        — собрать Docker образы"
	@echo "  make up           — запустить все сервисы"
	@echo "  make down         — остановить"
	@echo "  make restart      — перезапустить backend + worker"
	@echo "  make test         — запустить тесты"
	@echo "  make logs         — логи backend + worker"
	@echo "  make shell        — bash внутри backend контейнера"
	@echo "  make flower       — открыть Flower (Celery monitor)"
	@echo "  make docs         — открыть Swagger UI"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart backend worker



test:
	docker compose exec backend pytest tests/ -v

logs:
	docker compose logs -f backend worker

shell:
	docker compose exec backend bash

flower:
	@echo "Flower: http://localhost:5555"

docs:
	@echo "Swagger: http://localhost:8000/docs"
	@echo "ReDoc:   http://localhost:8000/redoc"
