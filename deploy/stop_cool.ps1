# Hard stop for COOL free-trial conversion (~2026-10-29 morning).
# Usage: $env:AWS_PROFILE='lookagain'; .\deploy\stop_cool.ps1 [-Terminate]

param(
    [switch]$Terminate
)

$ErrorActionPreference = "Stop"
$Region = "us-east-1"
$InstanceId = "i-0f6e85df280826133"

if (-not $env:AWS_PROFILE) { $env:AWS_PROFILE = "lookagain" }

Write-Host "Profile=$env:AWS_PROFILE Instance=$InstanceId"
aws sts get-caller-identity --region $Region | Out-Host

if ($Terminate) {
    Write-Host "Terminating $InstanceId ..."
    aws ec2 terminate-instances --region $Region --instance-ids $InstanceId
} else {
    Write-Host "Stopping $InstanceId (EBS retained; Marketplace software fee stops while stopped) ..."
    aws ec2 stop-instances --region $Region --instance-ids $InstanceId
}

aws ec2 describe-instances --region $Region --instance-ids $InstanceId `
    --query "Reservations[0].Instances[0].State.Name" --output text

Write-Host ""
Write-Host "NEXT (manual in Console): AWS Marketplace → Manage subscriptions → cancel COOL"
Write-Host "  https://console.aws.amazon.com/marketplace/home#/subscriptions"
Write-Host "Confirm trial end date before cancel if you still need a short COOL window."
