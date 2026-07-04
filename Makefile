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
	python -m pytest tests/protocols/srikara

srikara/demo/basic:
	python demos/srikara/basic.py

srikara/demo/analytic:
	python demos/srikara/message.py 'hello' --backend analytic

srikara/demo/sf:
	python demos/srikara/message.py 'hello' --backend sf

srikara/demo/sf-sampled:
	python demos/srikara/message.py 'hello' \
	--backend sf-sampled \
	--random-source sf-bs-qrng \
	--seed 30

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache build dist *.egg-info
