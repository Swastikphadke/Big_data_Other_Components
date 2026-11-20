<#
.SYNOPSIS  Genuine screenshot of a locally running web UI via headless Microsoft Edge.
.EXAMPLE   & common\capture_web.ps1 -Url http://localhost:8080/ -OutFile evidence\act2\screenshots\ui.png
#>
param(
    [Parameter(Mandatory)] [string] $Url,
    [Parameter(Mandatory)] [string] $OutFile,
    [int] $Width = 1500, [int] $Height = 1000, [int] $WaitMs = 15000
)
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$prof = Join-Path $env:TEMP "bd-edge-capture-profile"
New-Item -ItemType Directory -Force (Split-Path $OutFile) | Out-Null
$abs = Join-Path (Resolve-Path (Split-Path $OutFile)).Path (Split-Path $OutFile -Leaf)
$p = Start-Process -FilePath $edge -PassThru -Wait -ArgumentList @(
    "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=`"$prof`"",
    "--hide-scrollbars", "--window-size=$Width,$Height", "--virtual-time-budget=$WaitMs",
    "--screenshot=`"$abs`"", $Url)
if (Test-Path $abs) { "Captured $OutFile" } else { Write-Error "capture failed for $Url" }
