from pydantic import BaseModel, Field
from typing import Optional, List, Any


class LookupRequest(BaseModel):
    identifier: str = Field(..., description="VIN (17 chars) ou RENAVAM")
    type: str = Field(..., description="'vin' ou 'renavam'")

    class Config:
        schema_extra = {
            "example": {"identifier": "9BWZZZ377VT004251", "type": "vin"}
        }


class Valuation(BaseModel):
    Valor: Optional[str]
    Marca: Optional[str]
    Modelo: Optional[str]
    AnoModelo: Optional[str]
    Combustivel: Optional[str]


class LookupResponse(BaseModel):
    identifier: str
    type: str
    decoded: Optional[Any]
    valuation: Optional[Any]
    claims: List[Any] = []
    auctions: List[Any] = []
