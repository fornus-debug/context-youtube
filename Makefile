.PHONY: start dev setup test

start: setup
	@bash start.sh

setup:
	@pip install -r requirements.txt -q
	@cd frontend && npm install --silent

test:
	python -m pytest tests/ -v

dev-backend:
	uvicorn api:app --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev
