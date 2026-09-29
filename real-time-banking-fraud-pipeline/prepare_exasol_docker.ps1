param(
    [string]$ExasolContainerName = $(if ($env:EXASOL_CONTAINER_NAME) { $env:EXASOL_CONTAINER_NAME } else { "exasol-db" }),
    [string]$KafkaContainerName = $(if ($env:KAFKA_CONTAINER_NAME) { $env:KAFKA_CONTAINER_NAME } else { "banking-kafka" }),
    [string]$SchemaRegistryContainerName = $(if ($env:SCHEMA_REGISTRY_CONTAINER_NAME) { $env:SCHEMA_REGISTRY_CONTAINER_NAME } else { "banking-schema-registry" }),
    [string]$KafkaNetworkName = $env:KAFKA_NETWORK_NAME
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

function Require-RunningContainer {
    param([string]$Name)
    $running = docker ps --format "{{.Names}}"
    if (-not ($running -split "`r?`n" | Where-Object { $_ -eq $Name })) {
        throw "Container '$Name' is not running."
    }
}

Require-RunningContainer $ExasolContainerName
Require-RunningContainer $KafkaContainerName
Require-RunningContainer $SchemaRegistryContainerName

$kafkaInspect = (docker inspect $KafkaContainerName | ConvertFrom-Json)[0]

if (-not $KafkaNetworkName) {
    $KafkaNetworkName = $kafkaInspect.NetworkSettings.Networks.PSObject.Properties.Name | Select-Object -First 1
}

if (-not $KafkaNetworkName) {
    throw "Could not determine the Kafka Docker network."
}

Write-Log "Connecting '$ExasolContainerName' to '$KafkaNetworkName'..."
docker network connect $KafkaNetworkName $ExasolContainerName 2>$null | Out-Null

$kafkaInspect = (docker inspect $KafkaContainerName | ConvertFrom-Json)[0]
$schemaInspect = (docker inspect $SchemaRegistryContainerName | ConvertFrom-Json)[0]

$kafkaIp = $kafkaInspect.NetworkSettings.Networks.$KafkaNetworkName.IPAddress
$schemaRegistryIp = $schemaInspect.NetworkSettings.Networks.$KafkaNetworkName.IPAddress

if (-not $kafkaIp) {
    throw "Could not resolve the Kafka container IP on '$KafkaNetworkName'."
}

if (-not $schemaRegistryIp) {
    throw "Could not resolve the Schema Registry container IP on '$KafkaNetworkName'."
}

Write-Log "Updating /etc/hosts inside '$ExasolContainerName'..."
$currentHosts = docker exec $ExasolContainerName cat /etc/hosts
$filteredHosts = @()
foreach ($line in $currentHosts -split "`r?`n") {
    if ($line -and $line -notmatch '(^|\s)(kafka|schema-registry)$') {
        $filteredHosts += $line
    }
}

$payload = (($filteredHosts -join "`n") + "`n$kafkaIp kafka`n$schemaRegistryIp schema-registry`n") -replace "`r", ""
$payload | docker exec -i $ExasolContainerName tee /etc/hosts > $null

Write-Log "Prepared Exasol container networking."
Write-Log "Kafka: $kafkaIp (alias: kafka)"
Write-Log "Schema Registry: $schemaRegistryIp (alias: schema-registry)"
