# Conservative broker-symbol taxonomy for multi-asset research.
from __future__ import annotations
import re

_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK", "DKK", "SGD", "HKD", "CNH", "CNY", "ZAR", "TRY", "PLN", "MXN"}
_METALS = ("XAU", "XAG", "XPT", "XPD")
_ENERGY = ("WTI", "BRENT", "UKOIL", "USOIL", "XBR", "XTI", "NGAS", "NATGAS")
_CRYPTO = ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "LTC", "BNB")
_INDEXES = ("US30", "DJ30", "DJI", "US500", "SPX", "SP500", "SPX500", "US100", "NAS100", "NDX", "USTEC", "GER40", "DAX", "DE40", "UK100", "FTSE", "JP225", "JPN225", "NIKKEI", "HK50", "HSI", "AU200", "ASX200", "EU50", "STOXX", "FR40", "CAC", "ES35", "IBEX", "SA40", "CH20", "SMI")

def normalize_symbol(symbol: str | None) -> str:
    value = (symbol or "").upper().strip()
    match = re.match(r"[A-Z0-9]+", value)
    return match.group(0) if match else value

def classify_symbol(symbol: str | None) -> str:
    token = normalize_symbol(symbol)
    if not token: return "other"
    if any(token.startswith(prefix) for prefix in _METALS): return "metals"
    if any(token.startswith(prefix) or prefix in token for prefix in _ENERGY): return "energy"
    if any(token.startswith(prefix) or prefix in token for prefix in _CRYPTO): return "crypto"
    if any(token.startswith(prefix) or prefix in token for prefix in _INDEXES): return "indices"
    if len(token) == 6 and token[:3] in _CURRENCIES and token[3:] in _CURRENCIES: return "fx"
    return "other"
