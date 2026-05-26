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

# 2. VPS: salva Excel (il monitor lo modifica in-place), poi git reset --hard, poi smart-restore
#    smart_restore.py preserva solo il Livello (colonna 1) dal backup VPS, lasciando passare
#    i nuovi ticker dalla versione git — così le correzioni dei ticker arrivano sul VPS.
echo ""
echo "=== [2/5] Sync VPS con GitHub ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    cp etf_monitoraggio.xlsx /tmp/etf_monitoraggio_backup.xlsx 2>/dev/null || true
    git fetch origin main
    git reset --hard origin/main
    pip3 install openpyxl --break-system-packages -q 2>/dev/null || true
    python3 smart_restore.py /tmp/etf_monitoraggio_backup.xlsx etf_monitoraggio.xlsx || \
        cp /tmp/etf_monitoraggio_backup.xlsx etf_monitoraggio.xlsx 2>/dev/null || true
    echo 'VPS allineato, Livelli ripristinati da backup.'
"

# 3. Rebuild immagine Docker
echo ""
echo "=== [3/5] Build immagine Docker ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    docker compose -p etf_monitor_system build app
"

# 4. Ricrea container
echo ""
echo "=== [4/5] Deploy container ==="
ssh -i "$SSH_KEY" "$VPS" "
    cd $VPS_REPO
    # Rimuove tutti i container app (anche stale con hash nel nome) prima di ripartire
    docker ps -a --filter name=etf_monitor_system-app --format '{{.Names}}' | xargs -r docker rm -f
    docker compose -p etf_monitor_system up -d app
    echo 'Container aggiornato.'
"

# 5. Trigger monitor (aspetta che Flask sia pronto)
echo ""
echo "=== [5/5] Trigger monitor (aggiorna dashboard_data.json) ==="
ssh -i "$SSH_KEY" "$VPS" "until curl -sf http://localhost:5001/api/health > /dev/null 2>&1; do sleep 2; done && curl -s -X POST http://localhost:5001/api/trigger-update"

echo ""
echo "Deploy completato. Dashboard: https://etf.andreapavan.tech"
echo "Il monitor sta girando in background (~5-10 min). Poi ricarica la dashboard."
