# 🛡️ SYSTEM LOCKDOWN — Protezione Parametri & Logica
**Data:** 2026-08-06  
**Validazione:** Feature Extraction (80-trade baseline, 60% WR, €7,177 netto)  
**Frozen Until:** 2026-09-06

---

## 🎯 OBIETTIVO

Impedire che parametri e logiche di trading vengano cambiate senza:
1. Feature Extraction revalidation (3-6 mesi di dati nuovi)
2. Backtest minimo di 3 mesi
3. P&L improvement documentato >= €500 (su 10k€/trade)
4. Approvazione scritta da system architect

---

## 🔒 PARAMETRI BLOCCATI (2026-08-06 → 2026-09-06)

### Tier 1: HARD FREEZE (Non cambiare, punto.)

**`adx_entry` — ADX Entry Threshold**
```yaml
# Stato: FROZEN (2026-08-06)
# Motivo: Feature Extraction mostra gap NEGATIVO
#         Perdenti hanno ADX (24.4) > Vincenti (23.8)
#         Alzare la soglia peggiorerebbe le cose
# Approval required: NONE (locked)

equity_sviluppati:
  adx_entry: 22  # ❌ DO NOT CHANGE
mercati_emergenti:
  adx_entry: 22  # ❌ DO NOT CHANGE
# ... (all 14 families)
```

**`rsi_entry_low` / `rsi_entry_high` — RSI Entry Range**
```yaml
# Stato: FROZEN (2026-08-06)
# Motivo: Validato da FE, gap piccolo ma positivo (+2.15)
# Approval required: NONE (locked)

equity_sviluppati:
  rsi_entry_low: 45    # ❌ DO NOT CHANGE
  rsi_entry_high: 58   # ❌ DO NOT CHANGE
# ... (all 14 families)
```

**`ema_dist_max` — EMA20 Distance Max**
```yaml
# Stato: FROZEN (2026-08-06)
# Motivo: Validato da FE, gap marginale ma positivo (+0.29)
# Approval required: NONE (locked)

equity_sviluppati:
  ema_dist_max: 4.0  # ❌ DO NOT CHANGE
# ... (all 14 families)
```

### Tier 2: SOFT FREEZE (Cambio ammesso solo con ragione FORTE)

**`mm200_distance_max` — SMA200 Distance Max**
```yaml
# Stato: APPROVED (2026-08-06)
# Motivo: Feature Extraction solo per questa feature
# Change approval: NO NEW CHANGES until 2026-09-06
# (il parametro stesso è protetto, non modificare i valori)

equity_sviluppati:
  mm200_distance_max: 3.0  # ⚠️ TOUCHING REQUIRES BACKTEST
# ... (all 14 families)
```

---

## 📝 CHANGE LOG INTEGRATO

Ogni change deve essere tracciato nel YAML:

```yaml
# In config/etf_families.yaml (TOP):
metadata:
  version: "2026-08-06-deployment-01"
  frozen_until: "2026-09-06"
  frozen_reason: "Feature Extraction validated, don't change without backtest"
  
  change_log:
    - id: "2026-08-06-001"
      date: "2026-08-06 13:30"
      change: "Added mm200_distance_max filter to all 14 families"
      values_changed:
        - "equity_sviluppati: mm200_distance_max → 3.0%"
        - "mercati_emergenti: mm200_distance_max → 4.0%"
        - "... (11 more families)"
      validation_base: "Feature Extraction (80-trade, 60% WR)"
      expected_impact: "WR +2-5%, P&L +€323-1,323"
      author: "Feature Extraction Pipeline"
      approval: "Data-driven (FE gap -3.38%)"
      status: "ACTIVE"
      revalidation_date: "2026-09-06"
```

---

## 🚨 ENFORCEMENT: Misura 1 — Runtime Version Check

**File:** `technical_analysis.py` (top of class init)

