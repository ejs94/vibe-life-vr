# 📌 Ponto de Parada da Sessão (Session Checkpoint)

**Data do Checkpoint:** 24 de Outubro de 2026  
**Projeto:** Vibe-Life VR  
**Repositório:** `vibe-life-vr`  
**Branch:** `feature/openxr-vr`  
**Dispositivo Físico:** Meta Quest 3S (`3487C10GBP00JJ`) — Standalone APK instalável via ADB.  
**APK de Referência:** [`out/xash3d-vr-quest.apk`](out/xash3d-vr-quest.apk) (recompilar após mudanças de assets/grip)  
**Caderno de Engenharia:** [Documentation/vr/ENGINEERING_NOTEBOOK.md](Documentation/vr/ENGINEERING_NOTEBOOK.md)

---

## 🎨 Rebranding e MMOD (24/10/2026)

- Projeto renomeado para **Vibe-Life VR**: README, documentação, `gameinfo.txt` e o rótulo do app Android foram atualizados.
- Os 15 viewmodels do **Half-Life MMOD — Reanimated Pack** (`valve_addon`) foram integrados em `assets/valve_vr/models/`.
- `MMOD_AUDIT.md` foi removido; créditos, permissão, SHA-256 do arquivo, escopo e auditoria 360° por arma agora vivem em [`assets/valve_vr/CREDITS.md`](assets/valve_vr/CREDITS.md).
- Grip offsets foram recalibrados para os novos MDLs: `seat_err ≤ 0.001` em 14 armas. O foregrip da Crossbow foi reancorado no osso `grip` (origem validada em `(508.250, 315.853, -176.452)`).
- O probe `[VR_GRIP_BONE]` agora emite o vetor `err=(x y z)` em espaço local da arma, permitindo calibrar sem adivinhação.
- `scripts/setup_out_gamedir.sh` e `scripts/deploy_quest_assets.sh` agora instalam todos os viewmodels com proteção contra symlinks e verificação sha256.
- Validação: **43/43** testes Monado e **18/18** testes de regressão aprovados.
- APK reconstruído e instalado no Quest 3S; HIL básico passou (`out/evidence/quest_20261024_032018`).
- HIL de assets carregou `models/v_shotgun.mdl` no Quest e gerou eye buffer válido (`out/evidence/mmod_quest`).
- Repositório local renomeado para `vibe-life-vr` e GitHub renomeado para `ejs94/vibe-life-vr`.

---

## 🔄 Migração para OpenCode (24/10/2026)

- O Antigravity não é mais utilizado. A configuração MCP foi migrada de `.agents/mcp_config.json` para [`opencode.json`](opencode.json), usando `mcp.servers` com os servidores `repowise`, `graphify` e `blender`.
- As regras de agente e o mapa do projeto foram consolidados em [`AGENTS.md`](AGENTS.md).
- Foram adicionados agentes (`@reviewer`, `@quest-tester`), comandos (`/build-quest`, `/deploy-quest`, `/quest-test`, `/monado-test`, `/regression`, `/grip-check`) e skills locais (`.opencode/skills/quest` e `.opencode/skills/xash-vr-quest`).
- O loop HIL do Quest continua sendo a validação de referência; use `scripts/test_quest_auto.sh` após recompilar o APK.

---

## 🏁 O que foi Concluído até o Momento

