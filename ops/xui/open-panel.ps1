param(
    [Parameter(Mandatory = $true)]
    [string] $ServerHost,

    [string] $SshUser = "mirage",
    [string] $KeyPath = "$HOME\.ssh\mirage_ed25519",
    [string] $RemoteProject = "/home/mirage/projects/Mirage",
    [int] $LocalPort = 2096,
    [switch] $NoBrowser
)

$ErrorActionPreference = "Stop"

$remoteCommand = "cd $RemoteProject && sudo docker compose -f ops/xui/compose.yml run --rm -T xui-ops access-info --local-port $LocalPort --ssh-host $ServerHost --ssh-user $SshUser --json"
$raw = & ssh -i $KeyPath "$SshUser@$ServerHost" $remoteCommand 2>&1

if ($LASTEXITCODE -ne 0) {
    $raw | ForEach-Object { Write-Host $_ }
    throw "Не удалось получить access-info с VPS."
}

$text = ($raw -join "`n")
$start = $text.IndexOf("{")
$end = $text.LastIndexOf("}")
if ($start -lt 0 -or $end -lt $start) {
    $raw | ForEach-Object { Write-Host $_ }
    throw "Ответ access-info не содержит JSON."
}

$info = $text.Substring($start, $end - $start + 1) | ConvertFrom-Json
$portBusy = $false
try {
    $portBusy = [bool](Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue)
} catch {
    $portBusy = $false
}

if (-not $portBusy) {
    $forward = "${LocalPort}:127.0.0.1:$($info.panel_port)"
    $sshCommand = "ssh -i `"$KeyPath`" -N -L $forward $SshUser@$ServerHost"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $sshCommand)
    Start-Sleep -Seconds 3
} else {
    Write-Host "Локальный порт $LocalPort уже слушает. Использую существующий туннель."
}

Write-Host ""
Write-Host "Кабинет 3x-ui:"
Write-Host $info.local_panel_url
Write-Host ""
Write-Host "Не отправляй этот URL и web path в чат или git."

if (-not $NoBrowser) {
    Start-Process $info.local_panel_url
}
