"""Geometria da tela: retângulos, monitores, área de trabalho virtual, validação de regiões e conversão entre coordenadas.

Dois espaços de coordenadas aparecem no Windows:
  * FÍSICO  pixels reais da tela: é o que o mss captura e o que o OCR enxerga;
  * LÓGICO  pixels "independentes de densidade" do Qt, quando a escala do Qt está ligada (125%, 150%...).

O programa força o Qt a trabalhar em pixels FÍSICOS (geo.dpi), e então os dois espaços coincidem. Este módulo existe para
(1) validar regiões antes de capturar e (2) converter por monitor se, mesmo assim, o Qt reportar outra escala.
Nada aqui importa Qt, mss nem ctypes.

Convenções: retângulo = (esquerda, topo, largura, altura) em inteiros; a borda direita/inferior é EXCLUSIVA (como no mss e no Qt
moderno); coordenadas podem ser NEGATIVAS (monitor à esquerda ou acima do principal).
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

BBox = tuple[float, float, float, float]
ESCALAS_COMUNS = (1.0, 1.25, 1.5, 1.75, 2.0)


def arredondar(valor: float) -> int:
    """Arredonda metade para cima (e não 'para o par'), para que 0,5 e 1,5 se comportem do mesmo jeito."""
    return math.floor(valor + 0.5)


class ErroDeRegiao(ValueError):
    """Região que não pode ser capturada. 'codigo': vazia | pequena_demais | fora_da_tela | monitor_removido | sem_monitores."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


class ErroDeMonitores(RuntimeError):
    """Os monitores vistos pelo Qt e pela captura não correspondem: não dá para garantir onde o overlay vai aparecer."""


