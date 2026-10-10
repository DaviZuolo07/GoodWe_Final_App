"""
Schemas de SAÍDA do sistema (Pydantic v2).

`CalculoRecarga`  resultado da calculadora determinística (o LLM só o narra)
`RespostaTurno`   envelope de um turno do chatbot (texto + telemetria)
`RespostaRAG`     envelope de um turno do RAG (texto + fontes + verificação da citação)
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


class RespostaRAG(BaseModel):
    texto: str
    rota: Literal["bloqueio_moderacao", "sem_contexto", "recusa_escopo", "recusa_llm", "rag",
                  "apresentacao"]
    categoria_guardrail: Optional[str] = None
    fontes: list[dict] = Field(default_factory=list)      # trechos enviados ao modelo, com score
    descartados: list[dict] = Field(default_factory=list)  # top-k abaixo do limiar
    descartados_por_injecao: list[dict] = Field(default_factory=list)  # trecho com instrução ao modelo
    citacoes: list[str] = Field(default_factory=list)      # "(fonte: doc, página X)" presentes no texto
    citacao_adicionada: bool = False       # o modelo não citou; a chain anexou a do melhor trecho
    citacoes_invalidas: list[str] = Field(default_factory=list)  # citadas mas não recuperadas
    saida_corrigida_por_guardrail: Optional[str] = None
    chamadas_llm: int = 0
    tokens_servidor_entrada: int = 0
    tokens_servidor_saida: int = 0