1. **Controles Touch e Analógicos Ativos:** Locomoção e rotação via analógicos, botões de ação e lanterna integrados no topo de `IN_EngineAppendMove`.
2. **Origem do Laser e Empunhadura Dominante:** Deslocamento relativo à cabeça (`handPose - headPose`) e alinhamento milimétrico com a mão primária.
3. **Visão Ortonormal e Eliminação de Náusea:** Matriz de visão direta do quaternion OpenXR ($R, U, F$) combinada com `turn_yaw`.
4. **Sweet Spot Óptico no Menu Flutuante:** Distância e escala padrão do quad layer calibradas (`vr_menu_distance 1.5m`, `vr_menu_scale 1.4m`).
5. **Launcher 2D Horizon OS Modernizado:** Layout dinâmico responsivo, botões desacoplados e painel de preferências VR.
6. **Menu VR In-Headset Dedicado (`CMenuVR`):** Controle completo em C++ para conforto, calibração, miras e áudio dentro do headset.
7. **Simulador Headless Monado PCVR:** Bateria de testes automatizada executável via terminal sem depender do headset físico.
8. **Lanterna de Cabeça com Gesto na Têmpora:** Cone de luz acoplado à linha de visão e acionamento por toque na têmpora com debounce.
9. **Ponteiros Laser Alternados no Menu (Beat Saber Style):** Mira laser simultânea de ambas as mãos com alternância instantânea pelo gatilho.
10. **Balística a partir do Cano Físico no Servidor:** Tiros e projéteis emergem com precisão milimétrica de `pev->vuser1` (`GetGunPosition()`).
11. **Arremesso Físico de Granadas por Inércia 6DoF:** Vetor de lançamento soma a velocidade angular/linear do braço do jogador (`pev->vuser3`).
12. **Áudio Espacial 3D HRTF & Base 6DoF do Ouvinte (Issue #17):**
    - Listener binaural acoplado à cabeça via `XR_GetHeadCenterTransformWithBasis()`, eliminando gimbal lock no Roll.
    - Sombra acústica direcional da orelha humana (atenuação de sons traseiros) e difração vertical em `S_SpatializeChannel()`.
    - Bypass de silenciamento em simulação (`snd_mute_losefocus` desativado se `XR_IsActive()`).
13. **Bateria Master de Regressão (14/14 Gates 100% PASS):**
    - `scripts/run_regression_battery.sh` cobrindo OpenXR, FBOs, render estéreo, balística, lasers, áudio HRTF, APK arm64-v8a e layout do Horizon OS.
14. **Reorganização Estrutural do Repositório:**
    - Repositório principal mantido isolado e limpo na raiz (`vibe-life-vr`).
    - Ferramentas e referências agrupadas em subpastas categorizadas (`mcp-tools`, `other-vr-ports`, `xash3d-upstream`, `xash3d-vr-ports`, `openxr-tooling`).
15. **Integração das Ferramentas MCP ao Fluxo de Desenvolvimento (`mcp-tools`):**
    - Configurado `opencode.json` conectando os servidores MCP `repowise` (blast radius e dependência de símbolos), `graphify` (grafo de conhecimento AST da arquitetura) e `blender` (pipeline de assets).
    - Criado utilitário unificado [`scripts/mcp_tools.sh`](scripts/mcp_tools.sh) (`status`, `graph`, `dead-code`, `health`, `mcp-repowise`, `mcp-graphify`).
    - Gerados os artefatos iniciais do ecossistema: [`graphify-out/graph.json`](graphify-out/graph.json) (39.710 nós e 106.381 conexões) e visualização interativa [`graphify-out/graph.html`](graphify-out/graph.html).
    - Estabelecido protocolo de 3 fases (Pré-Refatoração com Repowise, Implementação com Graphify e Validação com Desloppify + Regressão) em `AGENTS.md` e Seção 8 do Caderno de Engenharia.

16. **Mapeamento de Controles Unificado Padrão Half-Life 2: VR Mod:**
    - Botão A direito: Recarregar (`+reload`).
    - Botão B direito: Disparo Secundário (`+attack2`, lança-granadas na MP5, tiro duplo na Shotgun).
    - Botão X esquerdo: Pular (`+jump`).
    - Botão Y esquerdo: Usar / Interagir (`+use`).
    - Alternância de menu universal no botão Menu (`K_ESCAPE`).
17. **Arquitetura de Compatibilidade de Mods em 3 Tiers & Governança de Roadmap:**
    - Tiers estritos: **Gold** (Native VR), **Silver** (Calibrated Profile), **Bronze** (Universal Fallback).
    - Manifesto padronizado tipado em TypeScript com `extended_features` e flag opcional `vibe_code`.
    - Isolamento de SDKs sem conflito no engine/DLL ABI.
    - Convenção honesta adotada no Roadmap: bugs reabrem fases em 🟠 **Maintenance / Remediation**.
18. **Remediações Críticas Implementadas no HL1 Benchmark (Qualidade Gold Native VR):**
    - **Agachamento Físico Roomscale (`vr_physical_crouch`):** Headset caindo $\ge 28\text{cm}$ ativa o hull de 36 unidades, evitando que o jogador fique preso em dutos de ventilação (ex: Black Mesa `c1a2`).
    - **Alinhamento 6DoF de Minas e Snarks:** Trace de posicionamento de Tripmines e arremesso de Snarks seguem o vetor físico 6DoF da mão controladora (`pev->vuser2`), incorporando a inércia do golpe físico (`pev->vuser3 * 1.25f`).
    - **Física de Escadas em VR Desacoplada do Headset Pitch:** Analógico para frente sempre sobe ao longo do plano da escada independente de olhar para baixo, e o pulso no topo da escada impulsiona suavemente para a borda em vez de ejetar o jogador 270 unidades para trás.
19. **APK Meta Quest Standalone Atualizado e Pronto:**
    - APK recompilado em [`out/xash3d-vr-quest.apk`](out/xash3d-vr-quest.apk).
    - Binários x86_64 do host atualizados e validados com testes automatizados headless (`simulate_gold_remediations.cfg`, exit code 0).
20. **Suíte Oficial de Testes Unitários no Monado OpenXR (`scripts/test_simulated_monado.sh`):**
    - Transformado em um executor de testes unitários end-to-end assertivo, cobrindo 100% dos subsistemas desenvolvidos em PCVR simulado via Monado (`scripts/monado_unit_tests.cfg`).
    - Bateria com 23 asserções automatizadas cobrindo runtime OpenXR, menus, lasers Beat Saber, layout HL2:VR, agachamento físico, balística 6DoF, minas, snarks, mãos esqueléticas e áudio HRTF.
    - **Resultado:** 23/23 testes aprovados (100% GREEN), 18 capturas de tela visuais em PNG geradas em `out/evidence/monado_unittest_*/`.
21. **Interface do Menu VR In-Headset com Abas de Sessões & Aba Dedicada para VR Debug (`CMenuVR`):**
    - Subdivisão do menu superlotado em 4 abas ergonômicas usando `CMenuTabView` com suporte total a input interativo (mouse, laser pointer VR, hotkeys `[` e `]`):
      - **Aba 1 (Locomotion & Comfort):** Smooth turn, snap turn angle, walk direction de controle, physical roomscale crouch e ajuste de distância/escala do menu 2D flutuante.
      - **Aba 2 (Weapons & Combat):** Mira laser 3D, lanterna de cabeça, estabilização bimanual, empunhadura canhota, mira óptica por proximidade, golpe físico do pé-de-cabra e ajuste de pitch do cano.
      - **Aba 3 (Presence & Audio):** Flexão procedural dos dedos, presença 6DoF da mão secundária, gesto touch-to-use, vibração tátil dos gatilhos, laser HUD pointer, áudio espacial 3D HRTF e calibração de altura/escala de mundo.
      - **Aba 4 (VR Debug - Aba Dedicada):** Marcadores visuais 3D de impacto de projéteis (`vr_debug_impacts`), simulação 6DoF de headset e controles para testes headless, botões de ação interativos para registrar amostras e limpar marcadores (`vr_record_impact`, `vr_clear_impacts`), reset de calibração para padrão de fábrica e painel de telemetria em tempo real (Meta Quest 3, taxa de amostragem de 120Hz, limiar de duck de 28cm e pipeline estéreo ref_gl_vr).
    - Validação com 100% PASS (23/23 testes green no Monado) e APK Meta Quest compilado e pronto em `out/xash3d-vr-quest.apk`.
22. **Estabilização Bimanual com Gating Espacial e Soft Clamp (`vr_twohanded`):**
    - Modelo ergonômico validado (*FEAR VR* e *Lambda1VR*): vetor dominante $\to$ secundária com avanço frontal de 5cm a 60cm, separação euclidiana de 12cm a 65cm e clamp assintótico suave (`softDev`) prevenindo paradas bruscas em rotações acentuadas.
23. **Proximity Scope Natural (`vr_proximity_scope`):**
    - Ativação automática de zoom ótico (`+alt1`) ao aproximar o visor da Crossbow/Magnum a menos de 15cm do olho.
24. **Toque Físico com o Cenário (`vr_gesture_use`):**
    - Disparo natural de interação ao estender a mão livre contra botões, painéis e estações HEV no mapa.

---

25. **Mãos Esqueléticas 3D e Curvatura Contínua dos Dedos (Issue #16):**
    - Desacoplamento de braços planos de 1998 com preservação de luvas e palmas (`vr_hide_arms 1`).
    - Flexão procedural analógica contínua orientando ossos de falanges via quaternions locais:
      - Gatilho analógico: Dedo indicador (`Finger1` / `Bone31..33`).
      - Grip analógico: Dedos médio, anelar e mínimo (`Finger2..4` / `Bone35..45`).
      - Toque capacitivo/deflexão: Polegar (`Finger0` / `Bone27..29`).
    - Suporte bidirecional para rigs Valve Standard (`Bip01 Finger0..4`) e malhas standalone (`Bone27..45`).
    - Entidade 6DoF dedicada de presença de mão desacoplada (`s_offhandEnt`, `vr_offhand_render 1`) com suporte nativo ao modelo [`models/v_hand.mdl`](assets/valve_vr/models/v_hand.mdl).
26. **Parser C em Tempo de Execução de Perfis Declarativos (`vr_weapons.json` — Tier Silver):**
    - Módulo C zero-dependência [`engine/platform/openxr/xr_profile.c`](engine/platform/openxr/xr_profile.c) e [`xr_profile.h`](engine/platform/openxr/xr_profile.h) que carrega e analisa manifests JSON na inicialização e troca de mapas.
    - Calibração por arma de `grip_offset`, `pitch_adjust`, `yaw_adjust`, `roll_adjust`, gating bimanual `two_handed` (bloqueando duas mãos no pé-de-cabra/granadas), distâncias mín/máx de empunhadura, índices de attachment de cano/ejeção/carregador e hápticos dedicados.
    - Comando de console para hot-reload em tempo real no headset: `vr_reload_weapon_profiles`.
    - Bateria de testes Monado expandida para 24 asserções automatizadas com **100% PASS (24/24 GREEN)**.
27. **Remediação de Dívida Técnica e Code Health Guiada por Repowise:**
    - Diagnóstico de saúde do Repowise MCP atendido: [`engine/platform/openxr/xr_input.c`](engine/platform/openxr/xr_input.c).
    - Modularização de `XR_InputAppendMove` (queda de complexidade de CCN 160 $\to$ 4, decomposta em `XR_ProcessTriggers`, `XR_ProcessAltFireButton`, `XR_ProcessCrouchAndSprint`, `XR_ProcessUseAndFlashlight`, `XR_ProcessHeadFlashlightGesture`, `XR_ProcessWeaponSelectionGestures`, `XR_ProcessTouchToUse`, `XR_ProcessProximityScope`, `XR_ProcessPhysicalMeleeSwing`, `XR_ProcessLocomotionAndTurn`).
    - Modularização de `XR_SyncInputs` (CCN 72 $\to$ 3, decomposta em `XR_SyncActionStates`, `XR_SyncThumbsticksAndCurls`, `XR_SyncHandPoses`).
    - Modularização de `XR_UpdatePointerCursor` (CCN 80 $\to$ 28, decomposta em `XR_ProcessMenuToggle`, `XR_TracePointerRayForHand`, `XR_ProcessPointerTriggers`, `XR_ProcessPointerScroll`).
    - Modularização de `XR_InitInput` (decomposta em `XR_CreateAllActions`, `XR_SuggestAllBindings`, `XR_AttachActionSetsAndSpaces`).
    - Validação total com build Waf 100% limpo e **24/24 Monado tests 100% GREEN**.
28. **Remediações do Teste de Campo Quest 3 Implementadas e Validadas (18/10/2026):**
    - **ACT-01 (Issue #22):** Modelos de RPG e Laser Tripmine restaurados em `ref/gl_vr/gl_studio.c` corrigindo a condição de reload prop suppression.
    - **ACT-02 (Issue #23):** Locomoção contínua em escadas por analógico corrigida em `pm_shared.c` sem travamento.
    - **ACT-03 (Issue #24):** Balística 6DoF a partir do cano físico (`pev->vuser1`/`GetGunPosition()`) e mira 6DoF (`pev->vuser2`) unificadas no Gauss/Tau, Egon/Gluon, Hornetgun e RPG, eliminando offsets legados da tela 2D.
    - **ACT-04 (Issue #25):** Inversão do eixo Roll das armas corrigida em `xr_swapchain.c` (`XR_QuatToEuler`).
    - **ACT-05 (Issue #26):** Detecção de golpe físico do pé-de-cabra corrigida convertendo m/s para unidades GoldSrc via `worldScale` em `xr_input.c`.
    - **ACT-06 (Issue #27):** Eliminação de saltos de 180° no analógico limitando o pitch a $[-89^\circ, 89^\circ]$ em `xr_input.c` e orientando pelo controle secundário.
    - **ACT-07 (Issue #28):** Ergonomia do menu 2D flutuante ajustada para 1.15m de distância/escala e sincronização garantida com `XR_ResetMenuAnchor()` no comando `vr_recenter`.
    - **ACT-08 (Issue #29):** Zoom ótico da Crossbow com debounce no Botão B e ativação por proximidade (`vr_proximity_scope`) ampliada para 24cm.
    - **ACT-09 (Issue #30):** Presença 6DoF da mão secundária ativada por padrão (`vr_offhand_render 1`), com tentativa contínua de carga de `v_hand.mdl` e assets embutidos no APK.
    - **ACT-10 (Issue #31):** Calibração de empunhadura do pé-de-cabra e armas em `vr_weapons.json` com packaging automatizado.
    - **Validação Monado:** 24/24 asserções aprovadas com 100% GREEN e 20 capturas visuais.
    - **Build Standalone APK:** Gerado com sucesso em [`out/xash3d-vr-quest.apk`](out/xash3d-vr-quest.apk) (34MB) usando NDK 30 e OpenJDK 21.
29. **Sistema 3D de Pontos de Rastreamento das Mãos, Centro de Massa (COM) e Telemetria em Tempo Real:**
    - **Pontos 3D das Mãos (Primary & Offhand):** Renderização de giroscópios orbitais ortogonais (anéis 3D) com marcadores de ponto central e eixos de coordenadas graduados (RGB) nas origens exatas de tracking de ambas as mãos.
    - **Centro de Massa das Armas (COM):** Cálculo contínuo do centróide volumétrico ponderado através de todos os hitboxes orientados pela matriz de ossos (`Matrix3x4_VectorTransform(bonestransform[bone])`). Renderizado com anéis dourados, retículo de gravidade ($\oplus$), vetor de alavanca empunhadura $\to$ COM e vetor COM $\to$ muzzle.
    - **Hitboxes em 3D (`vr_debug_hand 2`):** Desenho em aramado 3D de todas as caixas de colisão dos modelos de armas (`mstudiobbox_t`) coloridas por grupo anatômico (`hullcolor[group % 8]`).
    - **Telemetria Contínua no HUD:** Exibição em tempo real via `Con_NPrintf` (linhas 0 a 5) reportando coordenadas e rotação da Cabeça (HMD), Mão Direita (Dominante), Mão Esquerda (Secundária), Centro de Massa da Arma e Hitboxes.
    - **Comando de Console `vr_telemetry`:** Snapshot detalhado com todas as coordenadas e distâncias impresso no console.
    - **Menu VR (Tab 4):** Adicionados checkbox `6DoF Hand & Weapon COM Gizmos` e botão `Dump 6DoF Telemetry Snapshot` em `CMenuVR`.
    - **Validação:** 24/24 testes Monado 100% GREEN e APK Meta Quest recompilado.

---

## 🎯 Registro das Atividades de Remediação do Teste de Campo Quest 3 (18/10/2026)

| ID | Atividade / Bug | Subsistema Impactado | Severidade | Status | Solução Implementada |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ACT-01** | **Restauração de Modelos Invisíveis (RPG & Tripmine)** | `ref/gl_vr/gl_studio.c` | 🔴 Alta | ✅ **Concluído** | Condição de supressão corrigida para `!is_reload && pos[i][2] < -15.0f`. |
| **ACT-02** | **Correção de Subida e Travamento em Escadas** | `3rdparty/hlsdk-portable/pm_shared/pm_shared.c` | 🔴 Alta | ✅ **Concluído** | `PM_LadderMove` agora avalia analógicos contínuos de VR (`cmd.forwardmove`/`sidemove`). |
| **ACT-03** | **Alinhamento Balístico & Desvio Óptico (Tau, Gluon, Hornet, RPG)** | `3rdparty/hlsdk-portable/dlls/` (`gauss.cpp`, `egon.cpp`, `hornetgun.cpp`, `rpg.cpp`) | 🔴 Alta | ✅ **Concluído** | Disparos partem do cano físico 6DoF (`pev->vuser1`/`GetGunPosition()`) na direção `pev->vuser2`. |
| **ACT-04** | **Correção da Inversão do Roll das Armas** | `engine/platform/openxr/xr_swapchain.c` (`XR_QuatToEuler`) | 🟡 Média | ✅ **Concluído** | Invertido o sinal de roll angular GoldSrc (`-roll * (180.0f / M_PI)`). |
| **ACT-05** | **Sensibilidade e Escala do Golpe Físico do Pé-de-Cabra** | `engine/platform/openxr/xr_input.c` (`XR_ProcessPhysicalMeleeSwing`) | 🟡 Média | ✅ **Concluído** | Conversão de velocidade linear de m/s para GoldSrc (`speed * worldScale > 48.0f`). |
| **ACT-06** | **Correção de Deriva/Inversão na Locomoção por Analógico** | `engine/platform/openxr/xr_input.c` (`XR_ProcessLocomotionAndTurn`) | 🟡 Média | ✅ **Concluído** | Pitch do controle travado em $[-89^\circ, 89^\circ]$ evitando singularidade do cosseno. |
| **ACT-07** | **Ergonomia do Menu Flutuante e Recentralização Efetiva** | `engine/platform/openxr/xr_swapchain.c`, `ref/gl_vr/gl_rmain.c` | 🟡 Média | ✅ **Concluído** | Distância/escala padrão ajustadas para 1.15m; `R_VR_Recenter_f` chama `XR_ResetMenuAnchor()`. |
| **ACT-08** | **Acionamento de Zoom Óptico no Crossbow** | `3rdparty/hlsdk-portable/dlls/crossbow.cpp`, `engine/platform/openxr/xr_input.c` | 🟡 Média | ✅ **Concluído** | Debounce no Botão B para toggle do zoom; alcance de proximidade expandido para 24cm. |
| **ACT-09** | **Presença Ativa da Mão Secundária Independente (Offhand 6DoF)** | `ref/gl_vr/gl_studio.c` (`R_DrawOffHand`), `android/app/build.gradle.kts` | 🟢 Baixa | ✅ **Concluído** | `vr_offhand_render 1` ativo por padrão; retentativa de carregamento; assets inclusos no APK. |
| **ACT-10** | **Recalibração do Ponto de Empunhadura (Grip Offsets)** | `assets/valve_vr/models/vr_weapons.json` | 🟢 Baixa | ✅ **Concluído** | Pé-de-cabra ajustado para offset `[0.0, 0.5, -0.5]` e pitch `-2.0`, reempacotado no APK. |

---

## 🚀 Procedimento de Instalação e Teste no Meta Quest 3

Para atualizar o APK no headset via cabo USB ou Wi-Fi ADB:

```bash
adb install -r out/xash3d-vr-quest.apk
```

### Roteiro Recomendado de Validação no Headset:
1. **Subida de Escada:** Testar a subida e descida com o polegar analógico esquerdo empurrado para frente/trás (não deve travar nem ejetar ao atingir o topo).
2. **Modelos RPG e Tripmine:** Puxar a Tripmine e o RPG (devem estar com o corpo visível e alinhado na mão).
3. **Roll das Armas e Pé-de-Cabra:** Girar o pulso em 360° (deve acompanhar 1:1 o pulso físico). Desferir golpes físicos com o pé-de-cabra (deve disparar som e dano de impacto).
4. **Armas de Energia / Projéteis:** Disparar Tau Cannon, Gluon Gun, Hornet Gun e RPG observando o alinhamento perfeito do raio/projétil com a mira laser da mão (`pev->vuser1` $\to$ `pev->vuser2`).
5. **Menu Flutuante e Recenter:** Pressionar Menu (o quadro flutuante deve surgir a 1.15m confortável); acionar `vr_recenter` pelo menu ou console e verificar o reposicionamento imediato.
