"""
FinStream Transaction Generator Simulator
-----------------------------------------
Generates synthetic financial transaction JSON payloads using Faker and publishes
them asynchronously to a GCP Pub/Sub topic at a configurable rate (default: 10 msg/sec).
Supports a --dry-run mode for local development and testing without GCP credentials.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from faker import Faker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("transaction_generator")

fake = Faker()

# Pre-generated pools for consistent synthetic data distribution
ACCOUNT_POOL = [f"ACC-{fake.unique.random_number(digits=6, fix_len=True)}" for _ in range(500)]
MERCHANT_POOL = [f"MERCH-{fake.unique.random_number(digits=4, fix_len=True)}" for _ in range(100)]
STATUSES = ["COMPLETED", "PENDING", "FAILED"]
STATUS_WEIGHTS = [0.80, 0.15, 0.05]


def generate_transaction() -> Dict[str, Any]:
    """
    Generates a single synthetic financial transaction record conforming to FinStream schema.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    amount = round(random.uniform(1.00, 4999.99), 2)

    return {
        "transaction_id": str(uuid.uuid4()),
        "account_id": random.choice(ACCOUNT_POOL),
        "amount": amount,
        "currency": "USD",
        "timestamp": now_utc,
        "status": random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0],
        "merchant_id": random.choice(MERCHANT_POOL)
    }


def publish_callback(future, transaction_id: str):
    """
    Callback function invoked upon receiving a response from GCP Pub/Sub.
    """
    try:
        message_id = future.result()
        logger.debug(f"Successfully published txn {transaction_id} -> Msg ID: {message_id}")
    except Exception as exc:
        logger.error(f"Failed to publish transaction {transaction_id}: {exc}")


def run_simulator(project_id: str, topic_id: str, rate: int, total_count: int = None, dry_run: bool = False):
    """
    Runs the transaction publishing loop.
    
    :param project_id: GCP Project ID
    :param topic_id: Pub/Sub Topic ID
    :param rate: Target messages per second
    :param total_count: Total number of messages to publish (None for continuous loop)
    :param dry_run: If True, prints messages to stdout without contacting GCP
    """
    publisher = None
    topic_path = None

    if not dry_run:
        try:
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            topic_path = publisher.topic_path(project_id, topic_id)
            logger.info(f"Initialized Pub/Sub publisher for topic: {topic_path}")
        except Exception as err:
            logger.warning(f"Failed to initialize GCP Pub/Sub client ({err}). Falling back to --dry-run mode.")
            dry_run = True

    delay = 1.0 / rate if rate > 0 else 0.1
    published_count = 0

    logger.info(f"Starting transaction generator stream (Rate: {rate} msg/sec, Dry Run: {dry_run})...")

    try:
        while True:
            txn = generate_transaction()
            payload_bytes = json.dumps(txn).encode("utf-8")

            if dry_run:
                logger.info(f"[DRY-RUN] Transaction: {json.dumps(txn)}")
            else:
                future = publisher.publish(topic_path, data=payload_bytes)
                future.add_done_callback(
                    lambda f, tid=txn["transaction_id"]: publish_callback(f, tid)
                )

            published_count += 1

            if total_count and published_count >= total_count:
                logger.info(f"Reached specified target count of {total_count} transactions. Stopping.")
                break

            time.sleep(delay)

    except KeyboardInterrupt:
        logger.info("\nSimulation stopped by user.")
    finally:
        logger.info(f"Total transactions published in session: {published_count}")


def parse_args():
    parser = argparse.ArgumentParser(description="FinStream Synthetic Financial Transaction Simulator")
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID", "finstream-gcp-project"),
                        help="GCP Project ID")
    parser.add_argument("--topic-id", default=os.getenv("PUBSUB_TOPIC_ID", "finstream-events"),
                        help="Pub/Sub Topic ID")
    parser.add_argument("--rate", type=int, default=10,
                        help="Messages published per second (default: 10)")
    parser.add_argument("--count", type=int, default=None,
                        help="Total number of messages to publish (default: continuous loop)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print events to console without publishing to GCP")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_simulator(
        project_id=args.project_id,
        topic_id=args.topic_id,
        rate=args.rate,
        total_count=args.count,
        dry_run=args.dry_run
    )
