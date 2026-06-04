import json
import subprocess
import sys


def test_cli_writes_report(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    output_json = tmp_path / "report.json"
    customers_csv.write_text("customer_id,signup_date,country\nC001,2024-01-01,NL\n")
    subscriptions_csv.write_text(
        "customer_id,start_date,end_date,plan,monthly_price\nC001,2024-01-01,,basic,30\n"
    )

    result = subprocess.run(
        [sys.executable, "main.py", str(customers_csv), str(subscriptions_csv), str(output_json)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output_json.read_text())
    assert report["monthly_mrr"] == [{"month": "2024-01", "mrr": 30.0}]
    assert report["data_quality"]["valid_candidate_rows"]
    assert report["data_quality"]["rejected_rows"] == []
