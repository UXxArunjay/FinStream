"""
FinStream Financial Reconciliation Engine
------------------------------------------
Reconciles internal transaction logs (fetched from BigQuery or dry-run dataset)
against third-party external financial settlement files (CSV).

Identifies:
1. MATCHED: Transactions matching in both systems with identical amounts.
2. VARIANCE: Transactions present in both systems but with differing amounts.
3. UNMATCHED_INTERNAL: Transactions in BigQuery missing from settlement file.
4. UNMATCHED_SETTLEMENT: Settlement entries missing from BigQuery records.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Tuple, Dict, Any

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] reconciliation - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("reconciler")


def fetch_internal_transactions_bq(project_id: str, dataset: str, table: str, target_date: str) -> pd.DataFrame:
    """
    Queries BigQuery for internal transactions logged on a given date.
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project_id)
        
        query = f"""
            SELECT 
                transaction_id,
                account_id,
                amount AS internal_amount,
                currency AS internal_currency,
                timestamp AS internal_timestamp,
                status AS internal_status,
                merchant_id
            FROM `{project_id}.{dataset}.{table}`
            WHERE DATE(timestamp) = '{target_date}'
        """
        logger.info(f"Querying BigQuery table {project_id}.{dataset}.{table} for date {target_date}...")
        df = client.query(query).to_dataframe()
        return df
    except Exception as err:
        logger.warning(f"BigQuery fetch failed ({err}). Falling back to dry-run synthetic records.")
        return generate_mock_internal_df(target_date)


def generate_mock_internal_df(target_date: str) -> pd.DataFrame:
    """
    Generates synthetic internal BigQuery data for offline testing & dry runs.
    """
    data = [
        {"transaction_id": "txn-10001", "account_id": "ACC-101", "internal_amount": 150.50, "internal_currency": "USD", "internal_timestamp": f"{target_date} 10:00:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-01"},
        {"transaction_id": "txn-10002", "account_id": "ACC-102", "internal_amount": 499.00, "internal_currency": "USD", "internal_timestamp": f"{target_date} 10:15:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-02"},
        {"transaction_id": "txn-10003", "account_id": "ACC-103", "internal_amount": 89.99,  "internal_currency": "USD", "internal_timestamp": f"{target_date} 10:30:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-03"},
        {"transaction_id": "txn-10004", "account_id": "ACC-104", "internal_amount": 1250.00, "internal_currency": "USD", "internal_timestamp": f"{target_date} 11:00:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-04"}, # Variance ($1250 vs $1200)
        {"transaction_id": "txn-10005", "account_id": "ACC-105", "internal_amount": 75.25,  "internal_currency": "USD", "internal_timestamp": f"{target_date} 11:30:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-05"},
        {"transaction_id": "txn-10006", "account_id": "ACC-106", "internal_amount": 310.00, "internal_currency": "USD", "internal_timestamp": f"{target_date} 12:00:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-06"},
        {"transaction_id": "txn-10007", "account_id": "ACC-107", "internal_amount": 95.00,  "internal_currency": "USD", "internal_timestamp": f"{target_date} 12:15:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-07"},
        {"transaction_id": "txn-10008", "account_id": "ACC-108", "internal_amount": 45.50,  "internal_currency": "USD", "internal_timestamp": f"{target_date} 12:30:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-08"},
        {"transaction_id": "txn-10011", "account_id": "ACC-111", "internal_amount": 620.00, "internal_currency": "USD", "internal_timestamp": f"{target_date} 13:00:00", "internal_status": "COMPLETED", "merchant_id": "MERCH-11"}, # Unmatched Internal (Missing in Settlement)
    ]
    return pd.DataFrame(data)


