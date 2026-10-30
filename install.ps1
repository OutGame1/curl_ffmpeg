Write-Host "Installation de Python 3.13..."
winget install --id=Python.Python.3.13 -e -h --accept-package-agreements --accept-source-agreements

Write-Host "Installation de FFmpeg..."
winget install --id=Gyan.FFmpeg -e -h --accept-package-agreements --accept-source-agreements

Write-Host "Création du raccourci de démarrage..."

$AppDir = $PSScriptRoot
$PythonW = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue

if (-not $PythonW) {
    $Python = Get-Command "python.exe" -ErrorAction SilentlyContinue

    if ($Python) {
        $PythonWPath = Join-Path (Split-Path $Python.Source) "pythonw.exe"

        if (Test-Path -LiteralPath $PythonWPath -PathType Leaf) {
            $PythonW = Get-Item -LiteralPath $PythonWPath
        }
    }
}

if (-not $PythonW) {
    Write-Host "Impossible de trouver pythonw.exe. Le raccourci n'a pas été créé." -ForegroundColor Red
}
else {
    $WshShell = New-Object -ComObject WScript.Shell
    $ShortcutPath = Join-Path $AppDir "start.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)

    $Shortcut.TargetPath = $PythonW.Source
    $Shortcut.Arguments = "-m src.app"
    $Shortcut.WorkingDirectory = $AppDir
    $Shortcut.Description = "Démarrer curl_ffmpeg sans terminal"
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()

    Write-Host "Raccourci créé : $ShortcutPath" -ForegroundColor Green
}

pause