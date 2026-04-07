variable "jwt_signing_key" {
  description = "The signing key for JWT tokens"
  sensitive   = true
  type        = string
}

variable "testflinger_secrets_master_key" {
  description = "Master key for Testflinger secrets encryption"
  type        = string
  sensitive   = true
  default     = ""
}
