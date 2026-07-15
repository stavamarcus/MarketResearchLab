# FUND-04 Feature Whitelist (návrh, ke schválení)

**Fáze:** MRL-FUND-04 (protokol). Zdroj polí: adapter `FUNDAMENTAL_FIELDS`
(SF1 ART, non-price-derived): revenue, netinc, eps, fcf, roe, grossmargin,
netmargin, debt, de, assets, equity. Price-derived pole (marketcap/pe/ps/pb,
EV-based) jsou zakázána globálně (policy gate §2, vynuceno wrapperem).

Všechna pole jsou PIT dostupná přes `sf1_datekey <= candidate_date`
(FUND-03: coverage 100 % nad 1 144 candidate-days).

## Null policy (společná)

SF1 hodnota může být NaN i při existujícím snapshotu. Pravidlo:
NaN v poli vyžadovaném variantou ⇒ záznam **vyloučen z dané varianty**
s explicitním počítadlem `field_null_excluded` (per pole, per varianta)
v reportu. Nikdy tichý drop; baseline A zůstává nedotčena.

## Whitelist tabulka

| field | bucket | interpretace | vyšší = | null policy | transformace | leakage riziko | povolen pro 1. test |
|---|---|---|---|---|---|---|---|
| revenue | Size/Scale | tržby TTM (ART) | závisí (scale, ne kvalita) | exclude-from-variant | raw (jen denominátor/derived) | nízké | NE jako filter; ANO jako vstup revenue_yoy |
| revenue_yoy* | Growth | meziroční růst tržeb; *derived: revenue(t) / revenue(PIT t−365) − 1, oba lookupy PIT | lepší | exclude-from-variant (kterýkoli z 2 snapshotů chybí/NaN/revenue<=0) | raw sign / fixní práh | střední — dva PIT lookupy, viz protokol §PIT | ANO (varianta C) |
| netinc | Profitability | čistý zisk TTM | lepší | exclude-from-variant | raw sign (>0) | nízké | ANO (B, F) |
| fcf | Cash Flow | free cash flow TTM | lepší | exclude-from-variant | raw sign (>0) | nízké | ANO (B, F) |
| roe | Profitability | return on equity | lepší (pozor: záporná equity zkresluje) | exclude-from-variant; roe s equity<=0 ⇒ exclude | fixní práh (>0.15) | nízké | ANO (D, F) |
| netmargin | Profitability | čistá marže | lepší (sektorově heterogenní) | exclude-from-variant | raw | nízké | NE v 1. testu (redundantní k roe, sektorový bias bez neutralizace) |
| grossmargin | Profitability | hrubá marže | závisí (silně sektorové) | exclude-from-variant | — | nízké | NE (sektorová heterogenita) |
| eps | Profitability | zisk na akcii | lepší | exclude-from-variant | — | nízké | NE (share-count/dilution šum; netinc postačuje) |
| de | Balance Sheet/Leverage | debt/equity | horší (equity<=0 ⇒ nedefinované) | exclude-from-variant; de při equity<=0 ⇒ treat jako fail podmínky E | fixní práh (>2.0 exclude) | nízké | ANO (E, F) |
| debt | Balance Sheet | absolutní dluh | závisí (scale) | — | — | nízké | NE samostatně (jen v de) |
| assets | Size/Scale | aktiva | závisí (scale) | — | — | nízké | NE (scale bez interpretace kvality) |
| equity | Balance Sheet | vlastní kapitál | závisí | — | — | nízké | NE samostatně (jen v de/roe jmenovateli) |

## Shrnutí pro první edge test

```text
POVOLENO:  netinc, fcf, roe, de, revenue_yoy (derived), revenue (pouze jako vstup derived)
ZAKÁZÁNO:  eps, grossmargin, netmargin, debt, assets, equity samostatně;
           všechna price-derived pole
Transformace: výhradně fixní pre-registrované prahy (žádné in-sample
percentily/terciles — průměr ~4,7 candidate-days/den činí per-day
cross-section nefunkčním a pooled percentily nesou distribuční look-ahead)
```
