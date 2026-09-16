"""
Execução de chamadas ao modelo, com tolerância a diferenças entre famílias.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Na primeira rodada real do eval, o `gemma4:31b` devolveu string VAZIA em 23 de
23 casos — 8,7% de conformidade e 78 tokens por turno, contra 365 do gpt-oss.
Não era cota, não era rede: o servidor respondia 200 em ~1,6 s e o conteúdo
vinha em branco.

Causa: o parâmetro `think` (o `reasoning=` do ChatOllama). O gpt-oss trata
`think: low` como orçamento de raciocínio e responde normalmente. Outras
famílias, com o mesmo parâmetro, colocam a saída inteira no campo de raciocínio
e devolvem `content` vazio — ou recusam o parâmetro com erro.

O mesmo problema derrubou o juiz: `glm-5.3-flash` levantou ResponseError em
todos os 23 casos, e por isso a coluna "nota ponderada" saiu None.

A CORREÇÃO
----------
Nunca assumir que um parâmetro vale para todos os modelos. Aqui a chamada tenta
com raciocínio; se der erro ou vier vazia, repete UMA vez sem raciocínio e
memoriza a decisão para aquele modelo. Custa uma chamada extra por modelo, uma
única vez na sessão.

Isso vale como um dos "problemas encontrados e soluções" que o §8 exige — com
número antes e depois, que é o que dá peso ao parágrafo.
"""

from src.chain.llm import get_llm

# modelo -> aceita raciocínio? (None = ainda não sabemos)
_ACEITA_RACIOCINIO: dict = {}

# modelo -> lista de eventos, para o relatório
_HISTORICO: dict = {}


def _registrar(modelo: str, evento: str) -> None:
    _HISTORICO.setdefault(modelo, [])
    if evento not in _HISTORICO[modelo]:
        _HISTORICO[modelo].append(evento)


def _texto(resposta) -> str:
    """Extrai o texto de um AIMessage, tolerando conteúdo em blocos."""
    conteudo = getattr(resposta, "content", resposta)
    if isinstance(conteudo, str):
        return conteudo.strip()
    if isinstance(conteudo, list):
        partes = [
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in conteudo
        ]
        return "\n".join(p for p in partes if p).strip()
    return str(conteudo or "").strip()


def invocar(
    mensagens,
    *,
    model: str | None = None,
    papel: str = "principal",
    perfil: str = "redator",
    reasoning=None,
    **kwargs,
) -> str:
    """
    Chama o modelo e devolve texto. Nunca devolve None.

    `mensagens` pode ser string, lista de dicts {role, content} ou lista de
    mensagens do LangChain — o ChatOllama aceita as três.
    """
    from src.chain.llm import nome_do_modelo

    nome = model or nome_do_modelo(papel)
    aceita = _ACEITA_RACIOCINIO.get(nome)

    # Chamador pode desligar o raciocínio explicitamente (o juiz faz isso).
    if reasoning is False:
        _ACEITA_RACIOCINIO.setdefault(nome, False)
        aceita = False

    # --- primeira tentativa: com raciocínio, salvo se já sabemos que não vai -
    if aceita is not False:
        try:
            llm = get_llm(perfil=perfil, model=nome, reasoning=reasoning, **kwargs)
            saida = _texto(llm.invoke(mensagens))
            if saida:
                if aceita is None:
                    _ACEITA_RACIOCINIO[nome] = True
                return saida
            _registrar(nome, "resposta vazia com raciocinio ligado")
        except Exception as e:
            _registrar(nome, f"erro com raciocinio: {type(e).__name__}: {str(e)[:150]}")

    # --- segunda tentativa: sem raciocínio ---------------------------------
    try:
        llm = get_llm(perfil=perfil, model=nome, reasoning=False, **kwargs)
        saida = _texto(llm.invoke(mensagens))
        if saida:
            if aceita is not False:
                _ACEITA_RACIOCINIO[nome] = False
                _registrar(nome, "funciona apenas SEM raciocinio")
            return saida
        _registrar(nome, "resposta vazia tambem sem raciocinio")
        return ""
    except Exception as e:
        _registrar(nome, f"erro sem raciocinio: {type(e).__name__}: {str(e)[:150]}")
        raise


def relatorio_compatibilidade() -> dict:
    """O que descobrimos sobre cada modelo — material direto para o §8."""
    return {
        "aceita_raciocinio": dict(_ACEITA_RACIOCINIO),
        "eventos": dict(_HISTORICO),
    }