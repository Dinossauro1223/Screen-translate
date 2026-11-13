"""Fase 3.2 / teste 2 — D37: o pedido ao Windows para tirar o overlay da captura e o teste A/B que confere se funcionou."""
from __future__ import annotations

import numpy as np
import pytest

import exclusao_da_captura as ex

BUILD_ATUAL = (10, 0, 22631)


def api_com(retorno=1, levanta=None):
    chamadas = []

    def funcao(hwnd, modo):
        chamadas.append((hwnd, modo))
        if levanta is not None:
            raise levanta
        return retorno

    return type("Usuario", (), {"SetWindowDisplayAffinity": staticmethod(funcao)})(), chamadas


# --------------------------------------------------------------------------- a chamada ao Windows
def test_pede_wda_excludefromcapture_para_a_janela_certa():
    api, chamadas = api_com(1)
    r = ex.excluir_da_captura(12345, api=api, windows=True, versao=BUILD_ATUAL)
    assert r.aplicada and r.metodo == ex.METODO_DA_API and chamadas == [(12345, 0x11)] and r.motivo == ""


def test_o_valor_da_constante_e_o_do_windows():
    assert ex.WDA_EXCLUDEFROMCAPTURE == 0x11 and ex.BUILD_MINIMO == 19041


def test_windows_recusando_devolve_o_codigo_de_erro():
    api, _ = api_com(0)
    r = ex.excluir_da_captura(1, api=api, windows=True, versao=BUILD_ATUAL, ultimo_erro=lambda: 87)
    assert not r.aplicada and r.codigo_de_erro == 87 and "erro 87" in r.motivo and r.metodo == "nenhum"


@pytest.mark.parametrize("build", [10240, 18363, 19040])
def test_windows_anterior_a_2004_nem_tenta(build):
    api, chamadas = api_com(1)
    r = ex.excluir_da_captura(1, api=api, windows=True, versao=(10, 0, build))
    assert not r.aplicada and chamadas == [] and f"build {build}" in r.motivo and "19041" in r.motivo


@pytest.mark.parametrize("build", [19041, 19045, 22000, 26100])
def test_windows_10_2004_ou_mais_novo_tenta(build):
    api, chamadas = api_com(1)
    assert ex.excluir_da_captura(1, api=api, windows=True, versao=(10, 0, build)).aplicada and len(chamadas) == 1


def test_fora_do_windows_nao_existe_e_nao_chama_nada():
    api, chamadas = api_com(1)
    r = ex.excluir_da_captura(1, api=api, windows=False)
    assert not r.aplicada and chamadas == [] and "não é o Windows" in r.motivo


@pytest.mark.parametrize("erro", [OSError("sem acesso"), AttributeError("x"), TypeError("tipo"), ValueError("valor")])
def test_excecao_da_api_vira_resultado_e_nunca_sobe(erro):
    api, _ = api_com(levanta=erro)
    r = ex.excluir_da_captura(1, api=api, windows=True, versao=BUILD_ATUAL)
    assert not r.aplicada and type(erro).__name__ in r.motivo


def test_api_sem_a_funcao_e_explicada():
    r = ex.excluir_da_captura(1, api=object(), windows=True, versao=BUILD_ATUAL)
    assert not r.aplicada and "não existe" in r.motivo


def test_a_versao_do_windows_e_none_fora_do_windows_ou_uma_tripla():
    versao = ex.versao_do_windows()
    assert versao is None or len(versao) == 3


# --------------------------------------------------------------------------- medir o marcador
def amostra(bgr, lado=4):
    img = np.zeros((lado, lado, 4), np.uint8)
    img[..., :3] = bgr
    return img


