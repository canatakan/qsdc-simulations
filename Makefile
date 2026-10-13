env/create:
	python -m venv .venv

install:
	python -m pip install -r requirements.txt
	python -m pip install -e ".[dev]"

test:
	python -m pytest

cao/test:
	python -m pytest tests/protocols/cao tests/benchmark/studies/cao

srikara/test:
	python -m pytest tests/protocols/srikara tests/benchmark/studies/srikara

benchmark/test:
	python -m pytest tests/benchmark

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache build dist *.egg-info
