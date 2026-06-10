Write-Host "=== Python processes ==="
Get-Process python -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, StartTime, Path -AutoSize

Write-Host "`n=== Port 8000 listeners ==="
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    Write-Host "LocalAddress: $($c.LocalAddress):$($c.LocalPort) OwningProcess: $($c.OwningProcess)"
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host "  -> PID: $($p.Id) Name: $($p.ProcessName) Started: $($p.StartTime) Path: $($p.Path)"
    } else {
        Write-Host "  -> (Get-Process cannot find PID $($c.OwningProcess))"
    }
}

Write-Host "`n=== WMI query for port 8000 ==="
try {
    $wmi = Get-CimInstance -ClassName Win32_Process -Filter "Name like '%python%' or Name = 'uvicorn.exe'" -ErrorAction SilentlyContinue
    $wmi | Format-Table ProcessId, Name, CommandLine -AutoSize | Out-String -Width 200
} catch {
    Write-Host "WMI error: $_"
}