def test_fracao_do_marcador():
    assert ex.fracao_do_marcador(amostra((255, 0, 255))) == 1.0
    assert ex.fracao_do_marcador(amostra((200, 200, 200))) == 0.0
    assert ex.fracao_do_marcador(amostra((230, 20, 240))) == 1.0                       # dentro da tolerância
    metade = amostra((255, 0, 255))
    metade[:2, :, :3] = (0, 0, 0)
    assert ex.fracao_do_marcador(metade) == pytest.approx(0.5)
    assert ex.fracao_do_marcador(np.zeros((0, 0, 4), np.uint8)) == 0.0


# --------------------------------------------------------------------------- o teste A/B
class Cenario:
    """Um 'overlay' que o teste A/B controla: o marcador aparece na captura conforme o cenário."""

    def __init__(self, *, aparece_sem_protecao=True, aceita=True, some_ao_excluir=True, some_com_opacidade=True, some_ao_esconder=True):
        self.aparece_sem_protecao = aparece_sem_protecao
        self.exclusao_aceita, self.some_ao_excluir = aceita, some_ao_excluir
        self.some_com_opacidade, self.some_ao_esconder = some_com_opacidade, some_ao_esconder
        self.marcador = False
        self.excluida = False
        self.oculto: str | None = None
        self.eventos: list[str] = []

    def mostrar_marcador(self, ativo):
        self.marcador = ativo
        self.eventos.append(f"marcador={ativo}")

    def aplicar(self):
        self.eventos.append("exclusao")
        if self.exclusao_aceita:
            self.excluida = True
            return ex.ResultadoDaExclusao(True, ex.METODO_DA_API)
        return ex.ResultadoDaExclusao(False, "nenhum", "o Windows recusou o pedido (erro 5)", 5)

    def ocultar(self, metodo):
        self.eventos.append(f"ocultar_{metodo}")
        self.oculto = metodo

    def restaurar(self, metodo):
        self.eventos.append(f"restaurar_{metodo}")
        self.oculto = None

    def visivel_na_captura(self):
        if not self.marcador or not self.aparece_sem_protecao:
            return False
        if self.excluida and self.some_ao_excluir:
            return False
        if self.oculto == "opacidade" and self.some_com_opacidade:
            return False
        return not (self.oculto == "esconder" and self.some_ao_esconder)

    def amostrar(self):
        return amostra((255, 0, 255)) if self.visivel_na_captura() else amostra((200, 200, 200))


def verificar(cenario):
    esperas = []
    v = ex.verificar_exclusao(mostrar_marcador=cenario.mostrar_marcador, capturar_amostra=cenario.amostrar, aplicar_exclusao=cenario.aplicar,
                              ocultar=cenario.ocultar, restaurar=cenario.restaurar, esperar=esperas.append)
    return v, esperas


def test_ab_caminho_feliz_a_exclusao_vale():
    c = Cenario()
    v, esperas = verificar(c)
    assert (v.estado, v.estrategia, v.protegida) == ("eficaz", "excluida", True)
    assert v.medidas == {"controle": 1.0, "com_exclusao": 0.0} and esperas == [ex.ESPERA_PADRAO, ex.ESPERA_PADRAO]
    assert c.eventos == ["marcador=True", "exclusao", "marcador=False"]            # o marcador é sempre apagado no fim


def test_ab_o_windows_aceita_mas_a_janela_continua_na_captura_cai_para_esconder():
    v, _ = verificar(Cenario(some_ao_excluir=False))
    assert (v.estado, v.estrategia) == ("ineficaz", "ocultar_opacidade") and "continua aparecendo" in v.motivo
    assert v.medidas["com_exclusao"] == 1.0 and v.medidas["oculto_opacidade"] == 0.0


def test_ab_windows_antigo_nao_suporta_e_a_opacidade_resolve():
    c = Cenario(aceita=False)
    v, _ = verificar(c)
    assert (v.estado, v.estrategia) == ("nao_suportado", "ocultar_opacidade") and "erro 5" in v.motivo
    assert c.eventos == ["marcador=True", "exclusao", "ocultar_opacidade", "restaurar_opacidade", "marcador=False"]


