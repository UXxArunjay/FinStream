"""
FinStream Cloud Function: Transaction Ingestion & Validation
-----------------------------------------------------------
Cloud Function (Gen 2) triggered by GCP Pub/Sub event messages.
Decodes base64 payload, validates payload structure and field formats,
and streams the validated transaction into GCP BigQuery.
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Tuple

import functions_framework
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_transaction")

# Initialize BigQuery client (re-used across warm function invocations)
bq_client = None

DATASET_ID = os.getenv("BIGQUERY_DATASET", "finstream_dw")
TABLE_ID = os.getenv("BIGQUERY_TABLE", "transactions")
ALLOWED_STATUSES = {"COMPLETED", "PENDING", "FAILED"}


def get_bq_client() -> bigquery.Client:
    """Lazy initialization of BigQuery client."""
    global bq_client
    if bq_client is None:
        bq_client = bigquery.Client()
    return bq_client


def validate_transaction_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates transaction fields against expected types and bounds.
    Returns (is_valid, error_message).
    """
    required_fields = ["transaction_id", "account_id", "amount", "currency", "timestamp", "status", "merchant_id"]
    for field in required_fields:
        if field not in payload or payload[field] is None:
            return False, f"Missing required field: '{field}'"

    # Validate amount numeric type and value
    try:
        amount = float(payload["amount"])
        if amount <= 0:
            return False, f"Invalid amount '{amount}': must be greater than 0"
    except (ValueError, TypeError):
        return False, f"Invalid amount format: '{payload['amount']}'"

    # Validate status
    status = str(payload["status"]).upper()
    if status not in ALLOWED_STATUSES:
        return False, f"Invalid status '{status}': must be one of {ALLOWED_STATUSES}"

    # Validate ISO-8601 timestamp format
    try:
        # Standard ISO 8601 parsing
        ts_str = payload["timestamp"].replace("Z", "+00:00")
        datetime.fromisoformat(ts_str)
    except Exception as err:
        return False, f"Invalid timestamp format '{payload['timestamp']}': {err}"

    return True, ""


def stream_to_bigquery(record: Dict[str, Any], project_id: str = None) -> bool:
    """
    Streams a single validated record into the target BigQuery table.
    """
    client = get_bq_client()
    table_ref = f"{client.project}.{DATASET_ID}.{TABLE_ID}"

    rows_to_insert = [record]
    errors = client.insert_rows_json(table_ref, rows_to_insert)

    if not errors:
        logger.info(f"Successfully streamed transaction {record['transaction_id']} to {table_ref}")
        return True
    else:
        logger.error(f"Failed streaming transaction {record['transaction_id']} to BigQuery: {errors}")
        return False


@functions_framework.cloud_event
def process_pubsub_event(cloud_event):
    """
    Cloud Event entrypoint triggered by GCP Pub/Sub message.
    """
    try:
        # Pub/Sub payload is encapsulated inside cloud_event.data['message']['data']
        pubsub_message = cloud_event.data.get("message", {})
        data_base64 = pubsub_message.get("data")

        if not data_base64:
            logger.warning("Received Pub/Sub message with empty data payload.")
            return

        # Decode base64 data to string and parse JSON
        decoded_json = base64.b64decode(data_base64).decode("utf-8")
        payload = json.loads(decoded_json)

        logger.info(f"Received transaction payload: {payload.get('transaction_id')}")

        # Validate schema and business constraints
        is_valid, error_msg = validate_transaction_payload(payload)
        if not is_valid:
            logger.error(f"Transaction validation failed: {error_msg}. Payload: {payload}")
            return

        # Stream insertion into BigQuery
        stream_to_bigquery(payload)

    except json.JSONDecodeError as err:
        logger.error(f"Malformed JSON payload in Pub/Sub message: {err}")
    except Exception as err:
        logger.error(f"Unexpected error processing Pub/Sub event: {err}", exc_info=True)
