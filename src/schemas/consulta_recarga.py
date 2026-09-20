"""
Schema Pydantic v2 do domínio EV (Aula 03).

`ConsultaRecarga` é o contrato entre o que o LLM EXTRAI da conversa e o que o
código CALCULA. O modelo nunca faz conta: ele só preenche este formulário, o
Pydantic valida, e a calculadora determinística (`src/dominio/recarga.py`)
produz os números. Isso elimina a classe de erro mais cara de um assistente de
recarga: aritmética alucinada.

Os `field_validator` resolvem problemas reais do português do Brasil que um
`json.loads` puro não resolve — e que derrubavam a extração manual da Sprint 2:

    "7,4"        -> 7.4        (vírgula decimal)
    "7,4 kW"     -> 7.4        (unidade grudada)
    "80%"        -> 80.0
    "R$ 2,10"    -> 2.1
    "1.234,5"    -> 1234.5     (milhar com ponto)
    "livre"      -> "disponivel"
    "alternada"  -> "AC"
"""

from __future__ import annotations

import re
import unicodedata
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intencao = Literal[
    "estimativa_tempo",     # quanto tempo para carregar
    "estimativa_custo",     # quanto vou pagar
    "estado_carregador",    # está livre? está em falha?
    "faturamento",          # como é cobrado, valor na conta
    "conceitual",           # AC x DC, kW x kWh, curva de carga...
    "outro",
]

EstadoCarregador = Literal["disponivel", "ocupado", "reservado", "offline", "falha"]

_SINONIMOS_ESTADO = {
    "disponivel": "disponivel", "livre": "disponivel", "desocupado": "disponivel",
    "vago": "disponivel", "ocioso": "disponivel",
    "ocupado": "ocupado", "em uso": "ocupado", "em_uso": "ocupado",
    "carregando": "ocupado", "sendo usado": "ocupado",
    "reservado": "reservado", "agendado": "reservado", "fila": "reservado",
    "offline": "offline", "desligado": "offline", "sem conexao": "offline",
    "desconectado": "offline", "fora do ar": "offline",
    "falha": "falha", "erro": "falha", "defeito": "falha", "quebrado": "falha",
    "com problema": "falha", "alarme": "falha",
}

