from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.vin_decoder import decode_vin
from app.services.fipe_client import get_fipe_valuation
from app.cache import Cache
from app.models.schemas import LookupRequest, LookupResponse
import os

router = APIRouter()
cache = Cache()

@router.post("/lookup", response_model=LookupResponse)
async def lookup(payload: LookupRequest):
    identifier = payload.identifier.strip()
    id_type = payload.type

    # basic validation performed in pydantic model
    cache_key = f"lookup:{id_type}:{identifier}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = {
        "identifier": identifier,
        "type": id_type,
        "decoded": None,
        "valuation": None,
        "claims": [],
        "auctions": [],
    }

    if id_type == "vin":
        decoded = decode_vin(identifier)
        result["decoded"] = decoded
        # try FIPE valuation by make/model/year if available
        if decoded.get("make") and decoded.get("model") and decoded.get("year"):
            try:
                val = await get_fipe_valuation(decoded.get("make"), decoded.get("model"), decoded.get("year"))
                result["valuation"] = val
            except Exception as e:
                # não falhar inteiro se FIPE indisponível
                result["valuation_error"] = str(e)

    elif id_type == "renavam":
        # for RENAVAM we don't decode VIN; leave decoded None or implement RENAVAM lookup later
        pass

    # TODO: integrar sinistros e leilões (stubs por enquanto)

    await cache.set(cache_key, result)
    return result
