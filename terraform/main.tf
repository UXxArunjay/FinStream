terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# Pub/Sub Infrastructure
# ------------------------------------------------------------------------------

# Pub/Sub Topic for transaction ingestion stream
resource "google_pubsub_topic" "finstream_events" {
  name = var.topic_name

  labels = {
    environment = "production"
    pipeline    = "finstream"
  }
}

# Pub/Sub Subscription for subscribers or dead-letter processing
resource "google_pubsub_subscription" "finstream_events_sub" {
  name  = "${var.topic_name}-sub"
  topic = google_pubsub_topic.finstream_events.name

  # Retain unacknowledged messages for 7 days
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  ack_deadline_seconds = 20

  expiration_policy {
    ttl = "" # Never expire
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# ------------------------------------------------------------------------------
# BigQuery Data Warehouse Infrastructure
# ------------------------------------------------------------------------------

# BigQuery Dataset
resource "google_bigquery_dataset" "finstream_dw" {
  dataset_id                  = var.dataset_id
  friendly_name               = "FinStream Data Warehouse"
  description                 = "Real-time financial transactions data warehouse"
  location                    = "US"
  default_table_expiration_ms = null

  labels = {
    environment = "production"
    pipeline    = "finstream"
  }
}

# BigQuery Transactions Table (Partitioned by timestamp DAY, clustered by account_id)
resource "google_bigquery_table" "transactions" {
  dataset_id = google_bigquery_dataset.finstream_dw.dataset_id
  table_id   = var.table_id

  description = "Partitioned and clustered transaction events table"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["account_id"]

  schema = <<EOF
[
  {
    "name": "transaction_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique identifier for the financial transaction (UUID)"
  },
  {
    "name": "account_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Account identifier associated with the transaction"
  },
  {
    "name": "amount",
    "type": "NUMERIC",
    "mode": "REQUIRED",
    "description": "Transaction amount (2 decimal precision)"
  },
  {
    "name": "currency",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Three-letter ISO currency code (e.g., USD)"
  },
  {
    "name": "timestamp",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "UTC Timestamp when transaction occurred (ISO-8601)"
  },
  {
    "name": "status",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Transaction state: COMPLETED, PENDING, or FAILED"
  },
  {
    "name": "merchant_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Merchant identifier handling the transaction"
  }
]
EOF

  labels = {
    environment = "production"
    pipeline    = "finstream"
  }
}
