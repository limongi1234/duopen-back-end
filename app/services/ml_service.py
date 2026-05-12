from app.core.config import get_settings
from app.schemas.ml import MLPrediction
import logging

log = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.settings = get_settings()

    async def predict(self, obra_id: str) -> MLPrediction:
        # TODO: implementar modelo preditivo de risco
        log.info(f"Gerando predição para obra {obra_id}")
        return MLPrediction(
            obra_id=obra_id,
            risco_atraso=0.0,
            risco_sobrecusto=0.0,
            score_eficiencia=0.0,
            recomendacoes=[],
        )
