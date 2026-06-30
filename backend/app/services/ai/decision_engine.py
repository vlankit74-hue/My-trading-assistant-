"""
AI Decision Engine.

Takes the outputs of the technical analysis engine (SMC + Fibonacci +
indicators) plus recent news/sentiment for both assets, and asks the LLM
to produce a strict-JSON trade decision per asset, then a head-to-head
comparison. The LLM's raw text is NEVER trusted directly — it's parsed and
validated against Pydantic schemas, with one retry on malformed output.
"""
import json
from datetime import datetime, timezone

import structlog

from app.models.schemas import (
    AssetComparison,
    AssetSymbol,
    NewsItem,
    TechnicalAnalysisResult,
    TradeDecision,
)
from app.services.ai.base import LLMClient
from app.services.news_service import NewsAggregator

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a disciplined trading analyst assistant. You analyze \
Smart Money Concepts (market structure, order blocks), Fibonacci retracements, \
classic indicators (RSI, MACD, EMA), candlestick price-action patterns \
(engulfing, pin bars, hammers, dojis, stars), and news sentiment to produce a \
trade decision. You are NOT giving financial advice — you are producing \
structured technical/sentiment analysis for a dashboard.

When weighing candlestick patterns: treat them as confirmation/timing signals
that strengthen or weaken a setup defined by structure and fib levels, not as
a standalone reason to trade. A reversal pattern (engulfing, hammer, star)
forming exactly at a fib retracement level or an order block carries more
weight than the same pattern in open space. A pattern whose direction
conflicts with the prevailing trend/structure should lower confidence rather
than flip the call outright, unless structure has also just shifted (MSS).

Respond with ONLY a single valid JSON object. No markdown fences, no preamble, \
no commentary outside the JSON. The JSON must match this exact schema:

{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <float 0.0-1.0>,
  "risk_reward_ratio": <float or null>,
  "entry_zone_low": <float or null>,
  "entry_zone_high": <float or null>,
  "stop_loss": <float or null>,
  "take_profit": [<float>, ...],
  "invalidation_level": <float or null>,
  "reasoning": "<2-4 sentences explaining the decision using the SMC, Fibonacci, \
indicator, candlestick pattern, and news inputs you were given>"
}

Be conservative: prefer HOLD when signals conflict. Never invent data not given to you."""

_COMPARE_SYSTEM_PROMPT = """You are a disciplined trading analyst assistant comparing \
two trade setups (Gold/XAU-USD and Bitcoin/BTC-USD) to determine which currently \
offers the better risk-to-reward opportunity. You are NOT giving financial advice.

