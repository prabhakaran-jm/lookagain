# Restart the LookAgain COOL instance after an idle stop.
param(
    [string]$InstanceId = "i-0f6e85df280826133",
    [string]$Region = "us-east-1"
)
$ErrorActionPreference = "Stop"
if (-not $env:AWS_PROFILE) { $env:AWS_PROFILE = "lookagain" }

aws ec2 start-instances --region $Region --instance-ids $InstanceId | Out-Host
aws ec2 wait instance-running --region $Region --instance-ids $InstanceId
$ip = aws ec2 describe-instances --region $Region --instance-ids $InstanceId `
    --query "Reservations[0].Instances[0].PublicIpAddress" --output text
Write-Host "RUNNING $InstanceId  PUBLIC_IP=$ip"
Write-Host "SSH: ssh -i ~/.ssh/lookagain-cool.pem ubuntu@$ip"
Write-Host "Then: bash /tmp/start_cool_app.sh  (or scp scripts/start_cool_app.sh and run)"
"$InstanceId`n$ip" | Set-Content -Encoding ascii deploy\cool_instance.txt
