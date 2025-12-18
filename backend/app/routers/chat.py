"""Thoth AI chat endpoints with BYOK (Bring Your Own Key) streaming."""

import json
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx

from ..database import get_db

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    player_context: Optional[List[str]] = None  # Player IDs for context
    include_rankings: bool = False
    include_projections: bool = False


THOTH_SYSTEM_PROMPT = """You are Thoth, the Dynasty Edge AI assistant - an expert in fantasy football dynasty leagues.

Your knowledge includes:
- Dynasty trade values and rankings (KTC-based)
- Player analysis and projections
- Buy/sell signals based on ML edge scores
- Trade negotiation strategies
- Roster construction advice

Guidelines:
1. Be concise but insightful - dynasty players value depth over fluff
2. Use data to back up recommendations when available
3. Consider both short-term production and long-term dynasty value
4. Acknowledge uncertainty in projections
5. Focus on actionable advice

When player context is provided, use it to give specific recommendations.
When asked about trades, consider value, positional scarcity, and team needs."""


@router.post("")
async def chat(
    request: ChatRequest,
    x_anthropic_key: str = Header(..., alias="X-Anthropic-Key"),
):
    """
    Stream a chat response from Thoth AI.

    BYOK (Bring Your Own Key) - requires user's Anthropic API key in header.
    Elite tier only.

    The API key is passed directly to Anthropic and never stored.
    """
    if not x_anthropic_key or not x_anthropic_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=401,
            detail="Valid Anthropic API key required in X-Anthropic-Key header"
        )

    # Build context from player data if requested
    context_parts = []

    if request.player_context:
        db = get_db()
        player_query = """
            MATCH (p:Player)
            WHERE p.gsis_id IN $ids
            RETURN p.name as name, p.position as position, p.team as team,
                   p.age as age, p.ktc_value as ktc_value, p.ktc_rank as rank,
                   p.edge_score as edge_score, p.signal as signal,
                   p.projected_points as projected_points,
                   p.ppg_ppr as ppg_ppr
        """
        players = await db.execute(player_query, {"ids": request.player_context})

        if players:
            context_parts.append("**Player Context:**")
            for p in players:
                context_parts.append(
                    f"- {p['name']} ({p['position']}, {p['team']}): "
                    f"KTC {p.get('ktc_value', 'N/A')}, Rank #{p.get('rank', 'N/A')}, "
                    f"Edge: {p.get('edge_score', 'N/A')} ({p.get('signal', 'N/A')}), "
                    f"PPG: {p.get('ppg_ppr', 'N/A')}"
                )

    if request.include_rankings:
        db = get_db()
        top_rankings = await db.execute("""
            MATCH (p:Player)
            WHERE p.ktc_value IS NOT NULL AND p.team IS NOT NULL
            RETURN p.name as name, p.position as position, p.ktc_value as value
            ORDER BY p.ktc_value DESC
            LIMIT 10
        """, {})

        if top_rankings:
            context_parts.append("\n**Current Top 10 Dynasty Rankings:**")
            for i, p in enumerate(top_rankings, 1):
                context_parts.append(f"{i}. {p['name']} ({p['position']}) - {p['value']}")

    if request.include_projections:
        db = get_db()
        top_projections = await db.execute("""
            MATCH (p:Player)
            WHERE p.projected_points IS NOT NULL
            RETURN p.name as name, p.position as position,
                   p.projected_points as points, p.projection_confidence as conf
            ORDER BY p.projected_points DESC
            LIMIT 10
        """, {})

        if top_projections:
            context_parts.append("\n**Top 10 Projected Players (2025):**")
            for i, p in enumerate(top_projections, 1):
                context_parts.append(
                    f"{i}. {p['name']} ({p['position']}) - "
                    f"{p['points']:.1f} pts (conf: {p.get('conf', 'N/A')})"
                )

    # Build system prompt with context
    system = THOTH_SYSTEM_PROMPT
    if context_parts:
        system += "\n\n" + "\n".join(context_parts)

    # Convert messages to Anthropic format
    anthropic_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]

    async def generate():
        """Stream response from Anthropic API."""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": x_anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2048,
                    "system": system,
                    "messages": anthropic_messages,
                    "stream": True,
                },
                timeout=60.0,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: {json.dumps({'error': error_text.decode()})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        try:
                            event = json.loads(data)
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if "text" in delta:
                                    yield f"data: {json.dumps({'text': delta['text']})}\n\n"
                        except json.JSONDecodeError:
                            continue

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/quick")
async def quick_analysis(
    player_id: str,
    x_anthropic_key: str = Header(..., alias="X-Anthropic-Key"),
):
    """
    Get a quick AI analysis of a specific player.

    BYOK (Bring Your Own Key) - requires user's Anthropic API key.
    Elite tier only.
    """
    if not x_anthropic_key or not x_anthropic_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=401,
            detail="Valid Anthropic API key required"
        )

    db = get_db()

    # Get player data
    query = """
        MATCH (p:Player {gsis_id: $id})
        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)
        RETURN p.name as name, p.position as position, p.team as team,
               p.age as age, p.ktc_value as ktc_value, p.ktc_rank as rank,
               p.ktc_positional_rank as pos_rank, p.ktc_trend as trend,
               p.edge_score as edge_score, p.signal as signal,
               p.projected_points as projected_points,
               p.projected_ppg as projected_ppg,
               p.projection_confidence as confidence,
               p.ppg_ppr as ppg_ppr, p.games_played as games,
               p.draft_year as draft_year, p.draft_round as draft_round,
               t.wins as team_wins, t.losses as team_losses
    """
    results = await db.execute(query, {"id": player_id})

    if not results:
        raise HTTPException(status_code=404, detail="Player not found")

    player = results[0]

    # Build analysis prompt
    prompt = f"""Provide a concise dynasty analysis for {player['name']} ({player['position']}, {player['team']}).

Current Data:
- Age: {player.get('age', 'Unknown')}
- KTC Value: {player.get('ktc_value', 'N/A')} (Rank #{player.get('rank', 'N/A')}, Positional #{player.get('pos_rank', 'N/A')})
- Trend: {player.get('trend', 'N/A')}
- Edge Score: {player.get('edge_score', 'N/A')} ({player.get('signal', 'N/A')})
- Current PPG: {player.get('ppg_ppr', 'N/A')} in {player.get('games', 'N/A')} games
- 2025 Projection: {player.get('projected_points', 'N/A')} pts ({player.get('projected_ppg', 'N/A')} PPG)
- Draft: Round {player.get('draft_round', 'N/A')} ({player.get('draft_year', 'N/A')})

Provide:
1. Dynasty outlook (2-3 sentences)
2. Buy/Hold/Sell recommendation with brief rationale
3. One key risk and one key upside factor"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": x_anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "system": "You are Thoth, a dynasty fantasy football expert. Be concise and data-driven.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to get AI analysis"
            )

        result = response.json()
        analysis = result.get("content", [{}])[0].get("text", "")

    return {
        "player": player,
        "analysis": analysis,
    }


@router.get("/suggestions")
async def get_chat_suggestions():
    """Get suggested prompts for the chat interface."""
    return {
        "suggestions": [
            "Who are the best buy-low dynasty targets right now?",
            "Analyze the trade value of young WRs vs veteran RBs",
            "Which rookies have the highest dynasty upside?",
            "What players should I sell before their value drops?",
            "Help me evaluate a trade: [describe your trade]",
            "What's the outlook for [player name] in dynasty?",
            "Build me a contender roster strategy",
            "Build me a rebuild roster strategy",
        ]
    }
