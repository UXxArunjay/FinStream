output "pubsub_topic_id" {
  description = "The ID of the created Pub/Sub topic"
  value       = google_pubsub_topic.finstream_events.id
}

output "pubsub_subscription_id" {
  description = "The ID of the created Pub/Sub subscription"
  value       = google_pubsub_subscription.finstream_events_sub.id
}

output "bigquery_dataset_id" {
  description = "The ID of the created BigQuery dataset"
  value       = google_bigquery_dataset.finstream_dw.dataset_id
}

output "bigquery_table_id" {
  description = "The ID of the created BigQuery transactions table"
  value       = google_bigquery_table.transactions.id
}
