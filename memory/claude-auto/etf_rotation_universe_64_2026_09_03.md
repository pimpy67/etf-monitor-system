---
name: etf-rotation-universe-64-2026-09-03
description: "The 64-ETF curated universe resolved from the Directa PAC list (2026-09-03) — all .MI Milan EUR, yfinance-verified. Kept in case a few are added to normal L0-L3 monitoring; the PAC-rotation idea it was built for is CLOSED (backtest failed)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 09a37320-8783-4b11-9516-618e20ac9073
  modified: 2026-09-03T12:30:31.153Z
---

Built for the DCA-rotation "PAC level" idea (2026-09-03) — **that idea is CLOSED**, the
backtest failed in every variant (see [[etf-l1-gate-widening-analysis-2026-09-01]]). This
list is kept only because a subset (World sectors, gold miners, momentum/quality factors)
might be worth adding to the NORMAL L0-L3 monitoring universe for more L1/L0 entry chances —
a separate, low-priority, optional decision.

Directa PAC universe = 650 ETFs; system monitors 236; overlap 165. These 64 are the
curated "trend-eligible" subset (broad + MSCI-World sectors + factors + country + gold
miners + commodity), all resolved to `.MI` (Milan, EUR), yfinance-fetchable, ~2yr+ history
(older ones — XMWO from 2008, CSNDX 2010, XDWH 2016, FLXI 2019 — have full history; newest
thematics 2021-22). Only `XDWT.MI` (IE00BM67HT60) was already in the system.

`ISIN | ticker.MI | categoria`:

