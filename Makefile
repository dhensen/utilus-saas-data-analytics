.PHONY: test run run-10k visualize-mrr visualize-churn visualize-retention

test:
	uv run pytest

run:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json

run-10k:
	uv run python generate_big_data.py 10000
	uv run python main.py data/customers_big.csv data/subscriptions_big.csv output.json --log-file data_quality.log

visualize-mrr:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json --log-file data_quality.log
	uv run scripts/visualize_metric.py output.json mrr visualizations/monthly_mrr.png

visualize-churn:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json --log-file data_quality.log
	uv run scripts/visualize_metric.py output.json churn visualizations/monthly_churned_customers.png

visualize-retention:
	uv run python main.py data/customers.csv data/subscriptions.csv output.json --log-file data_quality.log
	uv run scripts/visualize_metric.py output.json retention visualizations/signup_cohort_retention.png
