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
    assert report["data_quality"] == {"rejected_rows": 0, "valid_candidate_rows": 2}


def test_cli_logs_rejected_rows_to_optional_log_file(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    output_json = tmp_path / "report.json"
    log_file = tmp_path / "data_quality.log"
    customers_csv.write_text("customer_id,signup_date,country\nC001,2024-01-01,NL\n")
    subscriptions_csv.write_text(
        "customer_id,start_date,end_date,plan,monthly_price\nC999,2024-01-01,,basic,30\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(customers_csv),
            str(subscriptions_csv),
            str(output_json),
            "--log-file",
            str(log_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output_json.read_text())
    assert report["data_quality"] == {"rejected_rows": 1, "valid_candidate_rows": 1}
    assert "unknown customer_id" in log_file.read_text()
    assert "unknown customer_id" not in output_json.read_text()
