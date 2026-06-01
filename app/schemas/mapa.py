from typing import Literal, Optional

from pydantic import BaseModel


class GeoJSONPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]  # [longitude, latitude] — ordem GeoJSON/Leaflet


class ObraProperties(BaseModel):
    id: str
    nome: str
    status: str
    nivel_risco: Optional[str] = None
    secretaria: Optional[str] = None
    bairro: Optional[str] = None
    valor_contrato: float
    percentual_executado: Optional[float] = None
    prob_atraso: Optional[float] = None
    ieop_score: Optional[float] = None
    ieop_classe: Optional[str] = None


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPoint
    properties: ObraProperties


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
