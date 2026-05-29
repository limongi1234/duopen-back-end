from typing import Any, Optional
import logging

from supabase import Client

log = logging.getLogger(__name__)

PREDICOES_TABLE = "predicoes"


class MLService:
    """Leitura das predições de risco geradas pelo modelo (tabela `predicoes`)."""

    def __init__(self, db: Client) -> None:
        self.db = db

    def get_predicao(self, obra_id: str) -> Optional[dict[str, Any]]:
        """Retorna a predição de uma obra, ou ``None`` se não houver."""
        result = (
            self.db.table(PREDICOES_TABLE)
            .select("*")
            .eq("id_obra", obra_id)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None

    def listar_predicoes(
        self, nivel_risco: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Lista todas as predições, opcionalmente filtrando por nível de risco."""
        query = self.db.table(PREDICOES_TABLE).select("*")
        if nivel_risco:
            query = query.eq("nivel_risco", nivel_risco)
        return query.execute().data or []
