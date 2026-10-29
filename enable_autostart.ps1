param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Aurum Demo Autopilot.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Write-Host 'AURUM-Autostart entfernt. Ein laufender Dienst wird dadurch nicht beendet.'
} else {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $env:ComSpec
    $shortcut.Arguments = '/c ""' + (Join-Path $PSScriptRoot 'start.bat') + '""'
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = 'AURUM-Demoautopilot nach Windows-Anmeldung starten'
    $shortcut.Save()
    Write-Host 'AURUM startet kuenftig nach deiner Windows-Anmeldung aus diesem Ordner.'
    Write-Host 'Der gespeicherte Stoppzustand wird respektiert. Ordner danach nicht verschieben.'
}