@dataclass(frozen=True)
class Retangulo:
    esquerda: int
    topo: int
    largura: int
    altura: int

    def __post_init__(self) -> None:
        for nome in ("esquerda", "topo", "largura", "altura"):
            valor = getattr(self, nome)
            if isinstance(valor, bool) or not isinstance(valor, int):
                raise TypeError(f"{nome} precisa ser um inteiro, veio {valor!r}")
        if self.largura < 0 or self.altura < 0:
            raise ValueError(f"largura e altura não podem ser negativas: {self.largura}x{self.altura}")

    @classmethod
    def de_cantos(cls, x1: int, y1: int, x2: int, y2: int) -> Retangulo:
        """Aceita os cantos em qualquer ordem (arrastar para a esquerda ou para cima)."""
        return cls(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    @property
    def direita(self) -> int:
        return self.esquerda + self.largura

    @property
    def base(self) -> int:
        return self.topo + self.altura

    @property
    def area(self) -> int:
        return self.largura * self.altura

    @property
    def vazio(self) -> bool:
        return self.largura == 0 or self.altura == 0

    def cantos(self) -> tuple[int, int, int, int]:
        return (self.esquerda, self.topo, self.direita, self.base)

    def contem_ponto(self, x: float, y: float) -> bool:
        return self.esquerda <= x < self.direita and self.topo <= y < self.base

    def contem(self, outro: Retangulo) -> bool:
        return (outro.esquerda >= self.esquerda and outro.topo >= self.topo
                and outro.direita <= self.direita and outro.base <= self.base)

    def intersecao(self, outro: Retangulo) -> Retangulo | None:
        esquerda, topo = max(self.esquerda, outro.esquerda), max(self.topo, outro.topo)
        direita, base = min(self.direita, outro.direita), min(self.base, outro.base)
        if direita <= esquerda or base <= topo:
            return None
        return Retangulo(esquerda, topo, direita - esquerda, base - topo)


@dataclass(frozen=True)
class Monitor:
    indice: int
    fisico: Retangulo
    logico: Retangulo | None = None   # só quando o Qt trabalha em pixels lógicos (escala ligada)
    escala: float = 1.0
    principal: bool = False
    nome: str = ""

    def __post_init__(self) -> None:
        if self.fisico.vazio:
            raise ValueError(f"monitor {self.indice} sem área: {self.fisico}")
        if self.logico is not None and self.logico.vazio:
            raise ValueError(f"monitor {self.indice} sem área lógica: {self.logico}")
        if not self.escala > 0:
            raise ValueError(f"escala inválida: {self.escala}")

    @property
    def logico_efetivo(self) -> Retangulo:
        return self.logico if self.logico is not None else self.fisico


def _area_da_uniao(retangulos: Sequence[Retangulo]) -> int:
    """Área coberta pela união (sem contar duas vezes a sobreposição, como em monitores espelhados)."""
    if not retangulos:
        return 0
    xs = sorted({r.esquerda for r in retangulos} | {r.direita for r in retangulos})
    total = 0
    for x0, x1 in zip(xs, xs[1:], strict=False):
        coberto, fim = 0, None
        for topo, base in sorted((r.topo, r.base) for r in retangulos if r.esquerda <= x0 and r.direita >= x1):
            if fim is None or topo >= fim:
                coberto += base - topo
                fim = base
            elif base > fim:
                coberto += base - fim
                fim = base
        total += coberto * (x1 - x0)
    return total


class AreaDeTrabalho:
    """A 'mesa' virtual formada por todos os monitores, em pixels físicos."""

    def __init__(self, monitores: Iterable[Monitor]) -> None:
        self.monitores: tuple[Monitor, ...] = tuple(monitores)
        if not self.monitores:
            raise ErroDeRegiao("sem_monitores", "Nenhum monitor foi encontrado.")
        esquerda = min(m.fisico.esquerda for m in self.monitores)
        topo = min(m.fisico.topo for m in self.monitores)
        self.fisico = Retangulo(esquerda, topo, max(m.fisico.direita for m in self.monitores) - esquerda,
                                max(m.fisico.base for m in self.monitores) - topo)

    @property
    def principal(self) -> Monitor:
        for monitor in self.monitores:
            if monitor.principal:
                return monitor
        for monitor in self.monitores:
            if monitor.fisico.esquerda == 0 and monitor.fisico.topo == 0:
                return monitor
        return self.monitores[0]

    def monitor_em(self, x: float, y: float) -> Monitor | None:
        return next((m for m in self.monitores if m.fisico.contem_ponto(x, y)), None)

    def monitores_que_cruzam(self, regiao: Retangulo) -> list[Monitor]:
        return [m for m in self.monitores if m.fisico.intersecao(regiao) is not None]

    def cobertura(self, regiao: Retangulo) -> float:
        """Fração da região que está sobre algum monitor (o resto é 'buraco' do layout ou fora da mesa)."""
        if regiao.vazio:
            return 0.0
        partes = [p for p in (m.fisico.intersecao(regiao) for m in self.monitores) if p is not None]
        return _area_da_uniao(partes) / regiao.area


def validar_regiao(regiao: Retangulo, area: AreaDeTrabalho, minimo: int = 1, *, recortar: bool = False,
                   cobertura_minima: float = 0.5) -> Retangulo:
    """Devolve a região a capturar ou levanta ErroDeRegiao explicando o motivo.

    recortar=False (captura): a região precisa caber INTEIRA na área de trabalho. Recortar mudaria a origem da imagem e
    deslocaria o overlay, então quem captura prefere falhar a capturar um pedaço diferente do pedido.
    recortar=True (depois de marcar a área): tira o excesso e devolve o que sobrou."""
    x1, y1, x2, y2 = regiao.cantos()
    pedido = f"{regiao.largura}x{regiao.altura} em ({x1}, {y1})"
    if regiao.vazio:
        raise ErroDeRegiao("vazia", f"A região {pedido} tem largura ou altura zero.")
    resultado = regiao
    if not area.fisico.contem(regiao):
        recortada = regiao.intersecao(area.fisico)
        if recortada is None:
            raise ErroDeRegiao("fora_da_tela", f"A região {pedido} está fora da área de trabalho "
                                               f"({area.fisico.largura}x{area.fisico.altura} em ({area.fisico.esquerda}, {area.fisico.topo})).")
        if not recortar:
            raise ErroDeRegiao("fora_da_tela", f"A região {pedido} passa dos limites da área de trabalho "
                                               f"({area.fisico.largura}x{area.fisico.altura} em ({area.fisico.esquerda}, {area.fisico.topo})).")
        resultado = recortada
    if resultado.largura < minimo or resultado.altura < minimo:
        raise ErroDeRegiao("pequena_demais", f"A região {resultado.largura}x{resultado.altura} é menor que o mínimo de {minimo}x{minimo} pixels.")
    if area.cobertura(resultado) < cobertura_minima:
        raise ErroDeRegiao("fora_da_tela", f"A região {pedido} está quase toda fora dos monitores (cai num espaço vazio entre eles).")
    return resultado


def reposicionar(regiao: Retangulo, antiga: AreaDeTrabalho, nova: AreaDeTrabalho, minimo: int = 1) -> Retangulo:
    """Leva a região para o novo layout depois de trocar de monitor, mudar a resolução ou plugar/desplugar telas.

    O monitor é reconhecido pelo nome (ou, sem nome, pelo índice); a posição relativa dentro dele é mantida."""
    cruzam = antiga.monitores_que_cruzam(regiao)
    origem = antiga.monitor_em(*_centro(regiao)) or (cruzam[0] if cruzam else None)
    if origem is None:
        raise ErroDeRegiao("fora_da_tela", "A região não estava sobre nenhum monitor no layout anterior.")
    destino = next((m for m in nova.monitores if (origem.nome and m.nome == origem.nome) or (not origem.nome and m.indice == origem.indice)), None)
    if destino is None:
        raise ErroDeRegiao("monitor_removido", f"O monitor {origem.nome or origem.indice} onde a região estava não existe mais.")
    o, d = origem.fisico, destino.fisico
    x1 = d.esquerda + arredondar((regiao.esquerda - o.esquerda) * d.largura / o.largura)
    y1 = d.topo + arredondar((regiao.topo - o.topo) * d.altura / o.altura)
    x2 = d.esquerda + arredondar((regiao.direita - o.esquerda) * d.largura / o.largura)
    y2 = d.topo + arredondar((regiao.base - o.topo) * d.altura / o.altura)
    return validar_regiao(Retangulo.de_cantos(x1, y1, x2, y2), nova, minimo, recortar=True)


def _centro(regiao: Retangulo) -> tuple[int, int]:
    return (regiao.esquerda + regiao.largura // 2, regiao.topo + regiao.altura // 2)


# --------------------------------------------------------------------------- conversão lógico <-> físico (por monitor)
def _distancia2(retangulo: Retangulo, x: float, y: float) -> float:
    dx = max(retangulo.esquerda - x, 0, x - (retangulo.direita - 1))
    dy = max(retangulo.topo - y, 0, y - (retangulo.base - 1))
    return dx * dx + dy * dy


def _monitor_mais_proximo(monitores: Sequence[Monitor], x: float, y: float, *, logico: bool) -> Monitor:
    def espaco(m: Monitor) -> Retangulo:
        return m.logico_efetivo if logico else m.fisico

    return min(monitores, key=lambda m: _distancia2(espaco(m), x, y))


def _mapear(valor: float, de_inicio: int, de_tamanho: int, para_inicio: int, para_tamanho: int) -> float:
    return para_inicio + (valor - de_inicio) * para_tamanho / de_tamanho


def _ponto(monitores: Sequence[Monitor], x: float, y: float, *, para_fisico: bool) -> tuple[float, float]:
    m = _monitor_mais_proximo(monitores, x, y, logico=para_fisico)
    de, para = (m.logico_efetivo, m.fisico) if para_fisico else (m.fisico, m.logico_efetivo)
    return (_mapear(x, de.esquerda, de.largura, para.esquerda, para.largura), _mapear(y, de.topo, de.altura, para.topo, para.altura))


def ponto_logico_para_fisico(x: float, y: float, monitores: Sequence[Monitor]) -> tuple[float, float]:
    return _ponto(monitores, x, y, para_fisico=True)


def ponto_fisico_para_logico(x: float, y: float, monitores: Sequence[Monitor]) -> tuple[float, float]:
    return _ponto(monitores, x, y, para_fisico=False)


def _retangulo(ret: Retangulo, monitores: Sequence[Monitor], *, para_fisico: bool) -> Retangulo:
    """Converte pelas bordas: o canto superior esquerdo usa o monitor do primeiro pixel e o inferior direito o do último pixel
    (a borda direita é exclusiva), de modo que retângulos vizinhos continuam vizinhos e nada fica com tamanho zero por arredondamento."""
    if ret.vazio:
        return ret
    ini = _monitor_mais_proximo(monitores, ret.esquerda, ret.topo, logico=para_fisico)
    fim = _monitor_mais_proximo(monitores, ret.direita - 1, ret.base - 1, logico=para_fisico)

    def alvo(m: Monitor) -> tuple[Retangulo, Retangulo]:
        return (m.logico_efetivo, m.fisico) if para_fisico else (m.fisico, m.logico_efetivo)

    (de_i, para_i), (de_f, para_f) = alvo(ini), alvo(fim)
    x1 = arredondar(_mapear(ret.esquerda, de_i.esquerda, de_i.largura, para_i.esquerda, para_i.largura))
    y1 = arredondar(_mapear(ret.topo, de_i.topo, de_i.altura, para_i.topo, para_i.altura))
    x2 = arredondar(_mapear(ret.direita, de_f.esquerda, de_f.largura, para_f.esquerda, para_f.largura))
    y2 = arredondar(_mapear(ret.base, de_f.topo, de_f.altura, para_f.topo, para_f.altura))
    return Retangulo(x1, y1, max(x2 - x1, 1), max(y2 - y1, 1))


def retangulo_logico_para_fisico(ret: Retangulo, monitores: Sequence[Monitor]) -> Retangulo:
    return _retangulo(ret, monitores, para_fisico=True)


def retangulo_fisico_para_logico(ret: Retangulo, monitores: Sequence[Monitor]) -> Retangulo:
    return _retangulo(ret, monitores, para_fisico=False)


class EspacoDeCoordenadas:
    """Ponte entre o Qt (seleção e overlay) e a captura (pixels físicos). Com o Qt em pixels físicos é a identidade."""

    def __init__(self, monitores: Sequence[Monitor]) -> None:
        self.monitores: tuple[Monitor, ...] = tuple(monitores)
        self.identidade = all(m.logico is None or m.logico == m.fisico for m in self.monitores)

    def qt_para_fisico(self, ret: Retangulo) -> Retangulo:
        return ret if self.identidade else retangulo_logico_para_fisico(ret, self.monitores)

    def fisico_para_qt(self, ret: Retangulo) -> Retangulo:
        return ret if self.identidade else retangulo_fisico_para_logico(ret, self.monitores)

    def bbox_fisico_para_qt(self, bbox: BBox) -> BBox:
        """Caixa de texto do OCR (floats, em pixels físicos) para a régua do overlay."""
        if self.identidade:
            return bbox
        x1, y1 = ponto_fisico_para_logico(bbox[0], bbox[1], self.monitores)
        x2, y2 = ponto_fisico_para_logico(bbox[2], bbox[3], self.monitores)
        return (x1, y1, x2, y2)


def descrever(monitores: Iterable[Monitor]) -> str:
    """Texto curto para o log e o diagnóstico."""
    linhas = []
    for m in monitores:
        f = m.fisico
        logico = "" if m.logico is None or m.logico == m.fisico else f", lógico {m.logico.largura}x{m.logico.altura} em ({m.logico.esquerda}, {m.logico.topo})"
        linhas.append(f"monitor {m.indice}{' (principal)' if m.principal else ''}{' ' + m.nome if m.nome else ''}: "
                      f"{f.largura}x{f.altura} em ({f.esquerda}, {f.topo}), escala {m.escala:g}{logico}")
    return "\n".join(linhas)
