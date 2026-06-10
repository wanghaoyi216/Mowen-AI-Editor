$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host "$($c.LocalAddress):$($c.LocalPort) -> PID $($p.Id) $($p.ProcessName) Started: $($p.StartTime)"
    } else {
        Write-Host "$($c.LocalAddress):$($c.LocalPort) -> PID $($c.OwningProcess) (no process found)"
    }
}
