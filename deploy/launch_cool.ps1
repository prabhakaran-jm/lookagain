# Launch COOL Graviton4 AMI on c8g.large after Marketplace subscribe + SSO login.
# Usage: .\deploy\launch_cool.ps1 -Profile archon -KeyName my-key -SubnetId subnet-xxx -SecurityGroupId sg-xxx

param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [Parameter(Mandatory = $true)][string]$KeyName,
    [Parameter(Mandatory = $true)][string]$SubnetId,
    [Parameter(Mandatory = $true)][string]$SecurityGroupId,
    [string]$Region = "us-east-1",
    [string]$InstanceType = "c8g.large",
    [string]$AmiId = ""
)

$ErrorActionPreference = "Stop"

Write-Host "Identity:"
aws sts get-caller-identity --profile $Profile --region $Region

if (-not $AmiId) {
    Write-Host "Looking up subscribed COOL AMI (arm64)…"
    $AmiId = aws ec2 describe-images `
        --profile $Profile `
        --region $Region `
        --owners aws-marketplace `
        --filters "Name=name,Values=*OpenCV*Graviton*" "Name=architecture,Values=arm64" "Name=state,Values=available" `
        --query "sort_by(Images,&CreationDate)[-1].ImageId" `
        --output text
    if (-not $AmiId -or $AmiId -eq "None") {
        throw "No Marketplace AMI found. Subscribe first: https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs"
    }
}

Write-Host "Using AMI $AmiId on $InstanceType"

# IMDSv2 required
$imds = @"
{
  \"HttpTokens\": \"required\",
  \"HttpPutResponseHopLimit\": 2,
  \"HttpEndpoint\": \"enabled\"
}
"@

$iid = aws ec2 run-instances `
    --profile $Profile `
    --region $Region `
    --image-id $AmiId `
    --instance-type $InstanceType `
    --key-name $KeyName `
    --subnet-id $SubnetId `
    --security-group-ids $SecurityGroupId `
    --metadata-options $imds `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=lookagain-cool},{Key=Project,Value=lookagain}]" `
    --query "Instances[0].InstanceId" `
    --output text

Write-Host "Launched $iid — waiting for running…"
aws ec2 wait instance-running --profile $Profile --region $Region --instance-ids $iid
$ip = aws ec2 describe-instances --profile $Profile --region $Region --instance-ids $iid `
    --query "Reservations[0].Instances[0].PublicIpAddress" --output text
Write-Host "Public IP: $ip"
Write-Host "ssh -i <key.pem> ubuntu@$ip"
Write-Host "Then: source /opt/cool/venvs/python_3.12/bin/activate"