_RE_NUMERO = re.compile(r"-?\d+(?:[.,]\d+)*")


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def numero_br(valor) -> Optional[float]:
    """
    Converte número em formato brasileiro/misto para float.

    Regra de desambiguação (a mesma das planilhas pt-BR):
      - vírgula presente  -> vírgula é decimal, pontos são milhar ("1.234,5")
      - só ponto, e o grupo após o último ponto tem 3 dígitos e há mais de um
        ponto -> milhar ("1.234.567"); senão ponto é decimal ("7.4")
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().lower()
    if texto in ("", "null", "none", "nao informado", "não informado", "n/a", "-", "?"):
        return None
    achado = _RE_NUMERO.search(texto)
    if not achado:
        return None
    bruto = achado.group(0)
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    elif bruto.count(".") > 1:
        bruto = bruto.replace(".", "")
    return float(bruto)


class ConsultaRecarga(BaseModel):
    """Parâmetros de uma consulta de recarga, extraídos da conversa pelo LLM."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    intencao: Intencao = Field(
        "outro",
        description="Objetivo principal da mensagem do usuário.",
    )
    capacidade_bateria_kwh: Optional[float] = Field(
        None, gt=0, le=250,
        description="Capacidade TOTAL da bateria do veículo em kWh. null se o usuário não informou.",
    )
    soc_atual_pct: Optional[float] = Field(
        None, ge=0, le=100,
        description="Nível atual da bateria em porcentagem (0-100). null se não informado.",
    )
    soc_alvo_pct: Optional[float] = Field(
        None, ge=0, le=100,
        description="Nível desejado ao fim da recarga em porcentagem (0-100). "
                    "null se não informado; use 100 só se o usuário disser 'completa' ou 'cheia'.",
    )
    potencia_carregador_kw: Optional[float] = Field(
        None, gt=0, le=400,
        description="Potência nominal do carregador em kW. null se não informada.",
    )
    potencia_max_ac_veiculo_kw: Optional[float] = Field(
        None, gt=0, le=22,
        description="Potência máxima que o carregador de bordo do VEÍCULO aceita em AC, em kW. "
                    "null se não informada.",
    )
    tarifa_kwh_brl: Optional[float] = Field(
        None, gt=0, le=10,
        description="Tarifa em reais por kWh. null se o usuário não informou (NUNCA estime).",
    )
    energia_entregue_kwh: Optional[float] = Field(
        None, ge=0, le=250,
        description="Energia já entregue/consumida numa sessão, em kWh. null se não informada.",
    )
    estado_carregador: Optional[EstadoCarregador] = Field(
        None,
        description="Estado do carregador SE o usuário o descreveu: disponivel, ocupado, "
                    "reservado, offline ou falha. null caso contrário.",
    )
    tipo_corrente: Optional[Literal["AC", "DC"]] = Field(
        None, description="AC (alternada, wallbox) ou DC (contínua, rápido). null se não dito.",
    )
    modelo_carregador: Optional[str] = Field(
        None, max_length=60,
        description="Modelo do carregador citado pelo usuário, exatamente como escrito. null se nenhum.",
    )
    confianca: float = Field(
        0.5, ge=0, le=1,
        description="Confiança da extração, de 0 a 1.",
    )

    # ------------------------------------------------------------------ #
    # field_validators (Aula 03) — rodam ANTES da checagem de tipo/faixa
    # ------------------------------------------------------------------ #
    @field_validator(
        "capacidade_bateria_kwh", "soc_atual_pct", "soc_alvo_pct",
        "potencia_carregador_kw", "potencia_max_ac_veiculo_kw",
        "tarifa_kwh_brl", "energia_entregue_kwh",
        mode="before",
    )
    @classmethod
    def normalizar_numero_br(cls, v):
        return numero_br(v)

    @field_validator("soc_atual_pct", "soc_alvo_pct", mode="after")
    @classmethod
    def arredondar_percentual(cls, v):
        # 0,1 ponto percentual já é abaixo da resolução de qualquer BMS de VE.
        return None if v is None else round(v, 1)

    @field_validator("estado_carregador", mode="before")
    @classmethod
    def normalizar_estado(cls, v):
        if v is None:
            return None
        chave = _sem_acento(str(v)).strip().lower()
        if chave in ("", "null", "none"):
            return None
        return _SINONIMOS_ESTADO.get(chave, chave)   # valor desconhecido -> Literal acusa

    @field_validator("tipo_corrente", mode="before")
    @classmethod
    def normalizar_corrente(cls, v):
        if v is None:
            return None
        chave = _sem_acento(str(v)).strip().lower()
        if chave in ("", "null", "none"):
            return None
        if chave.startswith(("ac", "alternada", "corrente alternada")):
            return "AC"
        if chave.startswith(("dc", "continua", "corrente continua", "rapido")):
            return "DC"
        return chave.upper()

    @field_validator("intencao", mode="before")
    @classmethod
    def normalizar_intencao(cls, v):
        return "outro" if v in (None, "", "null") else _sem_acento(str(v)).strip().lower()

    @field_validator("confianca", mode="before")
    @classmethod
    def normalizar_confianca(cls, v):
        n = numero_br(v)
        if n is None:
            return 0.5
        return n / 100 if n > 1 else n     # "85%" ou 85 -> 0.85

    # ------------------------------------------------------------------ #
    # Regra entre campos (Pydantic v2: model_validator)
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def alvo_maior_que_atual(self):
        if (self.soc_atual_pct is not None and self.soc_alvo_pct is not None
                and self.soc_alvo_pct <= self.soc_atual_pct):
            raise ValueError(
                f"soc_alvo_pct ({self.soc_alvo_pct}) deve ser maior que "
                f"soc_atual_pct ({self.soc_atual_pct})"
            )
        return self

    # ------------------------------------------------------------------ #
    # Derivados (não vêm do LLM — são calculados)
    # ------------------------------------------------------------------ #
    CAMPOS_FATO: ClassVar[tuple[str, ...]] = (
        "capacidade_bateria_kwh", "soc_atual_pct", "soc_alvo_pct",
        "potencia_carregador_kw", "potencia_max_ac_veiculo_kw", "tarifa_kwh_brl",
        "energia_entregue_kwh", "estado_carregador", "tipo_corrente", "modelo_carregador",
    )

    def fatos(self) -> dict:
        """Só os campos factuais preenchidos (sem intenção/confiança)."""
        return {k: getattr(self, k) for k in self.CAMPOS_FATO if getattr(self, k) is not None}

    def faltantes_para_tempo(self) -> list[str]:
        exigidos = {
            "capacidade_bateria_kwh": "capacidade da bateria (kWh)",
            "soc_atual_pct": "nível atual da bateria (%)",
            "soc_alvo_pct": "nível desejado (%)",
            "potencia_carregador_kw": "potência do carregador (kW)",
        }
        return [rotulo for campo, rotulo in exigidos.items() if getattr(self, campo) is None]


