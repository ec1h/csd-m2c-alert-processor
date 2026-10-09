locals {
  environment = "test"

  # The live non-prod stack was created before this repo existed and already
  # has Terraform state here. Reusing it adopts the stack in place instead of
  # building a duplicate. Do not change without moving the state first.
  state_bucket_name = "905418043725-terraform-af-south-1"
  state_key         = "csd/m2c-alert-integration/terraform.tfstate"
  lock_table_name   = "905418043725-terraform-af-south-1"
}
