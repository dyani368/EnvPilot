provider "aws" {
  region = var.aws_region
}

data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "sandbox" {
  name_prefix = "envpilot-${var.environment_id}-"
  description = "EnvPilot sandbox: no inbound access"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    EnvPilotEnvironment = var.environment_id
    ExpiresAt           = var.expires_at
    ManagedBy           = "EnvPilot"
  }
}

resource "aws_iam_role" "ssm" {
  name_prefix = "envpilot-${substr(var.environment_id, 0, 8)}-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
  tags = {
    EnvPilotEnvironment = var.environment_id
    ManagedBy           = "EnvPilot"
  }
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name_prefix = "envpilot-${substr(var.environment_id, 0, 8)}-"
  role        = aws_iam_role.ssm.name
}

resource "aws_instance" "sandbox" {
  ami                         = data.aws_ssm_parameter.ami.value
  instance_type               = "t3.micro"
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.sandbox.id]
  iam_instance_profile        = aws_iam_instance_profile.ssm.name
  associate_public_ip_address = false
  monitoring                  = false

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }
  tags = {
    Name                = "envpilot-${var.environment_id}"
    EnvPilotEnvironment = var.environment_id
    ExpiresAt           = var.expires_at
    ManagedBy           = "EnvPilot"
  }
}