Respond with ONLY a single valid JSON object, no markdown fences, no preamble:
{
  "preferred_asset": "XAUUSD" | "BTCUSD",
  "comparison_reasoning": "<3-5 sentences comparing the two setups: confidence, \
risk/reward, structure quality, and news/sentiment backdrop>"
}"""


def _build_asset_prompt(
    analysis: TechnicalAnalysisResult, news: list[NewsItem], avg_sentiment: float
) -> str:
    payload = {
        "symbol": analysis.symbol.value,
        "timeframe": analysis.timeframe,
        "current_price": analysis.current_price,
        "trend": analysis.trend.value,
        "structure_events": [e.model_dump(mode="json") for e in analysis.structure_events],
        "order_blocks": [ob.model_dump(mode="json") for ob in analysis.order_blocks],
        "fibonacci": analysis.fibonacci.model_dump(mode="json") if analysis.fibonacci else None,
        "indicators": analysis.indicators.model_dump(mode="json"),
        "candlestick_patterns": [p.model_dump(mode="json") for p in analysis.candlestick_patterns],
        "news_sentiment_avg": round(avg_sentiment, 3),
        "recent_headlines": [n.title for n in news[:5]],
    }
    return (
        "Analyze the following market data and produce a trade decision JSON:\n\n"
        + json.dumps(payload, indent=2)
    )


async def get_trade_decision(
    llm: LLMClient,
    analysis: TechnicalAnalysisResult,
    news: list[NewsItem],
) -> TradeDecision:
    avg_sentiment = NewsAggregator.average_sentiment(news)
    user_prompt = _build_asset_prompt(analysis, news, avg_sentiment)

    raw = await llm.complete(_SYSTEM_PROMPT, user_prompt)
    parsed = _parse_json_strict(raw)

    if parsed is None:
        logger.warning("llm_malformed_output_retrying", symbol=analysis.symbol)
        retry_prompt = user_prompt + "\n\nYour previous response was not valid JSON. Respond with ONLY the JSON object."
        raw = await llm.complete(_SYSTEM_PROMPT, retry_prompt)
        parsed = _parse_json_strict(raw)

    if parsed is None:
        logger.error("llm_malformed_output_fallback", symbol=analysis.symbol)
        return _fallback_hold_decision(analysis.symbol, "AI response could not be parsed; defaulting to HOLD.")

    try:
        entry_zone = None
        if parsed.get("entry_zone_low") is not None and parsed.get("entry_zone_high") is not None:
            entry_zone = (float(parsed["entry_zone_low"]), float(parsed["entry_zone_high"]))

        return TradeDecision(
            symbol=analysis.symbol,
            action=parsed["action"],
            confidence=max(0.0, min(1.0, float(parsed["confidence"]))),
            risk_reward_ratio=parsed.get("risk_reward_ratio"),
            entry_zone=entry_zone,
            stop_loss=parsed.get("stop_loss"),
            take_profit=parsed.get("take_profit", []) or [],
            invalidation_level=parsed.get("invalidation_level"),
            reasoning=parsed.get("reasoning", ""),
            generated_at=datetime.now(timezone.utc),
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error("llm_schema_validation_failed", symbol=analysis.symbol, error=str(e))
        return _fallback_hold_decision(analysis.symbol, "AI response failed schema validation; defaulting to HOLD.")


async def compare_assets(
    llm: LLMClient,
    gold_analysis: TechnicalAnalysisResult,
    btc_analysis: TechnicalAnalysisResult,
    gold_news: list[NewsItem],
    btc_news: list[NewsItem],
) -> AssetComparison:
    gold_decision = await get_trade_decision(llm, gold_analysis, gold_news)
    btc_decision = await get_trade_decision(llm, btc_analysis, btc_news)

    compare_payload = {
        "gold_decision": gold_decision.model_dump(mode="json"),
        "btc_decision": btc_decision.model_dump(mode="json"),
    }
    user_prompt = "Compare these two trade decisions and pick the better opportunity:\n\n" + json.dumps(
        compare_payload, indent=2
    )

    raw = await llm.complete(_COMPARE_SYSTEM_PROMPT, user_prompt)
    parsed = _parse_json_strict(raw)

    if parsed is None:
        # Deterministic fallback: prefer whichever has higher confidence.
        preferred = (
            AssetSymbol.XAUUSD if gold_decision.confidence >= btc_decision.confidence else AssetSymbol.BTCUSD
        )
        reasoning = "AI comparison response was malformed; defaulted to the higher-confidence setup."
    else:
        preferred = AssetSymbol(parsed["preferred_asset"])
        reasoning = parsed.get("comparison_reasoning", "")

    return AssetComparison(
        gold=gold_decision,
        btc=btc_decision,
        preferred_asset=preferred,
        comparison_reasoning=reasoning,
        generated_at=datetime.now(timezone.utc),
    )


def _parse_json_strict(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _fallback_hold_decision(symbol: AssetSymbol, reason: str) -> TradeDecision:
    return TradeDecision(
        symbol=symbol,
        action="HOLD",
        confidence=0.0,
        reasoning=reason,
        generated_at=datetime.now(timezone.utc),
    )
