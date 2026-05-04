# Phase 11: Docker Stats Monitoring Helper
# =========================================
# Purpose: Real-time Qdrant resource monitoring with alerting
# Usage: .\monitor_qdrant.ps1 -ThresholdGB 3.2

param(
    [float]$ThresholdGB = 3.2,
    [float]$CPUThreshold = 80,
    [int]$IntervalSeconds = 5
)

Write-Output "Qdrant Monitoring Started"
Write-Output "RAM Threshold: $ThresholdGB GB"
Write-Output "CPU Threshold: $CPUThreshold %"
Write-Output "Interval: $IntervalSeconds seconds"
Write-Output "Press Ctrl+C to stop`n"

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
            # parts: 0:ID, 1:NAME, 2:CPU%, 3:MEM_USAGE, 4:/, 5:LIMIT, 6:MEM%, ...
            
            $cpuPercent = [float]($parts[2] -replace '%', '')
            $memStr = $parts[3]
            
            $memUsage = 0
            if ($memStr -match '(\d+\.?\d*)([GM])i?B' ) {
                $memUsage = [float]$Matches[1]
                if ($Matches[2] -eq 'M') { $memUsage /= 1024 }  # Convert MB to GB
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
                Write-Output "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB"
            } elseif ($memUsage -gt ($ThresholdGB * 0.8)) {
                $ramStatus = "⚠ WARNING"
                Write-Output "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB"
            } else {
                Write-Output "$timestamp | RAM: $([Math]::Round($memUsage, 2)) GB $ramStatus | CPU: $([Math]::Round($cpuPercent, 1))% | Peak RAM: $([Math]::Round($peakRAMUsed, 2)) GB"
            }
        }
        else {
            Write-Output "$(Get-Date -Format 'HH:mm:ss') | Qdrant not running"
        }

        Start-Sleep -Seconds $IntervalSeconds
    }
    catch {
        Write-Output "Error running docker stats: $_"
        Start-Sleep -Seconds $IntervalSeconds
    }
}

