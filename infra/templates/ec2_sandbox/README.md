# EC2 sandbox template

One fixed `t3.micro` Amazon Linux 2023 instance in Sydney, with no inbound security-group rules, no public IP, required IMDSv2, encrypted 8 GiB root volume, and an SSM instance profile. The caller supplies a reviewed VPC and subnet. The subnet must have suitable SSM connectivity (NAT or VPC endpoints) for management and health checks. Provisioning is disabled until this template is validated and the deployment role and state bucket are configured.

Initialize the S3 backend with a distinct key `envpilot/environments/<uuid>/terraform.tfstate`, `encrypt=true`, and `use_lockfile=true`. Never commit backend credentials or state.