```python
class TechnicalAnalyzer:
    FROZEN_VERSION = "2026-08-06-deployment-01"
    FROZEN_UNTIL = datetime(2026, 9, 6)
    
    FROZEN_PARAMS = {
        'adx_entry': {
            'frozen': True,
            'reason': 'FE gap=-0.55 (perdenti hanno ADX più alto)',
            'value_baseline': 22,
        },
        'rsi_entry_low': {
            'frozen': True,
            'reason': 'FE gap=+2.15 (lieve, validato)',
            'value_baseline': None,  # family-specific
        },
        'rsi_entry_high': {
            'frozen': True,
            'reason': 'FE gap=+2.15 (lieve, validato)',
            'value_baseline': None,
        },
        'ema_dist_max': {
            'frozen': True,
            'reason': 'FE gap=+0.29 (lieve, validato)',
            'value_baseline': None,
        },
    }
    
    def __init__(self, params):
        # Verifica versione
        version = params.get('_version', 'unknown')
        if version != self.FROZEN_VERSION:
            logger.warning(f"⚠️ CONFIG VERSION MISMATCH: {version} vs {self.FROZEN_VERSION}")
        
        # Verifica parametri frozen
        for param_name, freeze_info in self.FROZEN_PARAMS.items():
            if freeze_info['frozen']:
                if param_name in params:
                    current_value = params[param_name]
                    if freeze_info['value_baseline'] is not None:
                        if current_value != freeze_info['value_baseline']:
                            logger.error(f"🚨 FROZEN PARAM MODIFIED: {param_name}={current_value} (baseline {freeze_info['value_baseline']})")
                            logger.error(f"   Reason: {freeze_info['reason']}")
                            raise ValueError(f"Parameter {param_name} is frozen until 2026-09-06")
```

---

## 🚨 ENFORCEMENT: Misura 2 — Pre-Deploy Validation Script

**File:** `scripts/pre_deploy_validation.py`

```python
#!/usr/bin/env python3
"""
Pre-deployment validation: Controlla che solo parametri APPROVATI
siano stati modificati rispetto alla versione baseline del 2026-08-06.
"""

import yaml
from datetime import datetime

APPROVED_CHANGES = {
    'mm200_distance_max': {
        'approved_date': '2026-08-06',
        'reason': 'Feature Extraction gap -3.38%',
        'change_type': 'value_update',  # oppure 'new_param'
    },
}

BLOCKED_PARAMS = {
    'adx_entry': 'FE gap negative — perdenti hanno ADX più alto',
    'rsi_entry_low': 'FE validato, no changes allowed',
    'rsi_entry_high': 'FE validato, no changes allowed',
    'ema_dist_max': 'FE validato, no changes allowed',
}

def validate_yaml_changes(old_yaml_path, new_yaml_path):
    """Valida che il YAML nuovo sia conforme alle regole di freeze."""
    
    with open(old_yaml_path) as f:
        old = yaml.safe_load(f)
    
    with open(new_yaml_path) as f:
        new = yaml.safe_load(f)
    
    diffs = find_parameter_diffs(old, new)
    
    for param, change in diffs.items():
        if param in BLOCKED_PARAMS:
            raise ValueError(f"❌ BLOCKED: {param} cannot be changed\n   Reason: {BLOCKED_PARAMS[param]}")
        
        if param not in APPROVED_CHANGES:
            raise ValueError(f"❌ UNAPPROVED: {param} not in approved changes list\n   To approve: add to APPROVED_CHANGES with date + reason")
    
    print("✅ All changes approved for deployment")
    return True

if __name__ == '__main__':
    import sys
    old = sys.argv[1] if len(sys.argv) > 1 else 'config/etf_families.yaml.backup-2026-08-06'
    new = sys.argv[2] if len(sys.argv) > 2 else 'config/etf_families.yaml'
    
    try:
        validate_yaml_changes(old, new)
    except ValueError as e:
        print(f"❌ Validation FAILED:\n{e}")
        sys.exit(1)
```

**Integrazione nel deploy:**

```bash
# .github/workflows/deploy.yml
- name: Pre-Deploy Validation
  run: python3 scripts/pre_deploy_validation.py config/etf_families.yaml.backup-2026-08-06 config/etf_families.yaml
  # Blocca il push se la validazione fallisce
```

---

## 🚨 ENFORCEMENT: Misura 3 — Parametri "Do Not Touch"

**File:** `config/etf_families.yaml` (ogni famiglia)

```yaml
equity_sviluppati:
  # ⚠️ FROZEN PARAMETERS (2026-08-06 → 2026-09-06)
  # Modifica richiede: Feature Extraction revalidation + 3-month backtest
  
  adx_entry: 22                 # FROZEN: FE gap -0.55
  rsi_entry_low: 45              # FROZEN: FE validato
  rsi_entry_high: 58             # FROZEN: FE validato
  ema_dist_max: 4.0              # FROZEN: FE validato
  
  # ⚠️ APPROVED CHANGE (2026-08-06)
  # Soggetto a monitoraggio settimanale fino al 2026-09-06
  
  mm200_distance_max: 3.0        # APPROVED: FE gap -3.38%
```

