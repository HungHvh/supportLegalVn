# Phase 11: Docker Stats Monitoring Helper
# =========================================
# Purpose: Real-time Qdrant resource monitoring with alerting
# Usage: .\monitor_qdrant.ps1 -ThresholdGB 3.2

param(
    [float]$ThresholdGB = 3.2,
    [float]$CPUThreshold = 80,
    [int]$IntervalSeconds = 5
)

Write-Host "Qdrant Monitoring Started" -ForegroundColor Green
Write-Host "RAM Threshold: $ThresholdGB GB" -ForegroundColor Yellow
Write-Host "CPU Threshold: $CPUThreshold %" -ForegroundColor Yellow
Write-Host "Interval: $IntervalSeconds seconds" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Cyan

$peakRAMUsed = 0
$peakCPUUsed = 0

while ($true) {
    try {
        # Run docker stats and parse Qdrant line
        $stats = docker stats --no-stream=true 2>$null | Select-String "qdrant"

        if ($stats) {
            # Parse the output
            $parts = $stats -split '\s+' | Where-Object { $_.Length -gt 0 }

            # Typical format: CONTAINER ID | NAME | CPU % | MEM USAGE / LIMIT | MEM % | NET I/O | BLOCK I/O | PIDS
            # Find the CPU and MEM values
            $cpuPercent = 0
            $memUsage = 0

            for ($i = 0; $i -lt $parts.Count; $i++) {
                if ($parts[$i] -match '^\d+\.\d+%$') {
                    $cpuPercent = [float]($parts[$i] -replace '%', '')
                    break
                }
            }

            for ($i = 0; $i -lt $parts.Count; $i++) {
                if ($parts[$i] -match '^\d+\.?\d*[GM]B$') {
                    $memStr = $parts[$i]
                    if ($memStr -match '(\d+\.?\d*)(G?)' ) {
                        $memUsage = [float]$Matches[1]
                        if ($Matches[2] -eq 'M') { $memUsage /= 1024 }  # Convert MB to GB
                    }
                    break
                }
            }

            $timestamp = Get-Date -Format "HH:mm:ss"

            # Track peaks
            if ($memUsage -gt $peakRAMUsed) { $peakRAMUsed = $memUsage }
            if ($cpuPercent -gt $peakCPUUsed) { $peakCPUUsed = $cpuPercent }

            # Display current status
            $ramStatus = "OK"
            $cpuStatus = "OK"

            if ($memUsage -gt $ThresholdGB) {
                $ramStatus = "⚠ ALERT"
                Write-Host "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB" -ForegroundColor Red
            } elseif ($memUsage -gt ($ThresholdGB * 0.8)) {
                $ramStatus = "⚠ WARNING"
                Write-Host "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB" -ForegroundColor Yellow
            } else {
                Write-Host "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB" -ForegroundColor Green
            }
        }
        else {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') | Qdrant not running" -ForegroundColor Gray
        }

        Start-Sleep -Seconds $IntervalSeconds
    }
    catch {
        Write-Host "Error running docker stats: $_" -ForegroundColor Red
        Start-Sleep -Seconds $IntervalSeconds
    }
}

