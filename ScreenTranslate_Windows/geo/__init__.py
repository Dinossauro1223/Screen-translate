"""Geometria da tela (Fase 3): retângulos, monitores, validação de região e conversão de coordenadas.

geometria.py  lógica pura (sem Qt, mss nem ctypes), testada com layouts sintéticos
monitores.py  monta a lista de monitores a partir do mss (pixels físicos) e do Qt (lógico) e confere se batem
dpi.py        deixa o processo e o Qt trabalhando em pixels FÍSICOS, para que seleção, captura, OCR e overlay usem a mesma régua
"""
