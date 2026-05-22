env/create:
	python -m venv .venv

env/activate:
	source .venv/bin/activate

install:
	python -m pip install -r requirements.txt
	python -m pip install -e ".[dev]"

test:
	python -m pytest

srikara/test:
	python -m pytest srikara/tests

srikara/demo/basic:
	srikara-basic-demo

srikara/demo/analytic:
	srikara-demo 'hello' --backend analytic

srikara/demo/sf:
	srikara-demo 'hello' --backend sf

srikara/demo/sf-sampled:
	srikara-demo 'hello' \
	--backend sf-sampled \
	--repetitions 10 \
	--random-source sf-bs-qrng \
	--seed 30

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache build dist *.egg-info
