<#
.SYNOPSIS
  Runs a command in a NEW, real console window and saves a screenshot of that
  window (genuine screen capture via the Win32 PrintWindow API).

.EXAMPLE
  powershell -File common\capture_console.ps1 -Command "docker ps" -OutFile evidence\act1\screenshots\docker_ps.png
#>
param(
    [Parameter(Mandatory)] [string] $Command,
    [Parameter(Mandatory)] [string] $OutFile,
    [int] $Cols = 150,
    [int] $Lines = 45,
    [int] $TimeoutSec = 300,
    [string] $WorkDir = (Get-Location).Path
)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win32Cap {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
[Win32Cap]::SetProcessDPIAware() | Out-Null

$title  = "capture-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$marker = Join-Path $env:TEMP "$title.done"
$inner = @"
`$Host.UI.RawUI.WindowTitle = '$title'
mode con: cols=$Cols lines=$Lines | Out-Null
Set-Location '$WorkDir'
Write-Host ("[" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "]  " + `$env:USERNAME + "@" + `$env:COMPUTERNAME + "  " + (Get-Location).Path) -ForegroundColor DarkGray
Write-Host ('PS> ' + @'
$Command
'@) -ForegroundColor Yellow
$Command
New-Item -ItemType File '$marker' | Out-Null
"@
$enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
# conhost.exe forces a classic console window we can locate by title
$proc = Start-Process conhost.exe -ArgumentList "powershell.exe -NoProfile -NoExit -EncodedCommand $enc" -PassThru

$deadline = (Get-Date).AddSeconds($TimeoutSec)
while (-not (Test-Path $marker) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
Start-Sleep -Milliseconds 1200   # let the console finish painting

$win = Get-Process | Where-Object { $_.MainWindowTitle -eq $title } | Select-Object -First 1
if (-not $win) { Write-Error "Console window '$title' not found"; exit 1 }
$h = $win.MainWindowHandle
$r = New-Object Win32Cap+RECT
[Win32Cap]::GetWindowRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc(); [Win32Cap]::PrintWindow($h, $hdc, 2) | Out-Null; $g.ReleaseHdc($hdc)
New-Item -ItemType Directory -Force (Split-Path $OutFile) | Out-Null
$bmp.Save((Join-Path (Resolve-Path (Split-Path $OutFile)).Path (Split-Path $OutFile -Leaf)), [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Remove-Item $marker -ErrorAction SilentlyContinue
Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.MainWindowTitle -eq $title } | Stop-Process -ErrorAction SilentlyContinue
Write-Output "Captured $OutFile"
