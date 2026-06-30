"""
Research Query Result Types

Čisté datové objekty vrácené ResearchQuery metodami.
Experiment pracuje s těmito objekty — nikdy přímo s DataFrame internals.

Pravidla:
    - Immutable po vytvoření (frozen=True nebo read-only properties)
    - Žádné DataFrame jako přímé pole
    - Hodnoty jsou plain Python typy (int, float, str, bool, date)
    - Experiment nesmí importovat pandas kvůli přístupu k datům
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AssetSnapshot:
    """
    Snapshot jedné akcie pro konkrétní datum.

    Obsahuje agregované feature hodnoty z FeatureSet.
    Experiment pracuje s AssetSnapshot — nikdy s raw Feature objekty.

    Příklad přístupu:
        snap = leaders[0]
        snap.ticker          → "NVDA"
        snap.mle_rank_20d    → 4.0
        snap.ims_score       → 91.0
        snap.sector          → "Technology"
    """
    conid: int
    ticker: str
    date: date

    # Asset metadata (z AssetUniverse)
    sector: str | None = None
    industry: str | None = None

    # MLE features
    mle_rank_1d:  float | None = None
    mle_rank_5d:  float | None = None
    mle_rank_10d: float | None = None
    mle_rank_20d: float | None = None
    mle_ret_1d:   float | None = None
    mle_ret_5d:   float | None = None
    mle_ret_10d:  float | None = None
    mle_ret_20d:  float | None = None

    # IMS features
    ims_score:            float | None = None
    ims_priority_group:   str | None = None
    ims_rs_vs_spy_20d:    float | None = None
    ims_rank_improvement_20d: float | None = None
    ims_rank_stability_20d:   float | None = None
    ims_rank_today:       float | None = None

    def __repr__(self) -> str:
        parts = [f"ticker={self.ticker!r}", f"date={self.date}"]
        if self.mle_rank_20d is not None:
            parts.append(f"mle_rank_20d={self.mle_rank_20d:.0f}")
        if self.ims_score is not None:
            parts.append(f"ims_score={self.ims_score:.1f}")
        return f"AssetSnapshot({', '.join(parts)})"


@dataclass(frozen=True)
class IndustrySnapshot:
    """
    Snapshot jedné industry pro konkrétní datum a lookback.

    Odpovídá jednomu řádku IRC archivu.
    Industry-level — nepatří konkrétní akcii.

    Příklad přístupu:
        ind = industries[0]
        ind.industry      → "Semiconductors"
        ind.rank          → 2
        ind.median_return → 3.14
    """
    date: date
    lookback: int           # 5, 10, 20, 30 dní
    rank: int
    industry: str
    sector: str | None

    median_return:  float | None = None
    mean_return:    float | None = None
    member_count:   int | None = None
    advance_ratio:  float | None = None

    # Top tickery v industry pro daný den
    top_1_ticker: str | None = None
    top_2_ticker: str | None = None
    top_3_ticker: str | None = None

    def __repr__(self) -> str:
        return (
            f"IndustrySnapshot(rank={self.rank}, industry={self.industry!r}, "
            f"lookback={self.lookback}d, median_ret={self.median_return})"
        )


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Snapshot tržních podmínek pro konkrétní datum.

    Market-level — nepatří žádné akcii ani industry.
    Jedna hodnota na den.

    Příklad přístupu:
        market = query.market_context(date=d)
        market.above_ma50_pct   → 61.1
        market.above_ma200_pct  → 62.5
        market.mcclellan        → 14.4
        market.is_risk_on        → None (MRC zatím neexistuje)
    """
    date: date

    universe_size: int | None = None

    # MA breadth
    above_ma50_pct:  float | None = None
    above_ma100_pct: float | None = None
    above_ma200_pct: float | None = None

    # Advance/Decline
    advance_count: int | None = None
    decline_count: int | None = None
    advance_decline_net: int | None = None
    new_highs: int | None = None
    new_lows:  int | None = None

    # Momentum
    mcclellan: float | None = None

    # Evolution (1D/3D/5D/10D/20D změny)
    above_ma50_1d_change_pp:  float | None = None
    above_ma50_5d_change_pp:  float | None = None
    above_ma50_20d_change_pp: float | None = None
    above_ma200_1d_change_pp: float | None = None
    above_ma200_5d_change_pp: float | None = None
    above_ma200_20d_change_pp: float | None = None

    # MRC placeholder — zatím vždy None
    is_risk_on: bool | None = None

    def __repr__(self) -> str:
        return (
            f"MarketSnapshot(date={self.date}, "
            f"ma50={self.above_ma50_pct}%, "
            f"ma200={self.above_ma200_pct}%, "
            f"mcclellan={self.mcclellan})"
        )
