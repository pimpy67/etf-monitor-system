# setup_claude_memory_junction.ps1 (2026-09-02)
# Collega la memoria automatica di Claude Code (per-progetto, path-dipendente) alla
# cartella memory/claude-auto/ di questo repo, cosi' la memoria viaggia con `git pull`
# invece di restare locale a un solo PC.
#
# Usare su OGNI PC dove si lavora al progetto, UNA volta, dopo il primo `git clone`/`pull`.
# NON serve amministratore (usa una directory junction, non un symlink).
#
# Uso:  powershell -File scripts\setup_claude_memory_junction.ps1

$ErrorActionPreference = 'Stop'

# Percorso del repo = cartella che contiene questo script (../)
$repoRoot = Split-Path -Parent $PSScriptRoot
$target   = Join-Path $repoRoot 'memory\claude-auto'

if (-not (Test-Path $target)) {
    Write-Error "Non trovo $target - fai prima 'git pull'."
    exit 1
}

# Claude Code deriva il nome della cartella memoria dal path assoluto del progetto:
#   <slug> = path con [\/:] -> '-' , e i separatori raddoppiati ('--' per '\')
$slug = ($repoRoot -replace '[\\/:]', '-')
$claudeMem = Join-Path $env:USERPROFILE ".claude\projects\$slug\memory"
$claudeProj = Split-Path -Parent $claudeMem

Write-Host "Repo:        $repoRoot"
Write-Host "Target:      $target"
Write-Host "Claude mem:  $claudeMem"

if (-not (Test-Path $claudeProj)) { New-Item -ItemType Directory -Path $claudeProj -Force | Out-Null }

if (Test-Path $claudeMem) {
    $item = Get-Item $claudeMem -Force
    if ($item.LinkType -eq 'Junction') {
        Write-Host "Junction gia' presente. Nulla da fare."
        exit 0
    }
    # Cartella reale esistente: salva eventuali note locali dentro il repo, poi sostituisci
    Get-ChildItem $claudeMem -Filter *.md -ErrorAction SilentlyContinue | ForEach-Object {
        $dest = Join-Path $target $_.Name
        if (-not (Test-Path $dest)) { Copy-Item $_.FullName $dest; Write-Host "  importato $($_.Name)" }
    }
    Rename-Item $claudeMem "memory.local.bak"
}

New-Item -ItemType Junction -Path $claudeMem -Target $target | Out-Null
if (Test-Path (Join-Path $claudeMem 'MEMORY.md')) {
    Write-Host "OK - junction creata. La memoria di Claude ora e' in memory/claude-auto/ (git)."
    $bak = Join-Path $claudeProj 'memory.local.bak'
    if (Test-Path $bak) { Remove-Item -Recurse -Force $bak }
} else {
    Write-Error "Junction creata ma MEMORY.md non leggibile - controlla a mano."
}
