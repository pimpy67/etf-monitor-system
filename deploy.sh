#!/bin/bash
# deploy.sh — pubblica su GitHub e aggiorna il container ETF sul VPS.
# Uso: ./deploy.sh
# Il DB PostgreSQL è in un volume Docker — non viene mai toccato.
# L'Excel etf_monitoraggio.xlsx viene salvato prima del reset e ripristinato dopo.

set -e

VPS="root@76.13.37.133"
VPS_REPO="/root/etf_monitor_system"
SSH_KEY="$HOME/.ssh/id_ed25519_vps"

# 1. Push su GitHub (solo se ci sono modifiche non ancora pushate)
echo "=== [1/4] Push GitHub ==="
if git diff --quiet && git diff --cached --quiet; then
    echo "Nessuna modifica locale da committare."
else
    git add -A
    git commit -m "Deploy $(date '+%Y-%m-%d %H:%M')"
fi
git push origin main

# 2. VPS: salva Excel (modificato dal monitor), poi git reset --hard
echo ""
echo "=== [2/4] Sync VPS con GitHub ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    cp etf_monitoraggio.xlsx /tmp/etf_monitoraggio_backup.xlsx 2>/dev/null || true
    git fetch origin main
    git reset --hard origin/main
    cp /tmp/etf_monitoraggio_backup.xlsx etf_monitoraggio.xlsx 2>/dev/null || true
    echo 'Excel ripristinato post-reset.'
"

# 3. Rebuild immagine Docker
echo ""
echo "=== [3/4] Build immagine Docker ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    docker compose -p etf_monitor_system build app
"

# 4. Ricrea container
echo ""
echo "=== [4/4] Deploy container ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    docker compose -p etf_monitor_system up -d --force-recreate app
    echo 'Container aggiornato.'
"

echo ""
echo "Deploy completato. Dashboard: https://etf.andreapavan.tech"
echo "Per trigger manuale monitor:"
echo "  ssh -i $SSH_KEY $VPS 'curl -s -X POST http://localhost:5001/api/trigger-update'"