def mesclar_fatos(antigos: dict, novos: dict) -> dict:
    """
    Política de memória de fatos: o valor mais recente vence, mas um campo
    que o usuário não repetiu NÃO é apagado. É isso que deixa "minha bateria é
    de 60 kWh" (turno 1) disponível para a conta do turno 5, mesmo depois de a
    mensagem do turno 1 ter saído da janela de tokens.
    """
    mesclado = dict(antigos or {})
    mesclado.update({k: v for k, v in (novos or {}).items() if v is not None})
    # Uma nova meta inconsistente com o nível atual antigo invalida o par.
    atual, alvo = mesclado.get("soc_atual_pct"), mesclado.get("soc_alvo_pct")
    if atual is not None and alvo is not None and alvo <= atual:
        if "soc_atual_pct" in (novos or {}):
            mesclado.pop("soc_alvo_pct", None)
        else:
            mesclado.pop("soc_atual_pct", None)
    return mesclado


def instrucoes_compactas(modelo: type[BaseModel] = ConsultaRecarga) -> str:
    """
    Instrução de formato gerada do MESMO schema, em ~1/4 dos tokens.

    `PydanticOutputParser.get_format_instructions()` despeja o JSON Schema
    inteiro (títulos, exemplo em inglês, chaves aninhadas): 1.060 tokens para
    este modelo. Aqui cada campo vira uma linha "nome: tipo — descrição". O
    parse e a validação continuam 100% com o PydanticOutputParser; só o texto
    que vai ao modelo encolheu. Medição em prompts/README.md.
    """
    schema = modelo.model_json_schema()
    linhas = ["Um único objeto JSON com exatamente estas chaves:"]
    for nome, prop in schema["properties"].items():
        opcoes = prop.get("anyOf", [prop])
        tipos, enum = [], None
        for o in opcoes:
            if "enum" in o:
                enum = o["enum"]
            elif "const" in o:
                enum = [o["const"]]
            elif o.get("type"):
                tipos.append({"number": "número", "string": "texto", "null": "null",
                              "integer": "inteiro", "boolean": "booleano"}.get(o["type"], o["type"]))
        if enum:
            tipos = [" | ".join(f'"{e}"' for e in enum)] + [t for t in tipos if t == "null"]
        faixa = []
        for o in opcoes:
            for chave, simb in (("exclusiveMinimum", ">"), ("minimum", ">="),
                                ("maximum", "<="), ("exclusiveMaximum", "<")):
                if chave in o:
                    faixa.append(f"{simb}{o[chave]:g}")
        tipo = " ou ".join(dict.fromkeys(tipos)) + (f" ({', '.join(faixa)})" if faixa else "")
        linhas.append(f'- "{nome}": {tipo} — {prop.get("description", "")}')
    return "\n".join(linhas)
