const fs = require('fs');
const d = JSON.parse(fs.readFileSync('./dashboard_data_debug.json', 'utf8'));

const conds = ['allineamento_ok','persistenza_ok','rsi_ok','distance_ok','adx_ok','macd_ok','space_residuo_ok'];
const fails = {};
conds.forEach(c => fails[c] = 0);
let total = 0;
let buyCountDist = {};
let nullOhlc = 0;
const all = [...(d.levels['2']||[]), ...(d.levels['3']||[])];

for (const item of all) {
  const c = item.conditions;
  if (!c || c.allineamento_ok === undefined) continue;
  total++;
  conds.forEach(k => { if (!c[k]) fails[k]++; });
  const bc = item.buy_count !== undefined ? item.buy_count : 'NA';
  buyCountDist[bc] = (buyCountDist[bc]||0) + 1;
  if (c.atr_normalized === null || c.atr_normalized === undefined) nullOhlc++;
}

console.log('summary:', JSON.stringify(d.summary));
console.log('Totale ETF analizzati (con conditions):', total);
console.log('ETF con atr_normalized NULL (OHLC mancante):', nullOhlc, '/', total);
console.log('\n--- Percentuale di fallimento per condizione ---');
conds.forEach(k => {
  console.log(k.padEnd(20), fails[k], '/', total, '=', (100*fails[k]/total).toFixed(1)+'%');
});
console.log('\n--- Distribuzione buy_count (su 7) ---');
Object.keys(buyCountDist).sort().forEach(k => console.log('buy_count='+k, ':', buyCountDist[k]));

const sorted = all.filter(i => i.conditions && i.conditions.allineamento_ok !== undefined)
  .sort((a,b) => (b.buy_count||0) - (a.buy_count||0)).slice(0, 15);
console.log('\n--- Top 15 ETF più vicini a L1 ---');
sorted.forEach(i => {
  const c = i.conditions;
  const failed = conds.filter(k => !c[k]);
  console.log(i.ticker, i.etf_type, 'buy_count='+i.buy_count, 'regime='+c.regime, 'atr_norm='+c.atr_normalized, 'falliti:', failed.join(','));
});
