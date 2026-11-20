<#
  Export the finished DOCX to PDF with Microsoft Word.
  - converts the document from Word-2007 compatibility mode to the current layout engine
    (compatibility-mode layout can depend on the default printer driver)
  - exports without tagged-PDF structure (much faster for long documents), with heading bookmarks
  - first exports pages 1-5 as a quick test, then the full document
  Progress: report\export_pdf.log
#>
$ErrorActionPreference = "Stop"
$docx = Join-Path $PSScriptRoot "BigDataSystems_24CI51_SLA_Report.docx"
$pdf  = Join-Path $PSScriptRoot "BigDataSystems_24CI51_SLA_Report.pdf"
$test = Join-Path $env:TEMP "bigdata_report_test_p1-5.pdf"
$log  = Join-Path $PSScriptRoot "export_pdf.log"
$t0 = Get-Date
function L($m) { $s = "{0,6:N0}s  {1}" -f ((Get-Date) - $t0).TotalSeconds, $m; $s; Add-Content -Encoding utf8 $log $s }
Set-Content -Encoding utf8 $log "### $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') export_pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0; $word.ScreenUpdating = $false
try {
    $d = $word.Documents.Open($docx, $false, $false, $false)
    L "opened (compatibility mode $($d.CompatibilityMode))"
    $d.SetCompatibilityMode(15)
    foreach ($toc in $d.TablesOfContents) { $toc.UpdatePageNumbers() }
    L "converted to mode $($d.CompatibilityMode); pages = $($d.ComputeStatistics(2))"
    $d.Save(); L "saved"
    # ExportAsFixedFormat(path, 17=PDF, open=false, 0=print, 3=FromTo, from, to, 0=content, docprops, keepIRM, 1=heading bookmarks, docStructureTags, bitmapMissingFonts, ISO19005)
    $d.ExportAsFixedFormat($test, 17, $false, 0, 3, 1, 5, 0, $true, $true, 1, $false, $true, $false)
    L "test export pages 1-5 OK ($([math]::Round((Get-Item $test).Length / 1KB)) KB)"
    $d.ExportAsFixedFormat($pdf, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1, $false, $true, $false)
    L "FULL PDF exported ($([math]::Round((Get-Item $pdf).Length / 1MB, 1)) MB)"
    $d.Close(0)
} catch { L "ERROR: $($_.Exception.Message)" }
finally { $word.Quit(0); L "Word closed" }