def load_settlement_csv(file_path: str) -> pd.DataFrame:
    """
    Loads external settlement file CSV into a pandas DataFrame.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Settlement file not found: {file_path}")

    logger.info(f"Loading external settlement file: {file_path}")
    df = pd.read_csv(file_path)
    
    # Ensure numeric settlement_amount
    df["settlement_amount"] = pd.to_numeric(df["settlement_amount"], errors="coerce")
    return df


def perform_reconciliation(internal_df: pd.DataFrame, settlement_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Performs full outer join on transaction_id and computes reconciliation breakdown metrics.
    """
    # Outer join to capture all records from both sources
    merged = pd.merge(
        internal_df,
        settlement_df,
        on="transaction_id",
        how="outer"
    )

    # Classify each row
    def classify_row(row):
        has_internal = pd.notna(row["internal_amount"])
        has_settlement = pd.notna(row["settlement_amount"])

        if has_internal and has_settlement:
            diff = abs(row["internal_amount"] - row["settlement_amount"])
            if diff < 0.001:
                return "MATCHED"
            else:
                return "VARIANCE"
        elif has_internal and not has_settlement:
            return "UNMATCHED_INTERNAL"
        else:
            return "UNMATCHED_SETTLEMENT"

    merged["reconciliation_status"] = merged.apply(classify_row, axis=1)
    merged["amount_variance"] = merged.apply(
        lambda r: (r["internal_amount"] - r["settlement_amount"]) if pd.notna(r["internal_amount"]) and pd.notna(r["settlement_amount"]) else 0.0,
        axis=1
    )

    # Summary metrics calculation
    matched_df = merged[merged["reconciliation_status"] == "MATCHED"]
    variance_df = merged[merged["reconciliation_status"] == "VARIANCE"]
    unmatched_int_df = merged[merged["reconciliation_status"] == "UNMATCHED_INTERNAL"]
    unmatched_set_df = merged[merged["reconciliation_status"] == "UNMATCHED_SETTLEMENT"]

    summary = {
        "total_internal_records": len(internal_df),
        "total_settlement_records": len(settlement_df),
        "matched_count": len(matched_df),
        "matched_amount": matched_df["internal_amount"].sum() if not matched_df.empty else 0.0,
        "variance_count": len(variance_df),
        "variance_net_diff": variance_df["amount_variance"].sum() if not variance_df.empty else 0.0,
        "unmatched_internal_count": len(unmatched_int_df),
        "unmatched_internal_amount": unmatched_int_df["internal_amount"].sum() if not unmatched_int_df.empty else 0.0,
        "unmatched_settlement_count": len(unmatched_set_df),
        "unmatched_settlement_amount": unmatched_set_df["settlement_amount"].sum() if not unmatched_set_df.empty else 0.0
    }

    return merged, summary


def display_reconciliation_report(summary: Dict[str, Any], date_str: str):
    """
    Renders formatted CLI summary report.
    """
    print("\n" + "=" * 65)
    print(f"       FINSTREAM FINANCIAL RECONCILIATION REPORT")
    print(f"       Reconciliation Date: {date_str}")
    print("=" * 65)
    print(f" Internal Transactions Count : {summary['total_internal_records']:>10}")
    print(f" Settlement File Records Count: {summary['total_settlement_records']:>10}")
    print("-" * 65)
    print(f" [OK] Matched Transactions    : {summary['matched_count']:>10}  |  ${summary['matched_amount']:>12,.2f}")
    print(f" [!] Amount Variances        : {summary['variance_count']:>10}  |  Net Diff: ${summary['variance_net_diff']:>9,.2f}")
    print(f" [?] Unmatched (Internal Only): {summary['unmatched_internal_count']:>10}  |  ${summary['unmatched_internal_amount']:>12,.2f}")
    print(f" [?] Unmatched (Settlement Only): {summary['unmatched_settlement_count']:>8}  |  ${summary['unmatched_settlement_amount']:>12,.2f}")
    print("=" * 65 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="FinStream Settlement Reconciliation Engine")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="Reconciliation target date (YYYY-MM-DD)")
    parser.add_argument("--settlement-file", default="sample_external_settlement.csv",
                        help="Path to external settlement CSV file")
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID", "finstream-gcp-project"),
                        help="GCP Project ID for BigQuery query")
    parser.add_argument("--dataset", default="finstream_dw", help="BigQuery Dataset ID")
    parser.add_argument("--table", default="transactions", help="BigQuery Table ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use synthetic local BigQuery data instead of querying GCP")
    parser.add_argument("--output-csv", default=None,
                        help="Path to save detailed reconciliation CSV output report")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Determine internal data source
    if args.dry_run:
        logger.info(f"[DRY-RUN] Generating synthetic internal BigQuery data for {args.date}...")
        internal_df = generate_mock_internal_df(args.date)
    else:
        internal_df = fetch_internal_transactions_bq(args.project_id, args.dataset, args.table, args.date)

    # Load external settlement CSV
    settlement_df = load_settlement_csv(args.settlement_file)

    # Execute reconciliation logic
    reconciled_df, summary_metrics = perform_reconciliation(internal_df, settlement_df)

    # Print summary
    display_reconciliation_report(summary_metrics, args.date)

    # Optional detailed output export
    if args.output_csv:
        reconciled_df.to_csv(args.output_csv, index=False)
        logger.info(f"Detailed reconciliation report saved to: {args.output_csv}")
