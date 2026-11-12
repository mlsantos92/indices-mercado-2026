from datetime import date, datetime

from zoneinfo import ZoneInfo

from indices.selo import avaliar, dia_util_antes, ultimo_fechamento

BRT = ZoneInfo("America/Sao_Paulo")


def test_ultimo_fechamento_depois_das_18h_e_o_proprio_dia():
    # quarta 11/11/2026 às 19h: pregão de hoje já encerrou
    assert ultimo_fechamento(datetime(2026, 11, 11, 19, 0, tzinfo=BRT)) == date(2026, 11, 11)


def test_ultimo_fechamento_antes_das_18h_e_o_dia_anterior_util():
    # quarta 11/11 às 8h30: último fechamento é terça 10/11
    assert ultimo_fechamento(datetime(2026, 11, 11, 8, 30, tzinfo=BRT)) == date(2026, 11, 10)
    # segunda 09/11 às 10h: último fechamento é sexta 06/11
    assert ultimo_fechamento(datetime(2026, 11, 9, 10, 0, tzinfo=BRT)) == date(2026, 11, 6)


def test_dia_util_antes_pula_fim_de_semana():
    assert dia_util_antes(date(2026, 11, 9)) == date(2026, 11, 6)


def test_verde_com_dados_do_ultimo_dia_util_e_testes_ok():
    esperado = date(2026, 11, 11)
    r = avaliar(date(2026, 11, 11), date(2026, 11, 11), esperado, True)
    assert r["cor"] == "verde"


def test_amarelo_com_dolar_defasado():
    esperado = date(2026, 11, 11)
    r = avaliar(date(2026, 11, 10), date(2026, 11, 10), esperado, True)
    assert r["cor"] == "amarelo"


def test_vermelho_sem_api_ou_com_testes_falhando():
    esperado = date(2026, 11, 11)
    assert avaliar(None, None, esperado, True)["cor"] == "vermelho"
    assert avaliar(date(2026, 11, 11), date(2026, 11, 11), esperado, False)["cor"] == "vermelho"
