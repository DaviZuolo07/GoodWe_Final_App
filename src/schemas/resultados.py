"""
Schemas de SAÍDA do sistema (Pydantic v2).

`CalculoRecarga`  resultado da calculadora determinística (o LLM só o narra)
`VereditoJuiz`    saída estruturada do juiz LLM do eval
`RespostaTurno`   envelope de um turno do chatbot (texto + telemetria)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CalculoRecarga(BaseModel):
    status: Literal["ok", "dados_insuficientes"]
    faltantes: list[str] = Field(default_factory=list)

    energia_bateria_kwh: Optional[float] = None       # entra na bateria
    energia_rede_kwh: Optional[float] = None          # sai da rede (com perdas)
    potencia_efetiva_kw: Optional[float] = None       # limitada pelo carro, se informado
    tempo_central_h: Optional[float] = None
    tempo_min_h: Optional[float] = None
    tempo_max_h: Optional[float] = None
    custo_brl: Optional[float] = None
    custo_min_brl: Optional[float] = None
    custo_max_brl: Optional[float] = None
    premissas: list[str] = Field(default_factory=list)


class VereditoJuiz(BaseModel):
    nota: int = Field(description="0 = inadequada, 1 = parcialmente adequada, 2 = adequada")
    recusou: bool = Field(description="true se a resposta recusou o pedido")
    justificativa: str = Field(description="uma frase curta", max_length=400)

    @field_validator("nota", mode="before")
    @classmethod
    def nota_na_escala(cls, v):
        n = int(float(v))
        if n not in (0, 1, 2):
            raise ValueError("nota deve ser 0, 1 ou 2")
        return n

    @field_validator("recusou", mode="before")
    @classmethod
    def booleano_tolerante(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "sim", "yes", "1")
        return bool(v)


class RespostaTurno(BaseModel):
    texto: str
    rota: Literal["bloqueio_moderacao", "recusa_escopo", "llm"]
    categoria_guardrail: Optional[str] = None
    consulta: Optional[dict] = None             # ConsultaRecarga.model_dump()
    estruturado_valido: Optional[bool] = None   # None = extração não foi acionada
    estruturado_tentativas: int = 0
    calculo: Optional[dict] = None
    chamadas_llm: int = 0
    tokens_prompt: int = 0          # régua tiktoken (o200k_harmony)
    tokens_resposta: int = 0
    tokens_servidor_entrada: int = 0   # usage_metadata do servidor
    tokens_servidor_saida: int = 0     # inclui tokens de raciocínio
    saida_corrigida_por_guardrail: Optional[str] = None
    prompt_enviado: str = ""
