param(
    [int]$Port = 8082
)

$ErrorActionPreference = "Stop"

Write-Host "=== Windows Connectivity Doctor ==="
Write-Host ("Host: {0}" -f $env:COMPUTERNAME)

$profiles = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -ne "Disconnected" }
if ($profiles) {
    Write-Host "Network profile(s):"
    $profiles | ForEach-Object {
        Write-Host ("  - {0} ({1})" -f $_.Name, $_.NetworkCategory)
    }
}

$ips = Get-NetIPConfiguration |
    Where-Object { $_.NetAdapter.Status -eq "Up" -and $_.IPv4Address -and $_.IPv4DefaultGateway } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Select-Object -Unique

if (-not $ips) {
    Write-Host "No active LAN IPv4 detected."
} else {
    Write-Host "Active LAN IPv4:"
    $ips | ForEach-Object { Write-Host ("  - {0}" -f $_) }
}

$local = Test-NetConnection -ComputerName "localhost" -Port $Port -WarningAction SilentlyContinue
Write-Host ("Local localhost:{0} = {1}" -f $Port, $(if ($local.TcpTestSucceeded) { "OK" } else { "FAIL" }))

if ($ips) {
    Write-Host "Client URL candidates:"
    $ips | ForEach-Object {
        Write-Host ("  http://{0}:{1}" -f $_, $Port)
    }
}

$fwRules = Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*8082*" -or $_.DisplayName -like "*Korespondensi*" }

if ($fwRules) {
    Write-Host "Firewall inbound rule hints:"
    $fwRules | Select-Object -ExpandProperty DisplayName | ForEach-Object { Write-Host ("  - {0}" -f $_) }
} else {
    Write-Host "No explicit inbound firewall rule found for 8082."
}

Write-Host "=== End Windows Doctor ==="
