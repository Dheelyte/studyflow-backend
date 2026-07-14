sudo docker compose -f docker-compose-dev.yml up -d
uv run uvicorn app.main:app --reload
