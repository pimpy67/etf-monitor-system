---
name: deployment_checklist
description: "Deploy procedures, checklist, and post-deploy verification steps"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

## 🚀 DEPLOYMENT CHECKLIST

### Pre-Deploy (Prima di fare git commit)
- [ ] Testato localmente il cambio (se possibile)
- [ ] Verificato che il file è stato letto (grep, jq, cat)
- [ ] Niente debug log dimenticato
- [ ] Parametri rispecchiano CLAUDE.md
- [ ] Aggiornata CURRENT_STATUS.md se è change importante

### Deploy Script (./deploy.sh)
1. `git add -A` + `git commit` + `git push`
2. SSH VPS: `git fetch && git reset --hard origin/main`
3. SSH VPS: `docker compose -p etf_monitor_system build app`
4. SSH VPS: `docker compose -p etf_monitor_system up -d --force-recreate app`
5. Trigger monitor manuale: `curl -X POST http://localhost:5001/api/trigger-update`
6. Sincronizza Excel locale dal VPS

### Post-Deploy Verification (Subito dopo)
- [ ] Container avviato: `docker ps | grep etf_monitor_system-app-1`
- [ ] Log pulito (no errors): `docker logs etf_monitor_system-app-1 | tail -20`
- [ ] Monitor risponde: `curl -s http://localhost:5001/api/health | jq`
- [ ] Dashboard carica: https://etf.andreapavan.tech/

### Post-Monitor Verification (5-10 min dopo)
- [ ] dashboard_data.json aggiornato: `ls -l /root/etf_monitor_system/data/dashboard_data.json`
- [ ] L0/L1/L2/L3 counts ragionevoli
- [ ] Email inviata (check inbox)
- [ ] Niente errori: `docker logs etf_monitor_system-app-1 | grep -i error`

### CRITICAL — Docker Dopo docker cp
Se hai copiato file .py nel container:
```bash
docker restart etf_monitor_system-app-1  # OBBLIGATORIO
```
Motivo: Python non ricarica moduli live, il vecchio codice rimane in memoria

### Rollback (Se qualcosa è rotto)
```bash
# Ultimo commit funzionante
git log --oneline -5
git revert <commit-hash>
git push
./deploy.sh
```

### Common Issues & Fixes

| Problema | Soluzione |
|----------|-----------|
| Monitor non si avvia | `docker logs etf_monitor_system-app-1` — check syntax errors |
| dashboard_data.json non aggiornato | Verifica bind mount: `docker inspect etf_monitor_system-app-1 \| grep Mounts` |
| Email non arrivano | Check RESEND_API_KEY in .env, email recipient giusto |
| L1 count non cambia | Parametri non letti? Verify: `docker exec etf_monitor_system-app-1 cat /app/config/etf_families.yaml \| grep ema20_slope_min` |

### Performance Notes
- **Prima build**: ~14 minuti (pip install)
- **Rebuild**: ~30 sec (if only .py changes)
- **Monitor runtime**: ~5-10 minuti (240 ETF)

### Key Deployment Commits (v2.0)
- `6145701` — Add ema20_slope_min YAML
- `1a5a5e6` — Parametrize STRATO 3
- `192882b` — Stringent slopes (1.0% equity)
