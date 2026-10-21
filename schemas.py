"""Esquemas Pydantic del sistema RAG.

Dos niveles:
- SalidaLLM: lo que debe devolver el modelo de lenguaje.
- RespuestaRAG: lo que devuelve get_rag_response(), con referencias reales.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

NO_LO_SE = "No lo sé"


class SalidaLLM(BaseModel):
    """Respuesta del modelo, basada solo en los fragmentos del CONTEXTO."""

    encontrada: bool = Field(
        description="true si la respuesta está en el CONTEXTO; false si no está."
    )
    respuesta: str = Field(
        description=f"La respuesta, usando solo el CONTEXTO. Si no está, exactamente: {NO_LO_SE}"
    )
    fragmentos: list[int] = Field(
        default_factory=list,
        description="Números de los fragmentos del CONTEXTO usados para responder.",
    )

    @field_validator("respuesta")
    @classmethod
    def respuesta_no_vacia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("respuesta no puede estar vacía")
        return valor.strip()

    @field_validator("fragmentos")
    @classmethod
    def fragmentos_validos(cls, valor: list[int]) -> list[int]:
        # Quita números no válidos y repetidos, conservando el orden.
        return list(dict.fromkeys(n for n in valor if n >= 1))

    @model_validator(mode="after")
    def coherencia(self) -> "SalidaLLM":
        # Si la respuesta es "No lo sé", no puede estar "encontrada".
        dice_no_se = self.respuesta.rstrip(".").strip().lower() == NO_LO_SE.lower()
        if dice_no_se:
            self.encontrada = False
        # Si no está en el contexto: respuesta fija y sin fragmentos.
        if not self.encontrada:
            self.respuesta = NO_LO_SE
            self.fragmentos = []
        return self


class Referencia(BaseModel):
    """Un fragmento de los documentos usado para responder."""

    archivo: str
    fragmento: int
    extracto: str


class RespuestaRAG(BaseModel):
    """Resultado final de get_rag_response()."""

    pregunta: str
    respuesta: str
    encontrada: bool
    referencias: list[Referencia] = Field(default_factory=list)
