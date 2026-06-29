"""
Asset — doménový objekt reprezentující obchodovaný instrument.

Pravidlo:
    Experimenty pracují s Asset, nikdy přímo s conid.
    conid zůstává technický identifikátor (IBKR), ale není primárním
    objektem výzkumné logiky.

Výhoda:
    Při přechodu na Sharadar nebo jiný zdroj se změní pouze provider.
    Experimenty zůstanou beze změny — pracují s Asset, ne s conid.

Kontrakt:
    Asset je immutable po vytvoření (frozen=True).
    Všechna pole kromě conid a ticker jsou optional.
    metadata dict slouží pro rozšíření bez změny kontraktu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Asset:
    """
    Doménový objekt reprezentující obchodovaný instrument.

    Povinná pole:
        conid:  IBKR contract ID — technický identifikátor, interní použití
        ticker: čitelný symbol (např. "AAPL", "SPY")

    Volitelná pole (None = informace není dostupná ze zdroje):
        company_name: plný název společnosti
        exchange:     burza (např. "SMART", "NASDAQ")
        currency:     měna (např. "USD")
        instrument_type: typ instrumentu ("STK", "ETF", ...)
        sector:       sektor (IBKR taxonomy)
        industry:     odvětví (IBKR taxonomy)
        subcategory:  podkategorie (IBKR taxonomy)
        active:       aktivní v universe k datu načtení

    metadata:
        Rozšiřitelný dict pro dodatečné atributy bez změny kontraktu.
        Příklad: {"ibkr_primary_exch": "NYSE", "market_cap": "large"}
    """

    conid: int
    ticker: str

    company_name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    instrument_type: str | None = None
    sector: str | None = None
    industry: str | None = None
    subcategory: str | None = None
    active: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.conid, int) or self.conid <= 0:
            raise ValueError(f"Asset.conid musí být kladné celé číslo, dostáno: {self.conid!r}")
        if not self.ticker or not self.ticker.strip():
            raise ValueError(f"Asset.ticker nesmí být prázdný (conid={self.conid})")

    def __repr__(self) -> str:
        return f"Asset(conid={self.conid}, ticker={self.ticker!r})"

    @classmethod
    def from_universe_row(cls, conid: int, row: dict) -> "Asset":
        """
        Sestaví Asset z řádku universe DataFrame (dict z .to_dict()).

        Používá UniverseProvider — experiment tuto metodu nevolá přímo.
        """
        def _clean(v) -> str | None:
            if v is None:
                return None
            s = str(v).strip()
            return s if s and s.lower() not in ("nan", "none", "") else None

        return cls(
            conid=conid,
            ticker=str(row.get("ticker", "")).strip(),
            company_name=_clean(row.get("company_name")),
            exchange=_clean(row.get("exchange")),
            currency=_clean(row.get("currency")),
            instrument_type=_clean(row.get("instrument_type")),
            sector=_clean(row.get("sector")),
            industry=_clean(row.get("industry")),
            subcategory=_clean(row.get("subcategory")),
            active=bool(row.get("active_flag", True)),
        )


class AssetUniverse:
    """
    Kolekce Asset objektů pro experiment.

    Poskytuje rychlý lookup bez nutnosti iterace.
    Experiment dostane AssetUniverse přes ExperimentContext.
    """

    def __init__(self, assets: list[Asset]) -> None:
        self._by_conid: dict[int, Asset] = {a.conid: a for a in assets}
        self._by_ticker: dict[str, Asset] = {a.ticker: a for a in assets}

    def get(self, conid: int) -> Asset | None:
        """Vrátí Asset pro daný conid, nebo None."""
        return self._by_conid.get(conid)

    def get_by_ticker(self, ticker: str) -> Asset | None:
        """Vrátí Asset pro daný ticker, nebo None."""
        return self._by_ticker.get(ticker.upper())

    def all(self) -> list[Asset]:
        """Vrátí všechny Asset objekty."""
        return list(self._by_conid.values())

    def active(self) -> list[Asset]:
        """Vrátí pouze aktivní Asset objekty."""
        return [a for a in self._by_conid.values() if a.active]

    def conids(self) -> list[int]:
        """Vrátí seznam všech conid."""
        return list(self._by_conid.keys())

    def tickers(self) -> list[str]:
        """Vrátí seznam všech tickerů."""
        return list(self._by_ticker.keys())

    def filter_by_sector(self, sector: str) -> "AssetUniverse":
        """Vrátí nový AssetUniverse filtrovaný podle sektoru."""
        return AssetUniverse([
            a for a in self._by_conid.values()
            if a.sector == sector
        ])

    def filter_by_industry(self, industry: str) -> "AssetUniverse":
        """Vrátí nový AssetUniverse filtrovaný podle odvětví."""
        return AssetUniverse([
            a for a in self._by_conid.values()
            if a.industry == industry
        ])

    def __len__(self) -> int:
        return len(self._by_conid)

    def __repr__(self) -> str:
        return f"AssetUniverse(n={len(self)}, active={len(self.active())})"
