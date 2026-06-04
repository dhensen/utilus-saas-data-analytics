.PHONY: test run run-10k

test:
	uv run pytest

run:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json

run-10k:
	uv run python generate_big_data.py 10000
	uv run python main.py data/customers_big.csv data/subscriptions_big.csv output.json --log-file data_quality.log
