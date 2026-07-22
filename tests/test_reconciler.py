"""
Unit tests for FinStream Reconciliation Engine & Validation logic
"""

import unittest
import pandas as pd

from reconciliation.reconciler import perform_reconciliation
from cloud_functions.ingest_transaction.main import validate_transaction_payload


class TestReconciliationEngine(unittest.TestCase):

    def setUp(self):
        """Set up test DataFrames for internal logs and settlement records."""
        self.internal_data = pd.DataFrame([
            {"transaction_id": "txn-1", "internal_amount": 100.00, "account_id": "ACC-1"},
            {"transaction_id": "txn-2", "internal_amount": 250.00, "account_id": "ACC-2"}, # Variance ($250 vs $200)
            {"transaction_id": "txn-3", "internal_amount": 75.50,  "account_id": "ACC-3"}, # Unmatched Internal
        ])

        self.settlement_data = pd.DataFrame([
            {"settlement_id": "s-1", "transaction_id": "txn-1", "settlement_amount": 100.00}, # Matched
            {"settlement_id": "s-2", "transaction_id": "txn-2", "settlement_amount": 200.00}, # Variance
            {"settlement_id": "s-4", "transaction_id": "txn-4", "settlement_amount": 500.00}, # Unmatched Settlement
        ])

    def test_perform_reconciliation_classification(self):
        """Verify outer join reconciliation categorizes records accurately."""
        reconciled_df, summary = perform_reconciliation(self.internal_data, self.settlement_data)

        self.assertEqual(summary["total_internal_records"], 3)
        self.assertEqual(summary["total_settlement_records"], 3)

        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["matched_amount"], 100.00)

        self.assertEqual(summary["variance_count"], 1)
        self.assertEqual(summary["variance_net_diff"], 50.00) # $250 - $200

        self.assertEqual(summary["unmatched_internal_count"], 1)
        self.assertEqual(summary["unmatched_internal_amount"], 75.50)

        self.assertEqual(summary["unmatched_settlement_count"], 1)
        self.assertEqual(summary["unmatched_settlement_amount"], 500.00)


class TestCloudFunctionPayloadValidation(unittest.TestCase):

    def test_valid_payload(self):
        """Verify valid transaction payload passes schema check."""
        valid_payload = {
            "transaction_id": "abc-123",
            "account_id": "ACC-999",
            "amount": 199.99,
            "currency": "USD",
            "timestamp": "2026-07-22T12:00:00Z",
            "status": "COMPLETED",
            "merchant_id": "MERCH-88"
        }
        is_valid, msg = validate_transaction_payload(valid_payload)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_missing_required_field(self):
        """Verify payload missing required field fails validation."""
        invalid_payload = {
            "transaction_id": "abc-123",
            "account_id": "ACC-999",
            # "amount" missing
            "currency": "USD",
            "timestamp": "2026-07-22T12:00:00Z",
            "status": "COMPLETED",
            "merchant_id": "MERCH-88"
        }
        is_valid, msg = validate_transaction_payload(invalid_payload)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", msg)

    def test_invalid_amount_or_status(self):
        """Verify negative amount or invalid status string fails validation."""
        payload_neg_amount = {
            "transaction_id": "abc-123",
            "account_id": "ACC-999",
            "amount": -50.00,
            "currency": "USD",
            "timestamp": "2026-07-22T12:00:00Z",
            "status": "COMPLETED",
            "merchant_id": "MERCH-88"
        }
        is_valid, msg = validate_transaction_payload(payload_neg_amount)
        self.assertFalse(is_valid)
        self.assertIn("must be greater than 0", msg)

        payload_bad_status = payload_neg_amount.copy()
        payload_bad_status["amount"] = 10.00
        payload_bad_status["status"] = "INVALID_STATUS"
        is_valid, msg = validate_transaction_payload(payload_bad_status)
        self.assertFalse(is_valid)
        self.assertIn("Invalid status", msg)


if __name__ == "__main__":
    unittest.main()
