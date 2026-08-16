import os
import httpx

FIPE_API_URL = os.getenv("FIPE_API_URL", "https://parallelum.com.br/fipe/api/v1")


async def _get(url: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def get_fipe_valuation(make: str, model: str, year: int) -> dict:
    """
    Implementação simplificada usando a API pública Parallelum (quando possível).
    Observação: a API pública espera ids numéricos para marca/modelo - aqui usamos uma busca simplificada.
    Em produção, mapear corretamente marca/modelo para ids FIPE.
    """
    # Busca marcas
    marcas = await _get(f"{FIPE_API_URL}/carros/marcas")
    # tentativa simples de encontrar marca por nome (case-insensitive)
    marca_id = None
    for m in marcas:
        if m.get("nome") and make and make.lower() in m.get("nome").lower():
            marca_id = m.get("codigo")
            break

    if not marca_id:
        raise RuntimeError("Marca FIPE não encontrada (stub search)")

    modelos = await _get(f"{FIPE_API_URL}/carros/marcas/{marca_id}/modelos")
    modelo_id = None
    for mod in modelos.get("modelos", []) :
        if mod.get("nome") and model and model.lower() in mod.get("nome").lower():
            modelo_id = mod.get("codigo")
            break

    if not modelo_id:
        raise RuntimeError("Modelo FIPE não encontrado (stub search)")

    # busca ano-modelo (lista de anos)
    anos = await _get(f"{FIPE_API_URL}/carros/marcas/{marca_id}/modelos/{modelo_id}/anos")
    # encontrar entrada que contenha o ano (a API retorna string como "2010-1" ou "2010" conforme)
    ano_entry = None
    for a in anos:
        if str(year) in str(a.get("codigo")) or str(year) in a.get("nome", ""):
            ano_entry = a.get("codigo")
            break

    if not ano_entry:
        raise RuntimeError("Ano FIPE não encontrado (stub search)")

    valor = await _get(f"{FIPE_API_URL}/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_entry}")
    return valor
