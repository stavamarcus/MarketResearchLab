"""
ResearchQuery — přístupová vrstva nad ExperimentContext.

Filozofie:
    context = data container
    ResearchQuery = data access helper

    Experiment nepracuje s DataFrame internals.
    Experiment nepracuje přímo s FeatureSet indexy.
    Experiment se ptá ResearchQuery v doménovém jazyce.

Pravidla (dle architektury):
    1. ResearchQuery není doménová entita — je to helper.
    2. ResearchQuery nemění data.
    3. ResearchQuery nepočítá nové signály.
    4. ResearchQuery pouze filtruje a spojuje:
       - context.features (FeatureSet)
       - context.signals (IRC, breadth DataFrames)
       - context.assets (AssetUniverse)
    5. Výstup jsou čisté Python objekty (AssetSnapshot, IndustrySnapshot, MarketSnapshot).
    6. DataFrame internals neprotékají do experimentů.

Použití:
    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        leaders = query.assets(
            date=some_date,
            mle_rank_max=50,
            ims_score_min=80,
        )

        industries = query.industry_context(
            date=some_date,
            lookback=20,
            rank_max=10,
        )

        market = query.market_context(date=some_date)
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.infrastructure.logging_manager import get_logger
from src.query.query_results import AssetSnapshot, IndustrySnapshot, MarketSnapshot

logger = get_logger(__name__)

# Mapping: AssetSnapshot field → feature_name v FeatureSet
_FEATURE_TO_FIELD: dict[str, str] = {
    "MLE_Rank_1d":  "mle_rank_1d",
    "MLE_Rank_5d":  "mle_rank_5d",
    "MLE_Rank_10d": "mle_rank_10d",
    "MLE_Rank_20d": "mle_rank_20d",
    "MLE_Ret_1d":   "mle_ret_1d",
    "MLE_Ret_5d":   "mle_ret_5d",
    "MLE_Ret_10d":  "mle_ret_10d",
    "MLE_Ret_20d":  "mle_ret_20d",
    "IMS_Score":               "ims_score",
    "IMS_Priority_Group":      "ims_priority_group",
    "IMS_RS_vs_SPY_20d":       "ims_rs_vs_spy_20d",
    "IMS_Rank_Improvement_20d":"ims_rank_improvement_20d",
    "IMS_Rank_Stability_20d":  "ims_rank_stability_20d",
    "IMS_Rank_Today":          "ims_rank_today",
}


class ResearchQuery:
    """
    Query API nad ExperimentContext.

    Jeden instance per experiment run — sestavit na začátku run():
        query = ResearchQuery(context)
    """

    def __init__(self, context: ExperimentContext) -> None:
        self._context = context

    # ------------------------------------------------------------------
    # assets() — asset-level query
    # ------------------------------------------------------------------

    def assets(
        self,
        date: date,
        *,
        mle_rank_max: int | None = None,
        mle_rank_min: int | None = None,
        mle_ret_20d_min: float | None = None,
        ims_score_min: float | None = None,
        ims_priority_group: str | None = None,     # "HIGH" | "RADAR"
        sector: str | None = None,
        industry: str | None = None,
        conids: list[int] | None = None,
        sort_by: str = "mle_rank_20d",
        ascending: bool = True,
    ) -> list[AssetSnapshot]:
        """
        Vrátí seznam AssetSnapshot pro daný datum splňující zadaná kritéria.

        Každý AssetSnapshot obsahuje všechny dostupné feature hodnoty
        pro daný conid a datum — bez ohledu na to jaké filtry jsou zadány.

        Args:
            date:                datum dotazu
            mle_rank_max:        pouze akcie s MLE_Rank_20d <= N (TOP N)
            mle_rank_min:        pouze akcie s MLE_Rank_20d >= N
            mle_ret_20d_min:     pouze akcie s MLE_Ret_20d >= X %
            ims_score_min:       pouze akcie s IMS_Score >= X
            ims_priority_group:  "HIGH" nebo "RADAR"
            sector:              filtr podle sektoru
            industry:            filtr podle odvětví
            conids:              explicitní seznam conid (přepíše ostatní filtry)
            sort_by:             pole pro řazení (field name AssetSnapshot)
            ascending:           směr řazení

        Returns:
            Seřazený seznam AssetSnapshot. Prázdný seznam pokud nic nevyhovuje.
        """
        ctx = self._context

        # Sestavíme snapshot pro každý conid s features pro daný den
        snapshots = self._build_snapshots(date)

        if not snapshots:
            logger.debug(f"assets({date}): žádné snapshots — prázdný FeatureSet?")
            return []

        result = list(snapshots.values())

        # Filtry
        if conids is not None:
            conid_set = set(conids)
            result = [s for s in result if s.conid in conid_set]

        if mle_rank_max is not None:
            result = [s for s in result if s.mle_rank_20d is not None
                      and s.mle_rank_20d <= mle_rank_max]

        if mle_rank_min is not None:
            result = [s for s in result if s.mle_rank_20d is not None
                      and s.mle_rank_20d >= mle_rank_min]

        if mle_ret_20d_min is not None:
            result = [s for s in result if s.mle_ret_20d is not None
                      and s.mle_ret_20d >= mle_ret_20d_min]

        if ims_score_min is not None:
            result = [s for s in result if s.ims_score is not None
                      and s.ims_score >= ims_score_min]

        if ims_priority_group is not None:
            result = [s for s in result
                      if s.ims_priority_group == ims_priority_group]

        if sector is not None:
            result = [s for s in result if s.sector == sector]

        if industry is not None:
            result = [s for s in result if s.industry == industry]

        # Řazení
        result = self._sort_snapshots(result, sort_by, ascending)

        return result

    # ------------------------------------------------------------------
    # industry_context() — industry-level query
    # ------------------------------------------------------------------

    def industry_context(
        self,
        date: date,
        *,
        lookback: int = 20,
        rank_max: int | None = None,
        sector: str | None = None,
        industry: str | None = None,
    ) -> list[IndustrySnapshot]:
        """
        Vrátí seznam IndustrySnapshot pro daný datum a lookback.

        Data pochází z context.signals["IRC"].

        Args:
            date:      datum dotazu
            lookback:  5 | 10 | 20 | 30 dní (default 20)
            rank_max:  pouze industry s rank <= N (TOP N)
            sector:    filtr podle sektoru
            industry:  filtr podle konkrétní industry

        Returns:
            Seřazený seznam IndustrySnapshot podle rank ASC.
            Prázdný seznam pokud IRC signál není v context.signals.
        """
        irc_df = self._context.signals.get("IRC")
        if irc_df is None or irc_df.empty:
            logger.warning(
                "industry_context(): IRC není v context.signals. "
                "Přidej 'IRC' do required_data nebo načti přes SignalProvider."
            )
            return []

        ts = pd.Timestamp(date)
        day_df = irc_df[
            (irc_df["date"] == ts) &
            (irc_df["lookback"] == lookback)
        ].copy()

        if day_df.empty:
            logger.debug(f"industry_context({date}, lookback={lookback}): žádná data.")
            return []

        # Filtry
        if rank_max is not None:
            day_df = day_df[day_df["rank"] <= rank_max]
        if sector is not None:
            day_df = day_df[day_df["sector"] == sector]
        if industry is not None:
            day_df = day_df[day_df["industry"] == industry]

        result = []
        for _, row in day_df.iterrows():
            result.append(IndustrySnapshot(
                date=date,
                lookback=int(row["lookback"]),
                rank=int(row["rank"]),
                industry=str(row["industry"]),
                sector=str(row["sector"]) if pd.notna(row.get("sector")) else None,
                median_return=_safe_float(row.get("median_return")),
                mean_return=_safe_float(row.get("mean_return")),
                member_count=_safe_int(row.get("member_count")),
                advance_ratio=_safe_float(row.get("advance_ratio")),
                top_1_ticker=_safe_str(row.get("top_1_ticker")),
                top_2_ticker=_safe_str(row.get("top_2_ticker")),
                top_3_ticker=_safe_str(row.get("top_3_ticker")),
            ))

        result.sort(key=lambda x: x.rank)
        return result

    # ------------------------------------------------------------------
    # market_context() — market-level query
    # ------------------------------------------------------------------

    def market_context(self, date: date) -> MarketSnapshot | None:
        """
        Vrátí MarketSnapshot pro daný datum.

        Data pochází z context.signals["breadth"].

        Returns:
            MarketSnapshot nebo None pokud breadth data nejsou dostupná.
        """
        brd_df = self._context.signals.get("breadth")
        if brd_df is None or brd_df.empty:
            logger.warning(
                "market_context(): breadth není v context.signals. "
                "Přidej 'breadth' do required_data nebo načti přes SignalProvider."
            )
            return None

        ts = pd.Timestamp(date)
        row_df = brd_df[brd_df["date"] == ts]

        if row_df.empty:
            logger.debug(f"market_context({date}): žádná breadth data.")
            return None

        row = row_df.iloc[0]

        return MarketSnapshot(
            date=date,
            universe_size=_safe_int(row.get("universe_size")),
            above_ma50_pct=_safe_float(row.get("above_ma50_pct")),
            above_ma100_pct=_safe_float(row.get("above_ma100_pct")),
            above_ma200_pct=_safe_float(row.get("above_ma200_pct")),
            advance_count=_safe_int(row.get("advance_count")),
            decline_count=_safe_int(row.get("decline_count")),
            advance_decline_net=_safe_int(row.get("advance_decline_net")),
            new_highs=_safe_int(row.get("new_highs")),
            new_lows=_safe_int(row.get("new_lows")),
            mcclellan=_safe_float(row.get("mcclellan")),
            above_ma50_1d_change_pp=_safe_float(row.get("above_ma50_1d_change_pp")),
            above_ma50_5d_change_pp=_safe_float(row.get("above_ma50_5d_change_pp")),
            above_ma50_20d_change_pp=_safe_float(row.get("above_ma50_20d_change_pp")),
            above_ma200_1d_change_pp=_safe_float(row.get("above_ma200_1d_change_pp")),
            above_ma200_5d_change_pp=_safe_float(row.get("above_ma200_5d_change_pp")),
            above_ma200_20d_change_pp=_safe_float(row.get("above_ma200_20d_change_pp")),
            is_risk_on=None,  # MRC zatím neexistuje
        )

    # ------------------------------------------------------------------
    # dates() — helper pro iteraci přes obchodní dny v context rozsahu
    # ------------------------------------------------------------------

    def dates(self) -> list[date]:
        """
        Vrátí seřazený seznam datumů pro které existují data v context.

        Odvozeno z dostupných cen (context.prices) — průnik s features.
        """
        if not self._context.prices:
            return []
        # Vezmi dny z první dostupné price série
        first_df = next(iter(self._context.prices.values()))
        return [ts.date() for ts in first_df.index]

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------

    def _build_snapshots(self, date: date) -> dict[int, AssetSnapshot]:
        """
        Sestaví dict[conid → AssetSnapshot] pro daný den ze FeatureSet a AssetUniverse.
        """
        features = self._context.features.all_for_date(date)
        if not features:
            return {}

        # Agregace features per conid
        per_conid: dict[int, dict[str, object]] = {}
        for f in features:
            if f.conid not in per_conid:
                per_conid[f.conid] = {}
            field_name = _FEATURE_TO_FIELD.get(f.feature_name)
            if field_name:
                per_conid[f.conid][field_name] = f.value

        # Sestavení AssetSnapshot
        snapshots: dict[int, AssetSnapshot] = {}
        for conid, fields in per_conid.items():
            asset = self._context.assets.get(conid)
            snapshots[conid] = AssetSnapshot(
                conid=conid,
                ticker=asset.ticker if asset else str(conid),
                date=date,
                sector=asset.sector if asset else None,
                industry=asset.industry if asset else None,
                **fields,
            )

        return snapshots

    def _sort_snapshots(
        self,
        snapshots: list[AssetSnapshot],
        sort_by: str,
        ascending: bool,
    ) -> list[AssetSnapshot]:
        """Seřadí AssetSnapshot seznam podle zadaného pole."""
        def key_fn(s: AssetSnapshot):
            val = getattr(s, sort_by, None)
            # None na konec
            if val is None:
                return (1, 0)
            return (0, val)

        return sorted(snapshots, key=key_fn, reverse=not ascending)


# ------------------------------------------------------------------
# Helper funkce
# ------------------------------------------------------------------

def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        f = float(val)
        return None if pd.isna(f) else int(f)
    except (TypeError, ValueError):
        return None


def _safe_str(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s else None
