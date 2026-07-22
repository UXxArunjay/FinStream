variable "project_id" {
  description = "The GCP Project ID where resources will be deployed"
  type        = string
}

variable "region" {
  description = "GCP Region for resource deployment"
  type        = string
  default     = "us-central1"
}

variable "dataset_id" {
  description = "The BigQuery dataset ID for financial analytics"
  type        = string
  default     = "finstream_dw"
}

variable "table_id" {
  description = "The BigQuery table ID for storing transaction events"
  type        = string
  default     = "transactions"
}

variable "topic_name" {
  description = "The Pub/Sub topic name for streaming transaction events"
  type        = string
  default     = "finstream-events"
}
