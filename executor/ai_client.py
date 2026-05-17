"""
ai_client.py — Custom Waterfall API Wrapper.
Primary: Gemini -> Secondary: DeepSeek -> Tertiary: Groq
Receives a compact structured prompt and returns EXECUTE or HOLD.
"""
import json
import logging
from typing import Literal
from openai import OpenAI

from config import settings
from schemas import validate_ai_request, validate_ai_response

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a highly specialized Gold (XAUUSD) trading risk officer working for a systematic trading firm.

You will receive a structured JSON payload containing market context for a potential XAUUSD trade.
Your job is to evaluate whether the trade should be executed or held based on Gold's price action and macroeconomic context (e.g., DXY strength, US Treasury yields, inflation news).

RULES:
1. Respond ONLY with valid JSON matching the ClaudeDecisionResponse schema.
2. Never invent lot sizes, risk percentages, or broker parameters.
3. Never override coded risk limits or session rules.
4. Your decision is EXECUTE or HOLD only.
5. If direction bias and higher-timeframe trend conflict, prefer HOLD.
6. If volatility_regime is "extreme" (e.g., during NFP, CPI, or FOMC news), prefer HOLD unless impact_score >= 4.5.
7. Keep your reason concise — maximum 2 sentences, explicitly referencing Gold-specific drivers if applicable.

Response schema:
{
  "decision": "EXECUTE" | "HOLD",
  "direction": "BUY" | "SELL",
  "confidence": 0.0-1.0,
  "reason": "string",
  "ttl_seconds": integer
}"""

def _execute_ai_call(api_key: str, base_url: str, model_name: str, system_text: str, user_text: str) -> str:
    """Helper function to execute the OpenAI-compatible API call."""
    if not api_key:
        raise ValueError(f"Missing API key for {base_url}")
        
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        temperature=0.1,
        max_tokens=300
    )
    raw = response.choices[0].message.content.strip()
    
    # Clean markdown if AI wraps the JSON
    if raw.startswith("```json"):
        raw = raw.replace("```json\n", "").replace("```", "").strip()
    elif raw.startswith("```"):
        raw = raw.replace("```\n", "").replace("```", "").strip()
        
    return raw

def get_decision(request_payload: dict) -> dict:
    validate_ai_request(request_payload)
    user_content = json.dumps(request_payload, indent=2)
    log.info(f"[AI] Sending decision request for {request_payload['asset']} {request_payload['direction_bias']}")

    raw_response = None

    # LEVEL 1: GEMINI
    try:
        log.info("[AI] Attempting Primary Brain (Gemini)")
        raw_response = _execute_ai_call(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            model_name="gemini-1.5-pro",
            system_text=SYSTEM_PROMPT,
            user_text=user_content
        )
    except Exception as e1:
        log.warning(f"[AI] Gemini failed: {e1}. Falling back to DeepSeek...")
        
        # LEVEL 2: DEEPSEEK
        try:
            raw_response = _execute_ai_call(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                model_name="deepseek-chat",
                system_text=SYSTEM_PROMPT,
                user_text=user_content
            )
        except Exception as e2:
            log.warning(f"[AI] DeepSeek failed: {e2}. Falling back to Groq...")
            
            # LEVEL 3: GROQ
            try:
                raw_response = _execute_ai_call(
                    api_key=settings.GROQ_API_KEY,
                    base_url="https://api.groq.com/openai/v1",
                    model_name="llama-3.3-70b-versatile",
                    system_text=SYSTEM_PROMPT,
                    user_text=user_content
                )
            except Exception as e3:
                log.error(f"[AI] ALL AI BRAINS FAILED. Groq error: {e3}")
                raise RuntimeError("All AI fallback levels exhausted. Trade aborted.")

    try:
        parsed_response = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned non-JSON response: {raw_response!r}") from e

    validate_ai_response(parsed_response)
    log.info(f"[AI] Decision={parsed_response['decision']} confidence={parsed_response['confidence']} reason={parsed_response['reason']}")
    return parsed_response


def get_management_decision(escalation_payload: dict) -> Literal["HOLD", "CLOSE_POSITION"]:
    from schemas import validate_escalation
    validate_escalation(escalation_payload)
    log.info(f"[AI] Management escalation: event={escalation_payload['event']} asset={escalation_payload['asset']}")

    management_system = """You are monitoring an active trading position.
A rule-based warning has triggered. Evaluate the situation and respond with ONLY one of:
{"action": "HOLD"} or {"action": "CLOSE_POSITION"}
No other fields. No explanation unless asked."""

    user_content = json.dumps(escalation_payload, indent=2)

    try:
        raw_response = _execute_ai_call(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            model_name="gemini-1.5-pro",
            system_text=management_system,
            user_text=user_content
        )
    except Exception as e1:
        log.warning(f"[AI] Management Gemini failed: {e1}. Falling back to DeepSeek...")
        try:
            raw_response = _execute_ai_call(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                model_name="deepseek-chat",
                system_text=management_system,
                user_text=user_content
            )
        except Exception:
            log.error("[AI] All management AI brains failed.")
            return "HOLD"

    try:
        parsed = json.loads(raw_response)
        action = parsed.get("action", "HOLD")
        if action not in ("HOLD", "CLOSE_POSITION"):
            return "HOLD"
        log.info(f"[AI] Management action: {action}")
        return action
    except json.JSONDecodeError:
        return "HOLD"
