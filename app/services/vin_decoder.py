import re

VIN_REGEX = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.I)


def normalize_vin(vin: str) -> str:
    return vin.strip().upper()


def is_valid_vin(vin: str) -> bool:
    vin = normalize_vin(vin)
    return bool(VIN_REGEX.match(vin))


def decode_vin(vin: str) -> dict:
    """
    Implementação stub de decodificação de VIN.
    Retorna campos comuns quando possível. Em produção integrar com provedor comercial.
    """
    vin = normalize_vin(vin)
    if not is_valid_vin(vin):
        return {"error": "invalid_vin"}

    # Stub: extrai ano-modelo aproximado pelo 10º caractere (tabela simplificada)
    year_codes = {
        'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014, 'F': 2015,
        'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019, 'L': 2020, 'M': 2021,
        'N': 2022, 'P': 2023, 'R': 2024, 'S': 2025, 'T': 2026,
    }

    year_char = vin[9]
    year = year_codes.get(year_char, None)

    # Como stub, não decodificamos marca/modelo reais — retorna placeholders
    return {
        "vin": vin,
        "make": None,
        "model": None,
        "year": year,
        "decoded_from": "stub",
    }
