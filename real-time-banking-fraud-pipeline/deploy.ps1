param(
    [switch]$UseExternalPostgres
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log([string]$Message) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message" -ForegroundColor Green
}

function Warn([string]$Message) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] WARNING: $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    throw $Message
}

function Import-EnvFile([string]$Path) {
    if (-not (Test-Path $Path)) {
        Fail "Missing .env file at '$Path'. Copy .env.example to .env and fill in your values."
    }

    foreach ($rawLine in Get-Content -Path $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1]
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Require-Env([string[]]$Names) {
    foreach ($name in $Names) {
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            Fail "$name must be set. Copy .env.example to .env and fill in your values."
        }
    }
}

function Render-ConnectorConfig(
    [string]$TemplateFile,
    [string]$OutputFile,
    [string]$DatabaseHost,
    [string]$DatabasePort,
    [string]$DatabaseUser,
    [string]$DatabasePassword,
    [string]$DatabaseName
) {
    $content = Get-Content -Path $TemplateFile -Raw
    $content = $content.Replace("__DATABASE_HOST__", $DatabaseHost)
    $content = $content.Replace("__DATABASE_PORT__", $DatabasePort)
    $content = $content.Replace("__DATABASE_USER__", $DatabaseUser)
    $content = $content.Replace("__DATABASE_PASSWORD__", $DatabasePassword)
    $content = $content.Replace("__DATABASE_DBNAME__", $DatabaseName)
    $null = $content | ConvertFrom-Json
    Set-Content -Path $OutputFile -Value $content -Encoding utf8NoBOM
}

Push-Location $PSScriptRoot

$renderedConfig = $null

