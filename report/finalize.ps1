<#
  Update the table of contents, list of figures and list of tables with Microsoft Word,
  then export the PDF. Run after build_report.py:
      powershell -ExecutionPolicy Bypass -File report\finalize.ps1
  Progress is written to report\finalize.log.
#>
$ErrorActionPreference = "Stop"
$docx = Join-Path $PSScriptRoot "BigDataSystems_24CI51_SLA_Report.docx"
$pdf  = Join-Path $PSScriptRoot "BigDataSystems_24CI51_SLA_Report.pdf"
$log  = Join-Path $PSScriptRoot "finalize.log"
$t0 = Get-Date
function L($m) { $s = "{0,6:N0}s  {1}" -f ((Get-Date) - $t0).TotalSeconds, $m; $s; Add-Content -Encoding utf8 $log $s }
Set-Content -Encoding utf8 $log "### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') finalize"
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0; $word.ScreenUpdating = $false
try {
    L "opening document"
    $d = $word.Documents.Open($docx, $false, $false, $false)
    L "opened; updating $($d.TablesOfContents.Count) TOC fields"
    foreach ($toc in $d.TablesOfContents) { $toc.Update(); L "  TOC updated" }
    foreach ($toc in $d.TablesOfContents) { $toc.UpdatePageNumbers() }
    L "page numbers refreshed"
    $pages = $d.ComputeStatistics(2)
    L "pages = $pages; saving"
    $d.Save()
    L "exporting PDF"
    $d.ExportAsFixedFormat($pdf, 17, $false, 0)
    L "PDF exported ($([math]::Round((Get-Item $pdf).Length / 1MB, 1)) MB)"
    $d.Close(0)
} finally { $word.Quit(0); L "Word closed" }
