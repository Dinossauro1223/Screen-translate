"""Monitores: lista vinda do mss (pixels físicos) e do Qt (lógico), e a checagem de que os dois descrevem a mesma tela."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from geo.geometria import ErroDeMonitores, Monitor, Retangulo, arredondar, descrever

IDENTIDADE = "identidade"   # o Qt usa pixels físicos: seleção, captura, OCR e overlay falam a mesma língua
ESCALADO = "escalado"       # o Qt usa pixels lógicos (escala ligada): a seleção e o overlay precisam de conversão
INCOERENTE = "incoerente"   # Qt e captura não descrevem os mesmos monitores: não dá para garantir a posição do overlay


def monitores_do_mss(monitores_mss: Sequence[Mapping[str, Any]]) -> list[Monitor]:
    """O item 0 do mss é a tela virtual inteira; os itens 1..N são os monitores. O principal vem de 'is_primary' (mss >= 10.2)
    ou, nas versões antigas, é o que tem a origem em (0, 0) (no Windows e no X11 o monitor principal fica sempre na origem)."""
    candidatos = list(monitores_mss[1:]) if len(monitores_mss) > 1 else list(monitores_mss)
    resultado: list[Monitor] = []
    for indice, bruto in enumerate(candidatos, start=1):
        try:
            fisico = Retangulo(int(bruto["left"]), int(bruto["top"]), int(bruto["width"]), int(bruto["height"]))
        except (KeyError, TypeError, ValueError) as erro:
            raise ErroDeMonitores(f"O monitor {indice} do mss não tem left/top/width/height válidos: {bruto!r}") from erro
        if fisico.vazio:
            continue
        resultado.append(Monitor(len(resultado) + 1, fisico, principal=bool(bruto.get("is_primary", False)), nome=str(bruto.get("name") or "")))
    if not resultado:
        raise ErroDeMonitores("O mss não encontrou nenhum monitor.")
    if not any(m.principal for m in resultado):
        resultado = [replace(m, principal=m.fisico.esquerda == 0 and m.fisico.topo == 0) for m in resultado]
    return resultado


def monitores_do_qt(telas: Sequence[Any], principal: Any = None) -> list[Monitor]:
    """Monta a lista a partir de QScreen (ou de qualquer objeto com geometry(), devicePixelRatio() e name()).
    O retângulo 'fisico' aqui é só uma ESTIMATIVA (lógico x escala) usada para casar com os monitores do mss."""
    resultado: list[Monitor] = []
    for indice, tela in enumerate(telas, start=1):
        g = tela.geometry()
        escala = float(tela.devicePixelRatio())
        logico = Retangulo(int(g.x()), int(g.y()), int(g.width()), int(g.height()))
        estimado = Retangulo(arredondar(g.x() * escala), arredondar(g.y() * escala),
                             max(arredondar(g.width() * escala), 1), max(arredondar(g.height() * escala), 1))
        resultado.append(Monitor(indice, estimado, logico, escala, principal=principal is not None and tela is principal, nome=str(tela.name())))
    return resultado


def parear(qt: Sequence[Monitor], fisicos: Sequence[Monitor]) -> list[Monitor] | None:
    """Casa cada monitor do Qt com o do mss: da esquerda para a direita e de cima para baixo (a escala preserva a ordem) e
    conferindo que o tamanho físico estimado bate (tolerância de 1 pixel). Devolve None se não fechar."""
    if len(qt) != len(fisicos):
        return None
    qt_ordenado = sorted(qt, key=lambda m: (m.logico_efetivo.esquerda, m.logico_efetivo.topo))
    fisicos_ordenados = sorted(fisicos, key=lambda m: (m.fisico.esquerda, m.fisico.topo))
    resultado = []
    for q, f in zip(qt_ordenado, fisicos_ordenados, strict=True):
        if abs(q.fisico.largura - f.fisico.largura) > 1 or abs(q.fisico.altura - f.fisico.altura) > 1:
            return None
        resultado.append(Monitor(f.indice, f.fisico, q.logico, q.escala, principal=f.principal or q.principal, nome=f.nome or q.nome))
    return sorted(resultado, key=lambda m: m.indice)


@dataclass(frozen=True)
class RelatorioDeCoerencia:
    modo: str
    monitores: tuple[Monitor, ...]
    avisos: tuple[str, ...] = ()
    problemas: tuple[str, ...] = ()


def avaliar_coerencia(qt: Sequence[Monitor], fisicos: Sequence[Monitor]) -> RelatorioDeCoerencia:
    if not qt or not fisicos:
        return RelatorioDeCoerencia(INCOERENTE, (), problemas=("Não há monitores " + ("no Qt." if not qt else "na captura."),))
    if len(qt) == len(fisicos) and all(abs(q.escala - 1.0) < 1e-6 for q in qt):
        retangulos = {f.fisico for f in fisicos}
        if all(q.logico_efetivo in retangulos for q in qt) and len({q.logico_efetivo for q in qt}) == len(qt):
            nomes = {q.logico_efetivo: q.nome for q in qt}
            return RelatorioDeCoerencia(IDENTIDADE, tuple(replace(f, nome=f.nome or nomes.get(f.fisico, "")) for f in fisicos))
    pareados = parear(qt, fisicos)
    if pareados is not None:
        avisos = tuple(f"O Qt usa escala {m.escala:g} no monitor {m.indice} ({m.logico_efetivo.largura}x{m.logico_efetivo.altura} lógicos para "
                       f"{m.fisico.largura}x{m.fisico.altura} físicos): a seleção e o overlay serão convertidos." for m in pareados
                       if m.logico_efetivo != m.fisico)
        return RelatorioDeCoerencia(ESCALADO, tuple(pareados), avisos=avisos)
    problemas = ["Os monitores do Qt e os da captura não correspondem.", "Qt:", *descrever(qt).splitlines(), "Captura:", *descrever(fisicos).splitlines()]
    return RelatorioDeCoerencia(INCOERENTE, (), problemas=tuple(problemas))


def exigir_coerencia(relatorio: RelatorioDeCoerencia) -> tuple[Monitor, ...]:
    """Os monitores prontos para uso, ou ErroDeMonitores com a descrição do que não bateu."""
    if relatorio.modo == INCOERENTE:
        raise ErroDeMonitores("\n".join(relatorio.problemas) + "\nFeche o programa, confira o arranjo dos monitores e abra de novo "
                                                               "(python -m bootstrap diagnostico mostra o que o programa enxerga).")
    return relatorio.monitores