```
LU0274208692 XMWO.MI   broad_world       Xtrackers MSCI World Swap
IE00BJ0KDQ92 XDWD.MI   broad_world       Xtrackers MSCI World 1C
IE00BJ0KDR00 XD9U.MI   broad_us          Xtrackers MSCI USA 1C
LU0274210672 XMUS.MI   broad_us          Xtrackers MSCI USA Swap
LU0274209237 XMEU.MI   broad_europe      Xtrackers MSCI Europe
LU0274209740 XMJP.MI   broad_japan       Xtrackers MSCI Japan
LU0292107645 XMEM.MI   broad_em          Xtrackers MSCI EM Swap
IE000BI8OT95 MWRD.MI   broad_world       Amundi MSCI World
IE00B53SZB19 CSNDX.MI  broad_us_tech     iShares Nasdaq 100
LU1681042864 CU2.MI    broad_us          Amundi MSCI USA
IE00BM67HK77 XDWH.MI   sector_health     Xtrackers MSCI World Health Care
IE00BM67HL84 XDWF.MI   sector_financials Xtrackers MSCI World Financials
IE00BM67HT60 XDWT.MI   sector_it         Xtrackers MSCI World IT   [GIA' NEL SISTEMA come XDWT.DE]
IE00BM67HV82 XDWI.MI   sector_industrials Xtrackers MSCI World Industrials
IE00BM67HS53 XDWM.MI   sector_materials  Xtrackers MSCI World Materials
IE00BM67HN09 XDWS.MI   sector_staples    Xtrackers MSCI World Consumer Staples
IE00BM67HP23 XDWC.MI   sector_discretionary Xtrackers MSCI World Consumer Disc
IE00BM67HQ30 XDWU.MI   sector_utilities  Xtrackers MSCI World Utilities
IE00BM67HM91 XDW0.MI   sector_energy     Xtrackers MSCI World Energy
IE00BM67HR47 XWTS.MI   sector_telecom    Xtrackers MSCI World Telecom
IE00BL25JL35 XDEQ.MI   factor_quality    Xtrackers MSCI World Quality
IE00BL25JM42 XDEV.MI   factor_value      Xtrackers MSCI World Value
IE00BL25JP72 XDEM.MI   factor_momentum   Xtrackers MSCI World Momentum
IE00BL25JN58 XDEB.MI   factor_minvol     Xtrackers MSCI World Min Vol
IE00BP3QZ601 IWQU.MI   factor_quality    iShares Edge MSCI World Quality
IE00BP3QZ825 IWMO.MI   factor_momentum   iShares Edge MSCI World Momentum
IE00BP3QZB59 IWVL.MI   factor_value      iShares Edge MSCI World Value
IE00B6SPMN59 MVUS.MI   factor_minvol     iShares Edge S&P500 Min Vol
IE00B86MWN23 MVEU.MI   factor_minvol     iShares Edge MSCI Europe Min Vol
IE00BHZRQZ17 FLXI.MI   country_india     Franklin FTSE India
IE00BHZRR030 FLXK.MI   country_korea     Franklin FTSE Korea
IE00BHZRQY00 FLXB.MI   country_brazil    Franklin FTSE Brazil
IE00BHZRR147 FLXC.MI   country_china     Franklin FTSE China
IE00BF2B0K52 FLXE.MI   country_em        Franklin Emerging Markets
IE000CM02H85 FLXT.MI   country_taiwan    Franklin FTSE Taiwan
LU0292109344 XMBR.MI   country_brazil    Xtrackers MSCI Brazil
LU0476289466 XMEX.MI   country_mexico    Xtrackers MSCI Mexico
LU0476289540 XCAN.MI   country_canada    Xtrackers MSCI Canada
IE00B5377D42 SAUS.MI   country_australia iShares MSCI Australia
IE00B52XQP83 SRSA.MI   country_southafrica iShares MSCI South Africa
IE00BK5BCD43 AIAI.MI   thematic_ai       L&G Artificial Intelligence
IE00BDVPNG13 WTAI.MI   thematic_ai       WisdomTree Artificial Intelligence
IE00BMW3QX54 ROBO.MI   thematic_robotics L&G ROBO Global Robotics
IE00BYZK4552 RBOT.MI   thematic_robotics iShares Automation & Robotics
IE00BMC38736 SMH.MI    thematic_semis    VanEck Semiconductor
IE00BK5BCH80 RENW.MI   thematic_cleanenergy L&G Clean Energy
IE000YYE6WK5 DFNS.MI   thematic_defense  VanEck Defense
IE00BLPK3577 WCBR.MI   thematic_cyber    WisdomTree Cybersecurity
IE00BG0J4C88 LOCK.MI   thematic_cyber    iShares Digital Security
IE00BYZK4776 HEAL.MI   thematic_health_innov iShares Healthcare Innovation
IE00BF0H7608 BIOT.MI   thematic_pharma   L&G Pharma Breakthrough
IE000O8KMPM1 WDNA.MI   thematic_biotech  WisdomTree BioRevolution
IE00BK5BC891 GLUG.MI   thematic_water    L&G Clean Water
IE00BMDKNW35 DAPP.MI   thematic_crypto   VanEck Crypto & Blockchain
IE000940RNE6 WBLK.MI   thematic_blockchain WisdomTree Blockchain
IE00BQQP9F84 GDX.MI    gold_miners       VanEck Gold Miners
IE00BQQP9G91 GDXJ.MI   gold_miners_junior VanEck Junior Gold Miners
IE00B3CNHG25 AUCO.MI   gold_miners       L&G Gold Mining
JE00BN2CJ301 WGLD.MI   gold_physical     WisdomTree Core Physical Gold
JE00B1VS2W53 PHPT.MI   metals_platinum   WisdomTree Physical Platinum
IE00BDFBTQ78 GDIG.MI   metals_mining     VanEck Global Mining
IE0002PG6CA6 REMX.MI   metals_rareearth  VanEck Rare Earth & Strategic Metals
IE00BKY4W127 PCOM.MI   commodity_broad   WisdomTree Broad Commodities
LU0292106167 XDBC.MI   commodity_broad   Xtrackers Commodity ex-Agri
IE00BYMLZY74 WCOA.MI   commodity_broad   WisdomTree Enhanced Commodity USD
```

**If ever adding a subset to `etf_monitoraggio.xlsx`**: the `.MI` ticker resolves on
yfinance (verified 2026-09-03); pick a `Categoria` string that maps via
`ETFTechnicalAnalyzer.detect_family` to the right family (gold_miners → oro_metalli_preziosi,
commodity → commodities, sectors/broad/factor → equity_sviluppati or settoriali_growth,
country_em → mercati_emergenti). Restart container after editing the xlsx (bind-mount
gotcha — [[etf_ticker_must_match_directa_listing]]).
