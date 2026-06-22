.PHONY: install dev test lint format typecheck clean

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8000} --reload

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app tests

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
