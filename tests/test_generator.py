"""
Unit tests for FinStream Synthetic Transaction Generator Simulator
"""

import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from simulator.transaction_generator import generate_transaction, run_simulator


class TestTransactionGenerator(unittest.TestCase):

    def test_generate_transaction_schema(self):
        """Verify generated transaction payload contains all required schema keys."""
        txn = generate_transaction()

        required_keys = {
            "transaction_id",
            "account_id",
            "amount",
            "currency",
            "timestamp",
            "status",
            "merchant_id",
        }
        self.assertTrue(required_keys.issubset(txn.keys()))

    def test_generate_transaction_field_types(self):
        """Verify data types and constraints of generated fields."""
        txn = generate_transaction()

        self.assertIsInstance(txn["transaction_id"], str)
        self.assertTrue(len(txn["transaction_id"]) > 0)
        self.assertTrue(txn["account_id"].startswith("ACC-"))
        self.assertTrue(txn["merchant_id"].startswith("MERCH-"))
        self.assertIsInstance(txn["amount"], float)
        self.assertGreater(txn["amount"], 0.0)
        self.assertEqual(txn["currency"], "USD")
        self.assertIn(txn["status"], ["COMPLETED", "PENDING", "FAILED"])

        # Timestamp ISO format check
        ts_str = txn["timestamp"].replace("Z", "+00:00")
        parsed_dt = datetime.fromisoformat(ts_str)
        self.assertIsNotNone(parsed_dt)

    def test_run_simulator_dry_run(self):
        """Verify simulator runs count-limited dry run without errors."""
        try:
            run_simulator(
                project_id="test-project",
                topic_id="test-topic",
                rate=100,
                total_count=5,
                dry_run=True
            )
        except Exception as exc:
            self.fail(f"run_simulator raised an exception in dry-run mode: {exc}")


if __name__ == "__main__":
    unittest.main()
