env/create:
	python -m venv .venv

env/activate:
	source .venv/bin/activate

install:
	python -m pip install -e ".[dev]"

test:
	pytest

demo/basic:
	qsdc-basic-demo

demo/analytic:
	qsdc-demo 'hello' --backend analytic

demo/sf:
	qsdc-demo 'hello' --backend sf

demo/sf-sampled:
	qsdc-demo 'hello' --backend sf-sampled --repetitions 100

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	rm -rf .pytest_cache build dist *.egg-info