def test_ab_se_a_opacidade_nao_tira_da_captura_usa_hide():
    """Como no X11 sem compositor: a opacidade não tem efeito, esconder resolve."""
    c = Cenario(aceita=False, some_com_opacidade=False)
    v, _ = verificar(c)
    assert (v.estado, v.estrategia) == ("nao_suportado", "ocultar_esconder")
    assert c.eventos[-3:] == ["ocultar_esconder", "restaurar_esconder", "marcador=False"] and "restaurar_opacidade" in c.eventos


def test_ab_nenhuma_estrategia_funciona_e_o_resultado_diz_sem_protecao():
    v, _ = verificar(Cenario(aceita=False, some_com_opacidade=False, some_ao_esconder=False))
    assert (v.estado, v.estrategia, v.protegida) == ("nao_suportado", "sem_protecao", False) and "esconder o overlay também não" in v.motivo


def test_ab_controle_que_falha_com_pedido_aceito_e_inconclusivo_mas_confia_no_pedido():
    v, esperas = verificar(Cenario(aparece_sem_protecao=False))
    assert (v.estado, v.estrategia) == ("inconclusivo", "excluida") and "não deu para conferir" in v.motivo
    assert esperas == [ex.ESPERA_PADRAO, ex.ESPERA_PADRAO + 0.5] and "controle_2" in v.medidas       # tentou de novo com mais espera


def test_ab_controle_que_falha_e_pedido_recusado_ainda_tenta_esconder_e_nao_afirma_nada():
    v, _ = verificar(Cenario(aparece_sem_protecao=False, aceita=False))
    assert v.estado == "nao_suportado" and v.estrategia in ("ocultar_opacidade", "ocultar_esconder", "sem_protecao")


def test_ab_controle_que_so_aparece_na_segunda_tentativa_continua_valendo():
    tentativas = {"n": 0}
    c = Cenario()

    def amostrar():
        tentativas["n"] += 1
        return amostra((200, 200, 200)) if tentativas["n"] == 1 else c.amostrar()

    v = ex.verificar_exclusao(mostrar_marcador=c.mostrar_marcador, capturar_amostra=amostrar, aplicar_exclusao=c.aplicar, ocultar=c.ocultar,
                              restaurar=c.restaurar, esperar=lambda s: None)
    assert v.estado == "eficaz" and v.medidas["controle"] == 0.0 and v.medidas["controle_2"] == 1.0


def test_ab_apaga_o_marcador_mesmo_se_a_captura_falhar():
    c = Cenario(aceita=False)

    def quebra():
        raise RuntimeError("captura falhou")

    with pytest.raises(RuntimeError):
        ex.verificar_exclusao(mostrar_marcador=c.mostrar_marcador, capturar_amostra=quebra, aplicar_exclusao=c.aplicar, ocultar=c.ocultar,
                              restaurar=c.restaurar, esperar=lambda s: None)
    assert c.marcador is False


def test_ab_restaura_o_overlay_se_a_captura_falhar_no_meio_do_teste_de_esconder():
    c = Cenario(aceita=False)

    def amostrar():
        if c.oculto:
            raise RuntimeError("falhou escondido")
        return c.amostrar()

    with pytest.raises(RuntimeError):
        ex.verificar_exclusao(mostrar_marcador=c.mostrar_marcador, capturar_amostra=amostrar, aplicar_exclusao=c.aplicar, ocultar=c.ocultar,
                              restaurar=c.restaurar, esperar=lambda s: None)
    assert c.oculto is None and c.marcador is False


def test_protegida_e_falsa_so_quando_nao_ha_estrategia():
    assert ex.Verificacao("eficaz", "excluida").protegida and ex.Verificacao("ineficaz", "ocultar_esconder").protegida
    assert not ex.Verificacao("nao_suportado", "sem_protecao").protegida
