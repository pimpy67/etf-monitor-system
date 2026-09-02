---
name: vps-tooling-notes
description: "Operational workarounds discovered 2026-08-27 — docker logs hangs on fund-monitor-app-1 (read the raw json log file instead), and how to read local .xls files via PowerShell Excel COM when the Read tool can't"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3318254f-a574-4958-aee9-2fddf39954f3
  modified: 2026-08-27T15:15:38.815Z
---

## `docker logs` can hang indefinitely on this VPS — read the raw log file instead

Found on `fund-monitor-app-1` (76.13.37.133): `docker logs fund-monitor-app-1 --tail=N`
hung with zero output even under a 15s `timeout` wrapper, for a log file only ~97KB —
not a size/volume problem. Root cause not diagnosed (didn't dig into the docker daemon
itself — SSH connectivity and `docker ps`/`docker inspect` on the same host worked fine in
parallel, so it's specific to the `logs` subcommand or that container's logging state, not
the whole daemon).

**Workaround that works reliably**: bypass the `docker logs` CLI entirely and read the
JSON log file directly:
```bash
ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133 \
  "docker inspect <container> --format '{{.LogPath}}' | xargs tail -c 3000"
```
Each line is a JSON object (`{"log":"...","stream":"stdout|stderr","time":"..."}`) — grep
with `-a` (treat as text) for keywords like `Analisi|Completato|ERROR|Errore|Traceback`
works fine on this raw format. Hasn't been seen on `etf_monitor_system-app-1` (docker logs
worked normally there in the same session) — may be container-specific, not host-wide.
Try `docker logs` first (it's simpler when it works); fall back to this if it hangs rather
than retrying the same command.

## Reading a local `.xls`/binary spreadsheet when the Read tool refuses it

The Read tool errors on binary `.xls` files ("cannot read binary files"). No local
`python`/`pandas`/`openpyxl` available in this environment (checked — only a Windows Store
stub alias exists, `python3`/`python` are not real interpreters here). Excel itself IS
installed locally and COM-automatable via PowerShell — this worked cleanly:

```powershell
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open("C:\path\to\file.xls")
$ws = $wb.Sheets.Item(1)
$usedRange = $ws.UsedRange
$rows = $usedRange.Rows.Count
$cols = $usedRange.Columns.Count
for ($r = 1; $r -le $rows; $r++) {
    $line = ""
    for ($c = 1; $c -le $cols; $c++) { $line += "$($ws.Cells.Item($r,$c).Text)`t" }
    Write-Output $line
}
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($ws) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wb) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
```
Uses `.Text` (formatted display value, e.g. `20/04/2026`, `533,38`) rather than `.Value2` —
easier to eyeball for reconciliation work, but remember Italian locale formatting
(comma decimal separator) when parsing programmatically later. Always release the COM
objects and `$excel.Quit()` — an orphaned Excel.exe process is easy to leave running
otherwise. Used successfully in [[fund_monitor_portfolio_reconciliation_2026_08_27]] to
read a Directa order export (`ElencoOrdiniPic.xls`).
