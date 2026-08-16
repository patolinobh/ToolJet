import os
import httpx

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/claude-instant")


async def summarize_for_lookup(text: str) -> str:
    """
    Stub de integração com Claude Code / Anthropic. Em produção, usar client oficial e respeitar políticas.
    A função só será acionada se SEND_TO_CLAUDE=true e CLAUDE_API_KEY estiver setada.
    """
    send = os.getenv("SEND_TO_CLAUDE", "false").lower() == "true"
    if not send or not CLAUDE_API_KEY:
        return ""

    # Exemplo simples usando httpx — ajuste conforme a API real do Claude/Anthropic
    payload = {
        "prompt": text,
        "max_tokens": 300
    }
    headers = {"Authorization": f"Bearer {CLAUDE_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(CLAUDE_API_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        # estrutura fictícia — adaptar para resposta real
        return data.get("completion", "")
