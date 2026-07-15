"""
MRLSharadarFundamentalSource — read-only most MRL candidate-days
→ sharadar_mdsm_adapter PIT SF1 snapshoty.

Fáze: MRL-FUND-01 (smoke integration).
Kontrakt: docs/MRL_FUNDAMENTAL_PROVIDER_CONTRACT.md v0.1.

Architektonická rozhodnutí (schválena 2026-07-04):
    - insertion point: lazy fundamental_source v ExperimentContext
    - price-derived pole (marketcap/pe/ps/pb) globálně zakázána v v1
    - žádná memoizace: 1 input řádek = 1 provider request = 1 output řádek
    - staleness: warning-only pass-through
    - snapshot_id pinovaný; "latest" pouze explicitně (allow_latest, debug)
    - missing fundamentals NEJSOU tichý drop — každý fail má reason_code

Wrapper NESMÍ: scoring, selekci, forward returns, API volání, čtení
parquet/manifestů mimo adapter API, zápis mimo předaný artifacts adresář,
import MDSM-Lite / Decision Resolveru / produkčních modulů, mutaci
candidate-days.

Závislost: balík `sharadar_mdsm_adapter` (import lazy — MRL bez
nainstalovaného adapteru funguje beze změny, dokud se source nepoužije).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)

STATUS_OK = "OK"
STATUS_EXCLUDED = "EXCLUDED"

REQUIRED_INPUT_COLUMNS = ("conid", "candidate_date")

# Metadata sloupce outputu (kontrakt §3); fundamental pole se doplní dle fields.
OUTPUT_META_COLUMNS = (
    "conid", "candidate_date", "sf1_datekey", "staleness_days",
    "staleness_flag", "identity_tier", "is_alias",
    "coverage_status", "reason_code",
)


class FundamentalSourceError(Exception):
    """Konfigurační / programátorská chyba wrapperu (ne datový fail)."""


def _adapter():
    """Lazy import adapter modulů. Selže srozumitelně, pokud adapter
    není nainstalovaný (pip install -e; viz FUND-01 open issues)."""
    try:
        from sharadar_mdsm_adapter import (config, coverage, exceptions,
                                           identity_map, schemas, sf1_provider,
                                           sf1_store)
    except ImportError as e:
        raise FundamentalSourceError(
            "Balík sharadar_mdsm_adapter není importovatelný. "
            "Nainstaluj adapter jako dependency (pip install -e). "
            f"Původní chyba: {e}"
        ) from e
    return config, coverage, exceptions, identity_map, schemas, \
        sf1_provider, sf1_store


class MRLSharadarFundamentalSource:
    """Batch PIT fundamentals pro MRL candidate-days.

    Konstruuje se jednou per run přes build_fundamental_source().
    """

    def __init__(self, provider, handle, fields: tuple | None = None):
        _, _, _, _, schemas, _, _ = _adapter()
        allowed = tuple(schemas.FUNDAMENTAL_FIELDS)
        if fields is None:
            fields = allowed
        forbidden = [f for f in fields if f not in allowed]
        if forbidden:
            # price-derived i neznámá pole — zakázáno na wrapper úrovni (v1)
            raise FundamentalSourceError(
                f"Pole mimo FUNDAMENTAL_FIELDS jsou v MRL v1 zakázána "
                f"(price-derived policy): {forbidden}"
            )
        self._provider = provider
        self._handle = handle
        self._fields = tuple(fields)

    # ------------------------------------------------------------ metadata

    @property
    def snapshot_id(self) -> str:
        return self._handle.snapshot_id

    @property
    def contract_versions(self) -> dict:
        return dict(self._handle.contract_versions)

    @property
    def snapshot_data_hash(self) -> str | None:
        return self._handle.manifest.get("data_hash")

    @property
    def fields(self) -> tuple:
        return self._fields

    # --------------------------------------------------------------- batch

    def get_fundamentals(
        self,
        candidate_days: pd.DataFrame,
        experiment_id: str | None = None,
    ):
        """1 input řádek = 1 provider request = 1 output řádek (1:1, v pořadí).

        Returns:
            (output_df, CoverageAccumulator)
        EXCLUDED řádky zůstávají v outputu s NaN fundamentals + reason_code.
        """
        _, coverage_mod, exceptions_mod, _, _, _, _ = _adapter()

        missing = [c for c in REQUIRED_INPUT_COLUMNS
                   if c not in candidate_days.columns]
        if missing:
            raise FundamentalSourceError(
                f"candidate_days chybí povinné sloupce: {missing}"
            )

        cov = coverage_mod.CoverageAccumulator(
            snapshot_id=self.snapshot_id,
            contract_versions=self.contract_versions,
        )

        records = []
        for row in candidate_days.itertuples(index=False):
            conid = int(row.conid)
            cand = row.candidate_date
            base = {
                "conid": conid,
                "candidate_date": cand,
                "sf1_datekey": pd.NaT,
                "staleness_days": float("nan"),
                "staleness_flag": None,
                "identity_tier": None,
                "is_alias": None,
                "coverage_status": STATUS_EXCLUDED,
                "reason_code": None,
                **{f: float("nan") for f in self._fields},
            }
            try:
                snap = self._provider.get_snapshot(
                    conid, cand, fields=list(self._fields))
            except exceptions_mod.SharadarProviderError as e:
                cov.record_failure(conid, cand, e.reason)
                base["reason_code"] = e.reason
            except Exception as e:  # noqa: BLE001 — kontrakt §4 UNKNOWN_ERROR
                logger.warning(
                    f"fundamental_source UNKNOWN_ERROR conid={conid} "
                    f"date={cand}: {e!r}")
                cov.record_failure(conid, cand, "UNKNOWN_ERROR")
                base["reason_code"] = "UNKNOWN_ERROR"
            else:
                cov.record_success(conid, cand, snap)
                base.update({
                    "sf1_datekey": snap.datekey,
                    "staleness_days": snap.staleness_days,
                    "staleness_flag": snap.staleness_flag,
                    "identity_tier": snap.identity_tier,
                    "is_alias": snap.alias_flag is not None,
                    "coverage_status": STATUS_OK,
                    "reason_code": None,
                })
                base.update({f: snap.fundamentals.get(f, float("nan"))
                             for f in self._fields})
            records.append(base)

        columns = list(OUTPUT_META_COLUMNS) + list(self._fields)
        out = pd.DataFrame.from_records(records, columns=columns)
        if len(out) != len(candidate_days):
            # tvrdá 1:1 invarianta — porušení = bug wrapperu
            raise FundamentalSourceError(
                f"1:1 invarianta porušena: input {len(candidate_days)} "
                f"vs output {len(out)}")
        if experiment_id:
            logger.info(
                f"[{experiment_id}] fundamentals: "
                f"{cov.returned_snapshots}/{cov.requested_candidate_days} OK "
                f"(coverage_pct={cov.coverage_pct:.1f})")
        return out, cov

    def write_coverage_report(self, coverage, artifacts_dir,
                              run_id: str) -> Path:
        """coverage_<run_id>.md do artifacts adresáře běhu (adapter formát)."""
        return coverage.write_markdown(
            Path(artifacts_dir) / f"coverage_{run_id}.md")


# ---------------------------------------------------------- composition root

def build_fundamental_source(
    adapter_config_path,
    snapshot_id: str,
    fields: tuple | None = None,
    allow_latest: bool = False,
) -> MRLSharadarFundamentalSource:
    """Sestaví source nad pinovaným snapshotem přes veřejné adapter API.

    snapshot_id="latest" je povoleno POUZE s allow_latest=True
    (lokální smoke/debug) — experimenty musí pinovat konkrétní ID.

    Raises:
        FundamentalSourceError: latest bez allow_latest; adapter neimportovatelný
        SharadarProviderError:  CACHE_MISSING/SCHEMA_MISMATCH (setup-level;
                                volající — validate() — musí run odmítnout)
    """
    config_mod, _, _, identity_mod, _, provider_mod, store_mod = _adapter()

    if snapshot_id == "latest" and not allow_latest:
        raise FundamentalSourceError(
            "snapshot_id='latest' není povolen pro experimenty — pinuj "
            "konkrétní snapshot_id (allow_latest=True jen pro lokální debug).")

    cfg = config_mod.load_config(adapter_config_path)
    handle = store_mod.SF1Store(cfg).load(snapshot_id)
    ident = identity_mod.IdentityMap.load(cfg.identity_map_path,
                                          cfg.allowed_tiers)
    provider = provider_mod.SF1Provider(
        handle, ident, staleness_warning_days=cfg.staleness_warning_days)
    logger.info(
        f"fundamental_source: snapshot={handle.snapshot_id} "
        f"rows={len(handle)} contract={handle.contract_versions}")
    return MRLSharadarFundamentalSource(provider, handle, fields=fields)
