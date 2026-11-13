# Histórico de atualizações

Cada atualização tem um .bat nesta pasta que manda a versão para o GitHub. Mais nova primeiro.

## 12/11/2026 — Fase 3.2 — primeiro envio do projeto ao GitHub
- Projeto completo das Fases 0 a 3.2 na main do repositório (código, testes, documentos e guias)
- Fase 3.2: a tradução fica fora da captura da tela (SetWindowDisplayAffinity) e o programa testa isso sozinho ao abrir
- Fase 3.2: a tradução antiga some na hora em que a tela muda e só lê de novo 1,5 s depois de a tela parar
- Fase 3.2: ruído, cursor e animações pequenas deixam de refazer o OCR; cache de traduções
- Repositório: .gitignore, .gitattributes, gerador de .bat (tools/gerar_atualizacao.py) e este histórico de atualizações
- Não verificado no Windows: o teste A/B do overlay e o plano B ainda precisam rodar no seu computador
