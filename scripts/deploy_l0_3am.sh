#!/bin/bash
# deploy_l0_3am.sh — deploy NOTTURNO NON SUPERVISIONATO del cambio gate regime L0.
# Gira SULLA VPS via cron alle 03:00 (VPS scarica -> build veloce). Fa solo la parte
# meccanica: il codice e' gia' committato+pushato (rivisto in sessione). Nessuna
# migration (il cambio L0 non aggiunge tabelle). Logga tutto; se l'health check fallisce
# lascia il container com'e' e scrive un errore ben visibile.
#
# Installazione cron (una volta, sulla VPS):
#   (crontab -l 2>/dev/null; echo '0 3 * * * /root/etf_monitor_system/scripts/deploy_l0_3am.sh') | crontab -
# Rimozione dopo l'esecuzione:
#   crontab -l | grep -v deploy_l0_3am | crontab -

set -o pipefail
REPO=/root/etf_monitor_system
LOG=$REPO/data/deploy_l0_3am.log
CONTAINER=etf_monitor_system-app-1
exec >> "$LOG" 2>&1

echo ""
echo "========================================================================"
echo "=== DEPLOY L0 (gate regime rilassato) — $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
echo "========================================================================"

cd "$REPO" || { echo "FATAL: repo non trovato"; exit 1; }

echo "--- [1/6] sync git ---"
cp etf_monitoraggio.xlsx /tmp/etf_xlsx_bak.xlsx 2>/dev/null || true
git fetch origin main || { echo "FATAL: git fetch"; exit 1; }
git reset --hard origin/main
python3 smart_restore.py /tmp/etf_xlsx_bak.xlsx etf_monitoraggio.xlsx || cp /tmp/etf_xlsx_bak.xlsx etf_monitoraggio.xlsx 2>/dev/null || true
echo "HEAD: $(git log --oneline -1)"

echo "--- [2/6] verifica che il codice L0 sia presente ---"
grep -q "l0_regime_allowed" config/etf_families.yaml || { echo "FATAL: YAML senza l0_regime_allowed — push non arrivato?"; exit 1; }
grep -q "_l0_regime_allowed" technical_analysis.py || { echo "FATAL: technical_analysis.py senza la modifica guardata"; exit 1; }
test -f shadow_monitor_l0_regime_baseline.py || { echo "FATAL: shadow_monitor_l0_regime_baseline.py mancante"; exit 1; }
python3 -c "import ast; [ast.parse(open(f).read(),f) for f in ('technical_analysis.py','monitor.py','alerts.py','database.py','shadow_monitor_l0_regime_baseline.py')]" || { echo "FATAL: syntax error"; exit 1; }
echo "OK — codice L0 presente e sintatticamente valido"

echo "--- [3/6] build immagine (timeout 40m) ---"
timeout 2400 docker compose -p etf_monitor_system build app
BUILD_RC=$?
if [ $BUILD_RC -ne 0 ]; then
    echo "WARN: 'docker compose build' rc=$BUILD_RC (timeout o hang). Controllo se l'immagine e' comunque stata creata di recente..."
    RECENT=$(docker images etf_monitor_system-app --format '{{.CreatedSince}}' | head -1)
    echo "  immagine: $RECENT"
    case "$RECENT" in
        *"seconds"*|*"minute"*|"About a minute"*) echo "  -> immagine recente, procedo comunque";;
        *) echo "FATAL: nessuna immagine recente, non ricreo il container"; exit 1;;
    esac
    docker ps -a --filter name=etf_monitor_system-app --format '{{.Names}}' | xargs -r docker kill 2>/dev/null || true
fi

echo "--- [4/6] ricrea container ---"
docker ps -a --filter name=etf_monitor_system-app --format '{{.Names}}' | xargs -r docker rm -f
docker compose -p etf_monitor_system up -d app
sleep 5
docker ps --filter name=etf_monitor_system-app --format '{{.Names}} {{.Status}}'

echo "--- [5/6] health check (max 4 min) ---"
OK=0
for i in $(seq 1 48); do
    if curl -sf http://localhost:5001/api/health > /dev/null 2>&1; then OK=1; break; fi
    sleep 5
done
if [ $OK -ne 1 ]; then
    echo "FATAL: health check FALLITO dopo 4 min. Container: $(docker ps --filter name=etf_monitor_system-app --format '{{.Status}}')"
    echo "  ultimi log container:"; docker logs "$CONTAINER" --tail 25 2>&1
    exit 1
fi
echo "OK — /api/health risponde"

echo "--- [6/6] verifica runtime L0 + trigger monitor ---"
docker exec "$CONTAINER" python3 -c "
import yaml
gp = yaml.safe_load(open('/app/config/etf_families.yaml'))['global_params']
print('  l0_regime_allowed nel container:', gp.get('l0_regime_allowed'))
from shadow_monitor_l0_regime_baseline import MODEL_NAME
print('  shadow baseline import OK:', MODEL_NAME)
" || { echo "FATAL: import runtime L0 fallito"; exit 1; }

curl -s -X POST http://localhost:5001/api/trigger-update
echo ""
echo "=== DEPLOY L0 COMPLETATO OK — $(date '+%H:%M:%S') ==="
echo "  Il monitor sta girando; controllare che STEP 8b2 (Shadow L0-baseline) non dia errore."
echo "  Prossimo: al 1° del mese arriva il primo digest mensile Shadow."
