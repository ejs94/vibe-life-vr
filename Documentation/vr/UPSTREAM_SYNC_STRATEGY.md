# Upstream Synchronization & Evaluation Strategy (FWGS -> VR Fork)

## 1. Visão Geral e Filosofia Arquitetural

O repositório **Xash3D FWGS VR** é um fork especializado que introduz subsistemas profundos de realidade virtual (OpenXR runtime estéreo, renderizador dedicado `ref_gl_vr`, matrizes 6DoF de mira e rastreamento de controles, áudio binaural HRTF 3D e launcher adaptado para o Meta Quest 3 / Horizon OS).

Por essa razão, **é estritamente proibido realizar `git merge upstream/master` ou `git rebase` cego**. Um merge indiscriminado causaria:
1. Conflitos massivos em arquivos críticos do motor (`engine/client`, `engine/server`, `ref_gl`).
2. Sobrescrita silenciosa de modificações de VR (posições de cano de arma, rotações de headset, cvars de calibração).
3. Importação de bugs ou regressões temporárias do desenvolvimento upstream.

### O Princípio Fundamental: *Selective Cherry-Pick com Janela de Maturação*
Adotamos uma abordagem cirúrgica baseada em:
* **Janela de Maturação (60 a 90 dias):** Nenhum commit do upstream é avaliado imediatamente após ser lançado. Aguardamos um período de estabilização no ecossistema do FWGS para garantir que eventuais regressões ou *hotfixes* já tenham sido identificados e corrigidos.
* **Isolamento e Teste Automatizado:** Todo commit candidato é testado em uma branch de sandbox isolada com compilação e execução da suíte de 23 asserções Monado VR antes de entrar na branch principal.

---

## 2. Matriz de Avaliação por Subsistema

Ao analisar commits do upstream (`FWGS/xash3d-fwgs`), classificamos as mudanças em três categorias:

| Categoria | Subsistemas do Upstream | Política de Adoção |
| :--- | :--- | :--- |
| 🟢 **ALTO VALOR (Recomendado)** | • **Rede e Protocolo** (`net_*.c`, `delta.c`)<br>• **Sistema de Arquivos** (`filesystem_stdio.c`, `fs_*.c`)<br>• **Segurança e Parsers** (correções de crash em mapas BSP, modelos corrompidos, buffers)<br>• **Áudio Geral** (`s_main.c`, drivers ALSA/Pulse/PipeWire) | **Aprovar e Cherry-pickar:** Beneficia a estabilidade geral da engine sem afetar o pipeline de renderização VR ou os controles 6DoF. |
| 🟡 **ALERTA / ANÁLISE MANUAL** | • **Renderizador** (`ref_gl`, shaders OpenGL)<br>• **Modelos de Estúdio** (`gl_studio.c`, matrizes de ossos)<br>• **Movimentação do Jogador** (`pmove.c`, `sv_pmove.c`)<br>• **Estruturas de Entidades** (`entity_state.h`, `const.h`) | **Avaliação Criteriosa:** Como temos o renderizador `ref_gl_vr` e intervenções em `sv_pmove.c` (`vuser1..vuser4`), patches devem ser adaptados manualmente para não quebrar a balística 6DoF ou a projeção estéreo. |
| 🔴 **IGNORAR (Incompatível / Sem Efeito)** | • **Controles Touch Mobile** (`touch.c`, botões virtuais na tela, layouts touch)<br>• **Joysticks 2D Analógicos Planos** (otimizações para telas capacitivas de smartphones)<br>• **Launcher Android Flat Padrão** (`GameActivity` padrão de celular) | **Descartar:** No Meta Quest 3, a interação é 100% conduzida por controles 6DoF físicos, ponteiros laser e o Launcher imersivo Horizon OS. Commits touch só adicionam ruído. |

---

## 3. Ferramenta Automatizada: `upstream_sync_audit.sh`

Para tornar essa rotina simples e reprodutível, foi criado o utilitário [`scripts/upstream_sync_audit.sh`](../../scripts/upstream_sync_audit.sh).

### 3.1. Verificar Status de Sincronização
Exibe quantos commits o upstream avançou e a distância da base do fork:
```bash
./scripts/upstream_sync_audit.sh status
```

### 3.2. Baixar Atualizações do Upstream
Atualiza as referências remotas oficiais do FWGS sem tocar nas branches locais:
```bash
./scripts/upstream_sync_audit.sh fetch
```

### 3.3. Filtrar Commits por Janela de Maturação
Lista commits do upstream que já possuem mais de 60 (ou $N$) dias de maturidade, categorizados por relevância:
```bash
./scripts/upstream_sync_audit.sh filter 60
```

### 3.4. Inspecionar Detalhes de um Commit
Visualiza o diff, autor e descrição completa de um commit específico:
```bash
./scripts/upstream_sync_audit.sh inspect <hash-do-commit>
```

### 3.5. Teste Sandbox Automatizado de Cherry-Pick
Cria uma branch temporária isolada, aplica o cherry-pick, compila com `waf` e executa a bateria de 23 testes unitários Monado VR:
```bash
./scripts/upstream_sync_audit.sh test-pick <hash-do-commit>
```
Se todos os testes passarem sem regressão, o script indica o comando exato para aplicar em definitivo. Se falhar ou causar conflitos, a branch de teste é descartada automaticamente sem deixar resíduos no seu repositório.

---

## 4. Checklist de Qualidade para Integração Permanente

Antes de commitar qualquer cherry-pick do upstream na branch `feature/openxr-vr`:
1. [ ] **Verificação de Compilação Linux Desktop:** `./waf build && ./waf install --destdir=./out` (Zero erros/warnings).
2. [ ] **Verificação de Regressão VR:** `./scripts/test_simulated_monado.sh` (100% verde, 23/23 testes).
3. [ ] **Verificação de Build Meta Quest 3:** `./scripts/build_quest_apk.sh` (Geração limpa de `out/xash3d-vr-quest.apk`).
4. [ ] **Comentários de Código em Inglês:** Conforme regra global do projeto, qualquer comentário adicionado ou adaptado deve estar em inglês.
