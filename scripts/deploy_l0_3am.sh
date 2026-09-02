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

# Email di riepilogo a fine deploy (OK o FATAL) — indipendente da sessione/PC.
# Tutto passato via env (niente interpolazione shell dentro il sorgente python).
notify() {
    ND_ESITO="$1" ND_DETT="$2" ND_TAIL="$(tail -30 "$LOG")" \
    docker exec -e ND_ESITO -e ND_DETT -e ND_TAIL "$CONTAINER" python3 -c '
import os, html, resend
resend.api_key = os.getenv("RESEND_API_KEY", "")
if not resend.api_key:
    print("RESEND_API_KEY mancante, niente email"); raise SystemExit
esito = os.getenv("ND_ESITO", "?")
dett  = html.escape(os.getenv("ND_DETT", ""))
tail  = html.escape(os.getenv("ND_TAIL", ""))
sender = os.getenv("EMAIL_SENDER", "onboarding@resend.dev")
recip  = os.getenv("EMAIL_RECIPIENT", "andreapavan67@gmail.com")
pre_style = "background:#f5f5f5;padding:12px;font-size:12px;overflow:auto"
resend.Emails.send({
    "from": "ETF Monitor <" + sender + ">",
    "to": [recip],
    "subject": esito + " - Deploy L0 gate regime (notturno)",
    "html": "<h2>" + esito + "</h2><p>" + dett + "</p><pre style=\x22" + pre_style + "\x22>" + tail + "</pre>",
})
print("email inviata")
' 2>&1 || echo "notify(): invio email fallito"
}
fail() { echo "FATAL: $1"; notify "FALLITO" "$1"; exit 1; }

echo ""
echo "========================================================================"
echo "=== DEPLOY L0 (gate regime rilassato) — $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
echo "========================================================================"

cd "$REPO" || fail "repo non trovato"

echo "--- [1/6] sync git ---"
cp etf_monitoraggio.xlsx /tmp/etf_xlsx_bak.xlsx 2>/dev/null || true
git fetch origin main || fail "git fetch fallito"
git reset --hard origin/main
python3 smart_restore.py /tmp/etf_xlsx_bak.xlsx etf_monitoraggio.xlsx || cp /tmp/etf_xlsx_bak.xlsx etf_monitoraggio.xlsx 2>/dev/null || true
echo "HEAD: $(git log --oneline -1)"

echo "--- [2/6] verifica che il codice L0 sia presente ---"
grep -q "l0_regime_allowed" config/etf_families.yaml || fail "YAML senza l0_regime_allowed (push non arrivato?)"
grep -q "_l0_regime_allowed" technical_analysis.py || fail "technical_analysis.py senza la modifica guardata"
test -f shadow_monitor_l0_regime_baseline.py || fail "shadow_monitor_l0_regime_baseline.py mancante"
python3 -c "import ast; [ast.parse(open(f).read(),f) for f in ('technical_analysis.py','monitor.py','alerts.py','database.py','shadow_monitor_l0_regime_baseline.py')]" || fail "syntax error nei file .py"
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
        *) fail "build fallito e nessuna immagine recente — container NON toccato";;
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
    echo "  ultimi log container:"; docker logs "$CONTAINER" --tail 25 2>&1
    fail "health check FALLITO dopo 4 min ($(docker ps --filter name=etf_monitor_system-app --format '{{.Status}}'))"
fi
echo "OK — /api/health risponde"

echo "--- [6/6] verifica runtime L0 + trigger monitor ---"
docker exec "$CONTAINER" python3 -c "
import yaml
gp = yaml.safe_load(open('/app/config/etf_families.yaml'))['global_params']
print('  l0_regime_allowed nel container:', gp.get('l0_regime_allowed'))
from shadow_monitor_l0_regime_baseline import MODEL_NAME
print('  shadow baseline import OK:', MODEL_NAME)
" || fail "import runtime L0 fallito"

curl -s -X POST http://localhost:5001/api/trigger-update
echo ""
echo "=== DEPLOY L0 COMPLETATO OK — $(date '+%H:%M:%S') ==="
echo "  Il monitor sta girando; controllare che STEP 8b2 (Shadow L0-baseline) non dia errore."
echo "  Prossimo: al 1° del mese arriva il primo digest mensile Shadow."
notify "✅ OK" "Deploy L0 completato. Gate regime rilassato (BULL/LATERALE/BEAR), shadow inverso attivo (STEP 8b2), digest mensile schedulato per il 1° del mese. Monitor in esecuzione."