---

## 📊 WEEKLY MONITORING — Implemen tazione

**File:** `scripts/weekly_validation.sh`

```bash
#!/bin/bash
# Run every Monday 09:00 CEST
# Cron: 0 9 * * 1 /root/etf_monitor_system/scripts/weekly_validation.sh

REPORT_FILE="/tmp/weekly_validation_$(date +%Y%m%d).txt"

echo "📊 WEEKLY VALIDATION — $(date)" > $REPORT_FILE

# Test 1: Parameter Integrity
echo "✓ Test 1: Parameter Integrity Check" >> $REPORT_FILE
python3 /root/etf_monitor_system/scripts/param_integrity_check.py >> $REPORT_FILE 2>&1 || {
    echo "❌ FAILED: Parameter integrity check" >> $REPORT_FILE
    FAILED=1
}

# Test 2: L0/L1 Distribution Sanity
echo "✓ Test 2: L0/L1 Distribution Sanity" >> $REPORT_FILE
python3 /root/etf_monitor_system/scripts/distribution_check.py >> $REPORT_FILE 2>&1 || {
    echo "❌ FAILED: Distribution sanity check" >> $REPORT_FILE
    FAILED=1
}

# Test 3: Backtest Rolling 30gg
echo "✓ Test 3: Backtest Rolling 30gg" >> $REPORT_FILE
python3 /root/etf_monitor_system/scripts/rolling_backtest_30d.py >> $REPORT_FILE 2>&1 || {
    echo "❌ FAILED: Rolling backtest" >> $REPORT_FILE
    FAILED=1
}

# Send email report
if [ $FAILED -eq 1 ]; then
    mail -s "[ETF Monitor] 🚨 VALIDATION FAILED — $(date +%Y-%m-%d)" \
         andreapavan67@gmail.com < $REPORT_FILE
else
    mail -s "[ETF Monitor] ✅ Weekly Validation PASSED — $(date +%Y-%m-%d)" \
         andreapavan67@gmail.com < $REPORT_FILE
fi
```

---

## 🎯 VALIDATION CHECKLIST — 30-day Window (2026-08-06 → 2026-09-06)

| Settimana | Verifica | Target | Status |
|-----------|----------|--------|--------|
| W1 (08-13) | WR rolling 30gg | 60-65% | ⏳ In Progress |
| W2 (08-20) | P&L netto | +€500+ (10k€) | ⏳ In Progress |
| W3 (08-27) | Param integrity | ZERO changes | ⏳ In Progress |
| W4 (09-03) | Distribution | Within ranges | ⏳ In Progress |
| W5 (09-06) | FINAL CHECK | All criteria | ⏳ Pending |

**If all pass: ✅ DEPLOYMENT CONFIRMED**  
**If any fail: ⏸️ INVESTIGATE + ROLLBACK if needed**

---

## 📋 ROLLBACK PROCEDURE (if needed)

```bash
# If deployment doesn't meet success criteria:

git revert 2deb026  # Revert mm200_distance_max deployment
git push origin main

# VPS:
ssh root@76.13.37.133 "cd /root/etf_monitor_system && git pull origin main && docker restart etf_monitor_system-app-1"

# Verify rollback:
curl http://localhost:5001/api/trigger-update
sleep 120
curl http://localhost:5001/api/check-status
```

**ETA Rollback:** 10 minuti

---

## 📝 APPROVAL MATRIX

For any parameter change after 2026-09-06:

| Change Type | Approvazione Richiesta | Evidence Richiesta | Effort |
|-------------|:---:|:---:|:---:|
| mm200_distance_max | Arch | 3-month backtest + FE | Medium |
| ADX entry | Arch + Data | 6-month backtest + FE | High |
| RSI range | Arch | 3-month backtest + FE | Medium |
| EMA20 distance | Arch | 3-month backtest + FE | Medium |
| New filter | VP Eng + Data | Full FE cycle | Very High |

---

## ✅ CONCLUSION

**System locked 2026-08-06 → 2026-09-06**  
**Revalidation required for any further changes**  
**Weekly monitoring active, quarterly FE recheck**

---

*Lockdown effective: 2026-08-06 13:30 CEST*  
*Baseline: 80-trade FE (60% WR, €7,177 net)*  
*Next review: 2026-09-06 (30-day validation complete)*
