from evals.pontuacao import _tem_algum, avaliar, contar_frases, normalizar


def test_termo_curto_isolado():
    assert _tem_algum(normalizar("leva 7h15"), ["h"]) == ["h"]
    assert _tem_algum(normalizar("olá, tudo bem"), ["h"]) == []


def test_contar_frases_v11():
    assert contar_frases("Leva 7.4 h. Aprox. isso.") == 2
    assert contar_frases("Passos:\n- um\n- dois\n- três") == 4


def test_recusa_detectada():
    assert avaliar("Não possuo essa especificação.", {"deve_recusar": True})["conforme"]