try {
    Import-EnvFile (Join-Path $PSScriptRoot ".env")

    if (-not $PSBoundParameters.ContainsKey("UseExternalPostgres")) {
        $UseExternalPostgres = ([Environment]::GetEnvironmentVariable("USE_EXTERNAL_POSTGRES", "Process") -eq "true")
    }

    $connectUrl = "http://localhost:8083"
    $connectTimeout = 120
    $expectedSourceTables = 5
    $debeziumConfigFile = if ($UseExternalPostgres) { "debezium-connector.external.avro.json" } else { "debezium-connector.avro.json" }
    $debeziumConnectorName = "banking-postgres-cdc-avro"

    $postgresDb = [Environment]::GetEnvironmentVariable("POSTGRES_DB", "Process")
    if (-not $postgresDb) {
        $postgresDb = "banking"
    }

    if ($UseExternalPostgres) {
        Require-Env @(
            "EXTERNAL_POSTGRES_CONTAINER",
            "EXTERNAL_POSTGRES_PSQL_USER",
            "EXTERNAL_POSTGRES_DB",
            "EXTERNAL_POSTGRES_USER",
            "EXTERNAL_POSTGRES_PASSWORD"
        )
    } else {
        Require-Env @(
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "DEBEZIUM_REPLICATION_USER",
            "DEBEZIUM_REPLICATION_PASSWORD"
        )
    }

    Log "Starting Docker Compose stack..."
    $services = @("zookeeper", "kafka", "schema-registry", "kafka-connect", "kafka-ui")
    if (-not $UseExternalPostgres) {
        $services = @("postgres") + $services
    }

    & docker compose --env-file .env up -d @services
    if ($LASTEXITCODE -ne 0) {
        Fail "docker compose up failed."
    }

    Log "Waiting for Kafka Connect REST API ($connectTimeout s)..."
    $elapsed = 0
    while ($true) {
        try {
            $response = Invoke-WebRequest -Uri "$connectUrl/connectors" -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                break
            }
        } catch {
        }

        Start-Sleep -Seconds 5
        $elapsed += 5
        if ($elapsed -ge $connectTimeout) {
            Fail "Kafka Connect did not start in time."
        }
        Write-Host -NoNewline "."
    }
    Write-Host ""
    Log "Kafka Connect is ready."

    $registerDebezium = $true
    if ($UseExternalPostgres) {
        $externalPostgresContainer = [Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_CONTAINER", "Process")
        $externalPostgresPsqlUser = [Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_PSQL_USER", "Process")
        $externalPostgresDb = [Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_DB", "Process")
        $externalPostgresHost = [Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_HOST", "Process")
        if (-not $externalPostgresHost) {
            $externalPostgresHost = "host.docker.internal"
        }
        $externalPostgresPort = [Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_PORT", "Process")
        if (-not $externalPostgresPort) {
            $externalPostgresPort = "5432"
        }

        Log "Using external PostgreSQL container: $externalPostgresContainer"
        $runningContainers = (& docker ps --format '{{.Names}}') | Where-Object { $_ }
        if ($runningContainers -notcontains $externalPostgresContainer) {
            Warn "External PostgreSQL container '$externalPostgresContainer' is not running. Debezium registration is skipped."
            $registerDebezium = $false
        } else {
            $walLevel = (& docker exec $externalPostgresContainer psql -U $externalPostgresPsqlUser -d $externalPostgresDb -Atc "SHOW wal_level;" 2>$null)
            if (-not $walLevel) {
                $walLevel = "UNKNOWN"
            }

            $tableCount = (& docker exec $externalPostgresContainer psql -U $externalPostgresPsqlUser -d $externalPostgresDb -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('customers','accounts','cards','transactions','fraud_alerts');" 2>$null)
            if (-not $tableCount) {
                $tableCount = "0"
            }

            if ($walLevel -ne "logical") {
                Warn "External PostgreSQL wal_level is '$walLevel'. Debezium needs 'logical', so connector registration is skipped."
                $registerDebezium = $false
            }

            if ($tableCount -ne "$expectedSourceTables") {
                Warn "Expected banking source tables were not found in $externalPostgresDb. Connector registration is skipped until 01_schema.sql and 02_seed.sql are loaded."
                $registerDebezium = $false
            }
        }
    } else {
        Log "Using Compose-managed PostgreSQL."
    }

    if ($registerDebezium) {
        Log "Registering Debezium PostgreSQL connector..."
        $renderedConfig = [System.IO.Path]::GetTempFileName()

        if ($UseExternalPostgres) {
            Render-ConnectorConfig `
                -TemplateFile $debeziumConfigFile `
                -OutputFile $renderedConfig `
                -DatabaseHost ([Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_HOST", "Process") ?? "host.docker.internal") `
                -DatabasePort ([Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_PORT", "Process") ?? "5432") `
                -DatabaseUser ([Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_USER", "Process")) `
                -DatabasePassword ([Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_PASSWORD", "Process")) `
                -DatabaseName ([Environment]::GetEnvironmentVariable("EXTERNAL_POSTGRES_DB", "Process"))
        } else {
            Render-ConnectorConfig `
                -TemplateFile $debeziumConfigFile `
                -OutputFile $renderedConfig `
                -DatabaseHost "postgres" `
                -DatabasePort "5432" `
                -DatabaseUser ([Environment]::GetEnvironmentVariable("DEBEZIUM_REPLICATION_USER", "Process")) `
                -DatabasePassword ([Environment]::GetEnvironmentVariable("DEBEZIUM_REPLICATION_PASSWORD", "Process")) `
                -DatabaseName $postgresDb
        }

        $body = Get-Content -Path $renderedConfig -Raw
        $registerResponse = Invoke-WebRequest `
            -Uri "$connectUrl/connectors" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -UseBasicParsing `
            -SkipHttpErrorCheck

        switch ([int]$registerResponse.StatusCode) {
            201 { Log "Debezium connector registered (201 Created)." }
            409 { Warn "Debezium connector already exists (409 Conflict). Skipping." }
            default { Fail "Failed to register Debezium connector. HTTP $($registerResponse.StatusCode)`n$($registerResponse.Content)" }
        }

        Start-Sleep -Seconds 5
        $statusResponse = Invoke-RestMethod -Uri "$connectUrl/connectors/$debeziumConnectorName/status" -TimeoutSec 10
        $connectorState = $statusResponse.connector.state
        Log "Connector state: $connectorState"
        if ($connectorState -ne "RUNNING") {
            $trace = ""
            if ($statusResponse.tasks -and $statusResponse.tasks[0].trace) {
                $trace = ($statusResponse.tasks[0].trace -split "`r?`n")[0]
            }
            Warn "Connector is not RUNNING yet. $($trace ? $trace : 'Check Kafka Connect and PostgreSQL logical replication settings.')"
        }
    } else {
        Warn "Debezium connector registration skipped."
    }

    Log "Checking Kafka topics..."
    Start-Sleep -Seconds 3
    $topics = & docker exec banking-kafka kafka-topics --bootstrap-server localhost:9092 --list
    $bankingTopics = $topics | Where-Object { $_ -match '^banking_avro\.' }
    if ($bankingTopics) {
        $bankingTopics | ForEach-Object { Write-Host $_ }
    } else {
        Warn "No banking Avro topics yet - CDC may still be initialising."
    }

    Write-Host ""
    Write-Host "======================================================"
    Write-Host " BANKING PIPELINE DEPLOYED"
    Write-Host "======================================================"
    if ($UseExternalPostgres) {
        Write-Host " PostgreSQL    : external container"
        Write-Host "                 $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_CONTAINER', 'Process')) / $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_DB', 'Process'))"
    } else {
        Write-Host " PostgreSQL    : localhost:5432"
        Write-Host "                 db=$postgresDb"
    }
    Write-Host " Kafka Broker  : localhost:29092"
    Write-Host " Kafka Connect : http://localhost:8083"
    Write-Host " Kafka UI      : http://localhost:8080"
    Write-Host " Schema Reg.   : http://localhost:8081"
    Write-Host " CDC Format    : Avro + Schema Registry"
    Write-Host " Exasol Sync   : official Kafka connector"
    Write-Host ""
    Write-Host "Next steps:"
    if ($UseExternalPostgres) {
        Write-Host " 1. External PostgreSQL prerequisites:"
        Write-Host "    - Container: $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_CONTAINER', 'Process'))"
        Write-Host "    - Database : $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_DB', 'Process'))"
        Write-Host "    - Required : wal_level=logical"
        Write-Host "    - Load schema with:"
        Write-Host "      docker exec -i $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_CONTAINER', 'Process')) psql -U $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_PSQL_USER', 'Process')) -d $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_DB', 'Process')) < 01_schema.sql"
        Write-Host "      docker exec -i $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_CONTAINER', 'Process')) psql -U $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_PSQL_USER', 'Process')) -d $([Environment]::GetEnvironmentVariable('EXTERNAL_POSTGRES_DB', 'Process')) < 02_seed.sql"
    } else {
        Write-Host " 1. Local PostgreSQL is ready on localhost:5432."
    }
    Write-Host ""
    Write-Host " 2. In Exasol, run:"
    Write-Host "      01_exasol_schema.sql"
    Write-Host "      03_exasol_kafka_connector_schema.sql"
    Write-Host " 3. Upload the official kafka-connector-extension JAR to BucketFS."
    Write-Host "    If Exasol runs in Docker, prepare its network access with:"
    Write-Host "      pwsh -File .\prepare_exasol_docker.ps1"
    Write-Host "    Then run:"
    Write-Host "      04_exasol_kafka_connector_udfs.sql"
    Write-Host "      05_exasol_kafka_connector_import_avro.sql"
    Write-Host "      06_exasol_kafka_connector_merge.sql"
    Write-Host " 4. Re-run 05_exasol_kafka_connector_import_avro.sql and"
    Write-Host "    06_exasol_kafka_connector_merge.sql whenever you want"
    Write-Host "    to pull the latest Kafka changes into Exasol."
    Write-Host ""
    Write-Host " 5. Train ML models:"
    Write-Host "    pip install -r requirements.txt && python train_pipeline.py"
    Write-Host ""
    Write-Host " 6. Upload model to Exasol BucketFS:"
    Write-Host '    curl -X PUT -T models/fraud_model.pkl \'
    Write-Host "      http://YOUR_EXASOL_HOST:2580/models/fraud_model.pkl"
    Write-Host ""
    Write-Host " 7. Run feature + UDF SQL in Exasol:"
    Write-Host "    Execute 02_features_and_udfs.sql in EXAplus"
}
finally {
    if ($renderedConfig -and (Test-Path $renderedConfig)) {
        Remove-Item $renderedConfig -Force
    }
    Pop-Location
}
