param(
    [ValidateSet("local", "docker")]
    [string]$Runtime,
    [string]$Model,
    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$serverUrl = "http://127.0.0.1:8080"
$llamaImage = "ghcr.io/ggml-org/llama.cpp:server"
$serverProcess = $null
$containerId = $null
$outputDirectory = Join-Path (Get-Location) "reaper-analysis"
$serverLog = Join-Path $outputDirectory "llama-server.log"
$serverErrorLog = Join-Path $outputDirectory "llama-server-error.log"

function Show-Usage {
    Write-Output "Usage: reaper-workflow.ps1 -Runtime local|docker -Model MODEL.gguf"
    Write-Output ""
    Write-Output "Scan and analyze the current directory, then generate a refactoring prompt."
}

function Test-Command([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Reaper([string[]]$Arguments) {
    & reaper @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "reaper $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-PortInUse {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", 8080)
        return $task.Wait(500) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-LlamaHealth {
    try {
        $response = Invoke-RestMethod -Uri "$serverUrl/health" -TimeoutSec 2
        return $response.status -eq "ok"
    }
    catch {
        return $false
    }
}

function Show-ServerLog {
    if ($containerId) {
        & docker logs $containerId 2>&1 | ForEach-Object {
            [Console]::Error.WriteLine($_)
        }
    }
    else {
        if (Test-Path $serverLog) {
            Get-Content $serverLog | ForEach-Object {
                [Console]::Error.WriteLine($_)
            }
        }
        if (Test-Path $serverErrorLog) {
            Get-Content $serverErrorLog | ForEach-Object {
                [Console]::Error.WriteLine($_)
            }
        }
    }
}

function Stop-ReaperServer {
    if ($containerId) {
        & docker logs $containerId 2>&1 | Set-Content -Path $serverLog
        & docker stop $containerId *> $null
    }
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue
        $serverProcess.WaitForExit(5000) | Out-Null
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

try {
    if (-not $Runtime) {
        throw "-Runtime local|docker is required"
    }
    if (-not $Model) {
        throw "-Model MODEL.gguf is required"
    }
    if (-not (Test-Command "reaper")) {
        throw "reaper is not installed or not on PATH"
    }

    $modelPath = (Resolve-Path -LiteralPath $Model -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
        throw "model is not a readable file: $Model"
    }

    Invoke-Reaper @("--check", "graphify")

    if (Test-PortInUse) {
        throw "port 8080 is already in use"
    }

    if ($Runtime -eq "local") {
        if (-not (Test-Command "llama-server")) {
            throw "local runtime requires llama-server on PATH"
        }
    }
    else {
        if (-not (Test-Command "docker")) {
            throw "docker is not installed or not on PATH"
        }
        & docker info *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "docker daemon is not available"
        }
        & docker image inspect $llamaImage *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "llama.cpp image is missing; run: docker pull $llamaImage"
        }
    }

    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

    if ($Runtime -eq "local") {
        $quotedModel = '"' + $modelPath + '"'
        $startArguments = @{
            FilePath = (Get-Command "llama-server").Source
            ArgumentList = @(
                "--model", $quotedModel,
                "--host", "127.0.0.1",
                "--port", "8080",
                "--ctx-size", "16384",
                "--parallel", "1"
            )
            RedirectStandardOutput = $serverLog
            RedirectStandardError = $serverErrorLog
            PassThru = $true
        }
        $serverProcess = Start-Process @startArguments
    }
    else {
        $dockerArguments = @(
            "run", "--detach", "--rm",
            "--publish", "127.0.0.1:8080:8080",
            "--mount", "type=bind,source=$modelPath,target=/models/model.gguf,readonly",
            $llamaImage,
            "--model", "/models/model.gguf",
            "--host", "0.0.0.0",
            "--port", "8080",
            "--ctx-size", "16384",
            "--parallel", "1"
        )
        $containerId = (& docker @dockerArguments).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $containerId) {
            throw "unable to start the llama.cpp container"
        }
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (Test-LlamaHealth) {
            $ready = $true
            break
        }
        if ($serverProcess) {
            $serverProcess.Refresh()
            if ($serverProcess.HasExited) {
                break
            }
        }
        if ($containerId) {
            $running = & docker inspect --format "{{.State.Running}}" $containerId 2>$null
            if ($LASTEXITCODE -ne 0 -or $running -ne "true") {
                break
            }
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        Show-ServerLog
        throw "llama-server did not become ready within 120 seconds"
    }

    Invoke-Reaper @("--scan", ".")
    Invoke-Reaper @("analyze", ".", "--all", "--server", $serverUrl)
    Invoke-Reaper @("prompt", ".")
    Write-Output "Workflow complete: $(Join-Path $outputDirectory 'refactor-prompt.md')"
}
catch {
    [Console]::Error.WriteLine("Error: $($_.Exception.Message)")
    exit 1
}
finally {
    Stop-ReaperServer
}
