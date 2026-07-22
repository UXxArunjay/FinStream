# FinStream 💳⚡

> **Real-Time Financial Transactions Ingestion & Analytics Pipeline**

FinStream is an event-driven, serverless data pipeline hosted on Google Cloud Platform (GCP). It simulates high-volume transactional event streams, processes and transforms payloads in real time, loads structured data into BigQuery for rapid analytics, and executes automated reconciliation with external financial settlement files.

---

## 🏗️ Architecture

```text
[ Transaction Simulator ]
       │ (JSON Stream over gRPC)
       ▼
[ GCP Pub/Sub ]
       │ (Event-Driven Trigger)
       ▼
[ Cloud Functions ] ──(Validation & Transform)
       │
       ▼
[ GCP BigQuery ] ◄──── [ Reconciliation Engine (Python/Pandas) ]
(Partitioned Analytics)                ▲
                                       │
                         [ External Settlement CSV ]
```

---

## ✨ Key Features

- **Real-Time Ingestion:** Handles continuous streams of synthetic financial payloads using GCP Pub/Sub.
- **Serverless Transformation:** Auto-scaling Python Cloud Function (Gen 2) for stream payload validation and insertion.
- **Optimized Data Warehouse:** BigQuery table design with daily partitioning on transaction timestamp (`timestamp`) and clustering by `account_id` for cost-efficient queries.
- **Automated Reconciliation:** Reconciles internal database transaction logs with third-party gateway settlement files to detect unmatched entries and variance amounts.
- **Infrastructure as Code:** Fully automated GCP resource provisioning using Terraform.
- **Offline / Dry-Run Support:** All components support offline simulation and mock datasets for local testing without active GCP billing.

---

## 🛠️ Tech Stack

- **Language:** Python 3.11
- **Cloud Provider:** Google Cloud Platform (GCP)
- **Streaming & Serverless:** GCP Pub/Sub, GCP Cloud Functions (Gen 2)
- **Data Warehouse:** GCP BigQuery
- **Data Processing:** Pandas, PyArrow, Faker
- **IaC & Tooling:** Terraform, Google Cloud SDK

---

## 📂 Repository Structure

```text
finstream/
├── simulator/
│   ├── transaction_generator.py   # Generates synthetic financial JSON events & publishes to Pub/Sub
│   └── requirements.txt
├── cloud_functions/
│   └── ingest_transaction/
│       ├── main.py                # Pub/Sub triggered Cloud Function (validates & streams to BigQuery)
│       └── requirements.txt
├── reconciliation/
│   ├── reconciler.py              # Matches internal BigQuery logs vs external settlement CSVs
│   └── sample_external_settlement.csv
├── terraform/
│   ├── main.tf                    # GCP Infrastructure (Pub/Sub topic/sub, BigQuery dataset/table)
│   ├── variables.tf
│   └── outputs.tf
├── tests/
│   ├── test_generator.py
│   └── test_reconciler.py
├── README.md
└── .gitignore
```

---

## 🚀 Quick Start & Deployment Guide

### Prerequisites

* GCP Account with billing enabled
* `gcloud` CLI & `terraform` installed locally
* Python 3.11+

### Step 1: Provision GCP Infrastructure via Terraform

```bash
cd terraform
terraform init
terraform plan -var="project_id=YOUR_GCP_PROJECT_ID"
terraform apply -var="project_id=YOUR_GCP_PROJECT_ID" -auto-approve
cd ..
```

### Step 2: Deploy the Ingestion Cloud Function

```bash
gcloud functions deploy ingest_transaction \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=./cloud_functions/ingest_transaction \
  --entry-point=process_pubsub_event \
  --trigger-topic=finstream-events \
  --memory=256Mi
```

### Step 3: Run Event Simulator

```bash
cd simulator
pip install -r requirements.txt

# Run live against GCP Pub/Sub:
export GCP_PROJECT_ID="YOUR_GCP_PROJECT_ID"
python transaction_generator.py --rate 10

# Or run locally in dry-run mode (without GCP credentials):
python transaction_generator.py --dry-run --count 20
cd ..
```

### Step 4: Run Reconciliation Engine

```bash
cd reconciliation
pip install pandas google-cloud-bigquery

# Reconcile against live BigQuery table:
python reconciler.py --date 2026-07-22 --settlement-file sample_external_settlement.csv

# Or run locally in dry-run mode:
python reconciler.py --dry-run --date 2026-07-22 --settlement-file sample_external_settlement.csv
cd ..
```

---

## 🧪 Running Unit Tests

Run all unit tests across generator, reconciler, and Cloud Function validation:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 📊 Analytics & Reconciliation Sample Queries

Run analytical checks directly in GCP BigQuery:

```sql
-- Transaction volume and aggregate spend per merchant
SELECT 
  merchant_id, 
  COUNT(transaction_id) AS total_txns, 
  SUM(amount) AS total_volume,
  AVG(amount) AS avg_txn_value
FROM `finstream_dw.transactions`
WHERE DATE(timestamp) = CURRENT_DATE()
GROUP BY merchant_id
ORDER BY total_volume DESC;
```

---

## 📄 License

This project is licensed under the MIT License.
