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
	rm -rf **/__pycache__ .pytest_cache build dist *.egg-info
