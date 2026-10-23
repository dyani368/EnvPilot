output "instance_id" {
  value = aws_instance.sandbox.id
}

output "private_ip" {
  value = aws_instance.sandbox.private_ip
}
