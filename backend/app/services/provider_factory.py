"""
Symbol-to-provider routing. This is the only place that knows which
provider serves which asset — everything else just asks for a provider by
symbol and gets the right one back.

Both Gold and BTC route through Twelve Data. Binance.com itself is NOT
used as a live data source because it blocks requests from US-based server
IPs with HTTP 451 ("Unavailable for Legal Reasons") — and Render's servers
run in US datacenters, so every Binance call failed there regardless of
where the developer is physically located. Twelve Data supports BTC/USD
natively and isn't subject to that restriction, so it covers both assets.
The BinanceProvider class is kept in the codebase (unused by default) in
case you later deploy somewhere Binance.com is reachable.

Providers are cached as simple module-level singletons rather than via
functools.lru_cache, because lru_cache hashes its arguments to build a
cache key — and the pydantic Settings object passed in here is not
hashable by default, which raised `TypeError: unhashable type: 'Settings'`
on every single request. Module-level globals give the same "build once,
reuse" behavior without that constraint.
"""
from app.core.config import Settings, get_settings
from app.models.schemas import AssetSymbol
from app.services.providers.base import PriceProvider
from app.services.providers.twelvedata_provider import TwelveDataProvider

_twelvedata_instance: TwelveDataProvider | None = None


def _get_twelvedata(settings: Settings) -> TwelveDataProvider:
    global _twelvedata_instance
    if _twelvedata_instance is None:
        _twelvedata_instance = TwelveDataProvider(settings)
    return _twelvedata_instance


def get_provider_for_symbol(symbol: AssetSymbol, settings: Settings | None = None) -> PriceProvider:
    settings = settings or get_settings()
    if symbol in (AssetSymbol.XAUUSD, AssetSymbol.BTCUSD):
        return _get_twelvedata(settings)
    raise ValueError(f"No provider configured for symbol: {symbol}")
