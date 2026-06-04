.PHONY: test run

test:
	uv run pytest

run:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json
