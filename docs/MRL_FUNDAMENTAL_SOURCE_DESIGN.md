# MRLSharadarFundamentalSource — návrh wrapperu (design only)

**Fáze:** MRL-FUND-00. Žádná implementace — pouze návrh ke schválení.
**Implementace:** až MRL-FUND-01 po architektonickém schválení.

---

## 1. Umístění a závislosti

```text
Navržený soubor: src/providers/sharadar_fundamental_source.py   (FUND-01)
Config sekce:    config/data_paths.yaml → sharadar_fundamentals:
                     adapter_config: C:\Users\stava\Projects\sharadar_mdsm_adapter\config\adapter_config.yaml
                     snapshot_id:    sf1art_20260704_005521   # pin, nikdy "latest" v experimentech

Závislosti (import): sharadar_mdsm_adapter (config, sf1_store, sf1_provider,
                     coverage, exceptions), pandas
Směr závislosti:     MRL → adapter. Nikdy opačně (adapter to kontraktně testuje).
Zakázané závislosti: MDSM-Lite, Decision Resolver, MLE, IRC, requests/urllib/httpx
```

## 2. Navržené API

```python
class MRLSharadarFundamentalSource:
    """Read-only most: MRL candidate-days -> adapter PIT snapshoty.

    Konstruuje se JEDNOU per experiment run (composition root / factory):
        cfg    = load_config(adapter_config_path)
        handle = SF1Store(cfg).load(snapshot_id)          # pinned, ne "latest"
        ident  = IdentityMap.load(cfg.identity_map_path, cfg.allowed_tiers)
        provider = SF1Provider(handle, ident, cfg.staleness_warning_days)
        source = MRLSharadarFundamentalSource(provider, handle)
    """

    def __init__(self, provider: SF1Provider, handle: StoreHandle,
                 fields: tuple = FUNDAMENTAL_FIELDS): ...

    @property
    def snapshot_id(self) -> str: ...
    @property
    def contract_versions(self) -> dict: ...
    @property
    def snapshot_data_hash(self) -> str: ...   # z manifestu -> source_hashes

    def get_fundamentals(
        self,
        candidate_days: pd.DataFrame,          # input schema kontraktu §2
        experiment_id: str | None = None,
    ) -> tuple[pd.DataFrame, CoverageAccumulator]:
        """1 input řádek = 1 provider request = 1 output řádek (kontrakt §3).

        Per řádek:
            try:  snap = provider.get_snapshot(conid, candidate_date,
                                               fields=list(self._fields))
                  coverage.record_success(...); řádek OK
            except SharadarProviderError as e:
                  coverage.record_failure(..., e.reason); řádek EXCLUDED
            except Exception:
                  coverage.record_failure(..., "UNKNOWN_ERROR"); řádek EXCLUDED
        """

    def write_coverage_report(self, coverage, run_artifacts_dir) -> Path:
        """coverage.write_markdown(run_artifacts_dir / f"coverage_{run_id}.md")"""
```

## 3. Odpovědnosti wrapperu

```text
1. přijmout MRL candidate-days (DataFrame dle kontraktu §2)
2. per řádek zavolat SF1Provider.get_snapshot() nad pinovaným snapshotem
3. vrátit output DataFrame 1:1 (fundamentals + coverage metadata + reason_code)
4. vést CoverageAccumulator a zapsat coverage_<run_id>.md do run artifacts
5. exponovat snapshot_id / contract_versions / data_hash pro run metadata
```

## 4. Co wrapper výslovně NESMÍ

```text
scoring, quality skóre, buckety, selekce, sizing, trading logic
forward returns nebo jakékoli výnosové výpočty
API volání (žádné HTTP importy — převzít adapter contract test vzor)
čtení raw/processed parquet či manifestů napřímo (pouze adapter API)
zápis kamkoli mimo run artifacts adresář experimentu
import MDSM-Lite / Decision Resolveru / produkčních modulů
mutace nebo filtrování candidate-days (ani dedup — v0.1)
fallback "latest" snapshot v experiment režimu
```

## 5. Napojení do frameworku (návrh, FUND-01)

Minimální zásah (varianta B z discovery):

```text
ExperimentContext:  nové optional pole fundamental_source (default None)
ProviderFactory:    build() sestaví source, pokud existuje config sekce
                    sharadar_fundamentals; jinak None (zpětně kompatibilní)
ContextBuilder:     předá source do contextu; ŽÁDNÝ prefetch
Experiment:         po vygenerování candidate-days:
                        fund_df, cov = context.fundamental_source.get_fundamentals(...)
ExperimentRunner:   beze změny (coverage report jde přes result.artifacts /
                    zápis do run_path — mechanismus upřesní FUND-01)
source_hashes:      + {"sf1_snapshot": data_hash, "sf1_snapshot_id": snapshot_id}
```

Dotčené MRL soubory ve FUND-01: `experiment_context.py` (+1 pole),
`provider_factory.py` (+optional build), `data_paths.yaml` (+sekce),
nový `sharadar_fundamental_source.py`, testy. Nic jiného.

## 6. Error / reason_code handling

| Situace | Chování |
|---|---|
| Store load fail (CACHE_MISSING/SCHEMA_MISMATCH) při konstrukci | výjimka nahoru → experiment `validate()` FAILED; run se nespustí |
| Request-level SharadarProviderError | řádek EXCLUDED + reason_code, run pokračuje |
| Ne-SharadarProviderError v get_snapshot | řádek EXCLUDED + UNKNOWN_ERROR, run pokračuje; >0 UNKNOWN_ERROR = investigace před interpretací výsledků |
| STALE_SNAPSHOT flag | řádek OK + staleness_flag; počítá se ve stale_warnings |

## 7. Očekávané schema výstupu

Přesně dle MRL_FUNDAMENTAL_PROVIDER_CONTRACT.md §3 (bez price-derived polí).

## 8. Testovatelnost (výhled FUND-01)

- Unit: syntetický SF1Provider/StoreHandle (vzor: adapter tests/test_smoke_runner.py)
- Contract: žádné HTTP/MDSM/Resolver importy; 1:1 input/output; coverage konzistence
- Žádná reálná Sharadar data v testech
