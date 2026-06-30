"""
REST API routes. Each endpoint is thin — it resolves dependencies (provider,
cache, LLM client) and delegates to service/strategy/AI layers. No business
logic lives here.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.models.schemas import AssetComparison, AssetSymbol, NewsItem, TechnicalAnalysisResult
from app.services.ai.clients import get_llm_client
from app.services.ai.decision_engine import compare_assets, get_trade_decision
from app.services.analysis_orchestrator import run_technical_analysis
from app.services.cache_service import CacheService
from app.services.news_service import NewsAggregator
from app.services.provider_factory import get_provider_for_symbol

router = APIRouter(prefix="/api/v1")


def get_cache(settings: Settings = Depends(get_settings)) -> CacheService:
    return CacheService(settings)


@router.get("/market/{symbol}/candles")
async def get_candles(
    symbol: AssetSymbol,
    timeframe: str = Query("H1", pattern="^(M15|H1|H4|D1)$"),
    count: int = Query(200, ge=50, le=500),
    settings: Settings = Depends(get_settings),
    cache: CacheService = Depends(get_cache),
):
    # Cached because Twelve Data's free plan allows only 8 calls/minute
    # total, shared with the analysis/signal endpoints and the backend's
    # own background polling. Without this cache, every chart load or
    # frontend refetch would be a guaranteed live API hit.
    cache_key = f"candles:{symbol.value}:{timeframe}:{count}"
    cached = await cache.get_json(cache_key)
    if cached:
        return cached

    provider = get_provider_for_symbol(symbol, settings)
    try:
        series = await provider.get_candles(symbol.value, timeframe, count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data provider error: {e}") from e

    result = series.model_dump(mode="json")
    await cache.set_json(cache_key, result, ttl=settings.price_refresh_interval_sec)
    return result


@router.get("/analysis/{symbol}", response_model=TechnicalAnalysisResult)
async def get_analysis(
    symbol: AssetSymbol,
    timeframe: str = Query("H1", pattern="^(M15|H1|H4|D1)$"),
    settings: Settings = Depends(get_settings),
    cache: CacheService = Depends(get_cache),
):
    cache_key = f"analysis:{symbol.value}:{timeframe}"
    cached = await cache.get_json(cache_key)
    if cached:
        return TechnicalAnalysisResult.model_validate(cached)

    provider = get_provider_for_symbol(symbol, settings)
    try:
        series = await provider.get_candles(symbol.value, timeframe, 250)
        result = run_technical_analysis(symbol, timeframe, series.candles)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data provider error: {e}") from e

    await cache.set_json(cache_key, result.model_dump(mode="json"), ttl=settings.analysis_refresh_interval_sec)
    return result


@router.get("/news/{symbol}", response_model=list[NewsItem])
async def get_news(symbol: AssetSymbol, settings: Settings = Depends(get_settings)):
    aggregator = NewsAggregator(settings)
    return await aggregator.get_news(symbol)


@router.get("/signal/compare", response_model=AssetComparison)
async def compare_signal(
    timeframe: str = Query("H1", pattern="^(M15|H1|H4|D1)$"),
    settings: Settings = Depends(get_settings),
    cache: CacheService = Depends(get_cache),
):
    """The headline feature: Gold vs BTC, which offers better R:R right now.

    IMPORTANT: this route must be declared BEFORE /signal/{symbol} below.
    FastAPI matches routes in declaration order, and {symbol} is a path
    parameter that would otherwise greedily match the literal string
    "compare" as if it were a symbol, causing a 422 validation error
    ("Input should be 'XAUUSD' or 'BTCUSD'") on every call to this endpoint.
    """
    cache_key = f"compare:{timeframe}"
    cached = await cache.get_json(cache_key)
    if cached:
        return AssetComparison.model_validate(cached)

    gold_provider = get_provider_for_symbol(AssetSymbol.XAUUSD, settings)
    btc_provider = get_provider_for_symbol(AssetSymbol.BTCUSD, settings)

    try:
        gold_series = await gold_provider.get_candles(AssetSymbol.XAUUSD.value, timeframe, 250)
        btc_series = await btc_provider.get_candles(AssetSymbol.BTCUSD.value, timeframe, 250)
        gold_analysis = run_technical_analysis(AssetSymbol.XAUUSD, timeframe, gold_series.candles)
        btc_analysis = run_technical_analysis(AssetSymbol.BTCUSD, timeframe, btc_series.candles)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data provider error: {e}") from e

    aggregator = NewsAggregator(settings)
    gold_news = await aggregator.get_news(AssetSymbol.XAUUSD)
    btc_news = await aggregator.get_news(AssetSymbol.BTCUSD)

    llm = get_llm_client(settings)
    comparison = await compare_assets(llm, gold_analysis, btc_analysis, gold_news, btc_news)

    await cache.set_json(cache_key, comparison.model_dump(mode="json"), ttl=settings.analysis_refresh_interval_sec)
    return comparison


@router.get("/signal/{symbol}")
async def get_signal(
    symbol: AssetSymbol,
    timeframe: str = Query("H1", pattern="^(M15|H1|H4|D1)$"),
    settings: Settings = Depends(get_settings),
):
    provider = get_provider_for_symbol(symbol, settings)
    try:
        series = await provider.get_candles(symbol.value, timeframe, 250)
        analysis = run_technical_analysis(symbol, timeframe, series.candles)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data provider error: {e}") from e

    aggregator = NewsAggregator(settings)
    news = await aggregator.get_news(symbol)

    llm = get_llm_client(settings)
    decision = await get_trade_decision(llm, analysis, news)
    return decision
