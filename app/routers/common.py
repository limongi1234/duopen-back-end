"""Dependências compartilhadas dos routers."""
from dataclasses import dataclass
from datetime import date
from typing import Optional

from fastapi import HTTPException, Query


def _parse_data(valor: Optional[str], campo: str) -> Optional[date]:
    # Tolera string vazia (o frontend envia `data_fim=` quando não há filtro).
    if valor is None or not valor.strip():
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo} inválido: use YYYY-MM-DD")


@dataclass
class Periodo:
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None


def get_periodo(
    data_inicio: Optional[str] = Query(None, description="Início do período (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Fim do período (YYYY-MM-DD)"),
) -> Periodo:
    """Recorte por período resiliente: aceita ausência **ou string vazia** (-> None)."""
    return Periodo(
        data_inicio=_parse_data(data_inicio, "data_inicio"),
        data_fim=_parse_data(data_fim, "data_fim"),
    )
