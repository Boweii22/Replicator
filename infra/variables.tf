variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "image" {
  type        = string
  description = "Immutable API/worker container image digest"
}

variable "model_id" {
  type    = string
  default = "gemini-3.5-flash"
}

variable "allowed_ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_ALL"
}
