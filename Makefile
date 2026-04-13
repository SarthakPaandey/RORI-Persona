.PHONY: setup ingest run-backend run-frontend run-all test deploy clean

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	cp -n .env.example .env 2>/dev/null || true
	@echo "Please fill in your .env file with actual API keys"

ingest:
	cd backend && python -m app.ingestion.run_ingestion

run-backend:
	cd backend && python3 -m uvicorn app.main:app --reload --port 8000

run-frontend:
	cd frontend && npm run dev

run-all:
	docker-compose up --build

test:
	cd backend && python3 -m pytest tests/ -v
	cd frontend && npm test


deploy:
	./scripts/deploy.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .next -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +
