# 📌 Ponto de Parada da Sessão (Session Checkpoint)

**Data do Checkpoint:** 17 de Outubro de 2026  
**Repositório:** `xash3d-fwgs-vr`  
**Branch:** `feature/openxr-vr`  
**Dispositivo Físico:** Meta Quest 3 (`3487C10GBP00JJ`) — Standalone APK pronto para instalação via ADB.  
**APK Atualizado e Pronto:** [`out/xash3d-vr-quest.apk`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/out/xash3d-vr-quest.apk)  
**Caderno de Engenharia:** [Documentation/vr/ENGINEERING_NOTEBOOK.md](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/Documentation/vr/ENGINEERING_NOTEBOOK.md)

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
    - Repositório principal mantido isolado e limpo na raiz (`xash3d-fwgs-vr`).
    - Ferramentas e referências agrupadas em subpastas categorizadas (`mcp-tools`, `other-vr-ports`, `xash3d-upstream`, `xash3d-vr-ports`, `openxr-tooling`).
15. **Integração das Ferramentas MCP ao Fluxo de Desenvolvimento (`mcp-tools`):**
    - Configurado `.agents/mcp_config.json` conectando os servidores MCP `repowise` (blast radius e dependência de símbolos) e `graphify` (grafo de conhecimento AST da arquitetura).
    - Criado utilitário unificado [`scripts/mcp_tools.sh`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/mcp_tools.sh) (`status`, `graph`, `dead-code`, `health`, `mcp-repowise`, `mcp-graphify`).
    - Gerados os artefatos iniciais do ecossistema: [`graphify-out/graph.json`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/graphify-out/graph.json) (39.710 nós e 106.381 conexões) e visualização interativa [`graphify-out/graph.html`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/graphify-out/graph.html).
    - Estabelecido protocolo de 3 fases (Pré-Refatoração com Repowise, Implementação com Graphify e Validação com Desloppify + Regressão) em `.agents/rules/mcp_workflow.md` e Seção 8 do Caderno de Engenharia.

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
    - **Física de Escadas em VR Desacoplada do Headset Pitch:** Analógico para frente sempre sobe ao longo do plano da escada independente de olhar para baixo, e o pulo no topo da escada impulsiona suavemente para a borda em vez de ejetar o jogador 270 unidades para trás.
19. **APK Meta Quest Standalone Atualizado e Pronto:**
    - APK recompilado em 33s em [`out/xash3d-vr-quest.apk`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/out/xash3d-vr-quest.apk).
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
    - Entidade 6DoF dedicada de presença de mão desacoplada (`s_offhandEnt`, `vr_offhand_render 1`) com suporte nativo ao modelo [`models/v_hand.mdl`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/assets/valve_vr/models/v_hand.mdl).
26. **Parser C em Tempo de Execução de Perfis Declarativos (`vr_weapons.json` — Tier Silver):**
    - Módulo C zero-dependência [`engine/platform/openxr/xr_profile.c`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/engine/platform/openxr/xr_profile.c) e [`xr_profile.h`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/engine/platform/openxr/xr_profile.h) que carrega e analisa manifests JSON na inicialização e troca de mapas.
    - Calibração por arma de `grip_offset`, `pitch_adjust`, `yaw_adjust`, `roll_adjust`, gating bimanual `two_handed` (bloqueando duas mãos no pé-de-cabra/granadas), distâncias mín/máx de empunhadura, índices de attachment de cano/ejeção/carregador e hápticos dedicados.
    - Comando de console para hot-reload em tempo real no headset: `vr_reload_weapon_profiles`.
    - Bateria de testes Monado expandida para 24 asserções automatizadas com **100% PASS (24/24 GREEN)**.
27. **Remediação de Dívida Técnica e Code Health Guiada por Repowise:**
    - Diagnóstico de saúde do Repowise MCP atendido: [`engine/platform/openxr/xr_input.c`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/engine/platform/openxr/xr_input.c).
    - Modularização de `XR_InputAppendMove` (queda de complexidade de CCN 160 $\to$ 4, decomposta em `XR_ProcessTriggers`, `XR_ProcessAltFireButton`, `XR_ProcessCrouchAndSprint`, `XR_ProcessUseAndFlashlight`, `XR_ProcessHeadFlashlightGesture`, `XR_ProcessWeaponSelectionGestures`, `XR_ProcessTouchToUse`, `XR_ProcessProximityScope`, `XR_ProcessPhysicalMeleeSwing`, `XR_ProcessLocomotionAndTurn`).
    - Modularização de `XR_SyncInputs` (CCN 72 $\to$ 3, decomposta em `XR_SyncActionStates`, `XR_SyncThumbsticksAndCurls`, `XR_SyncHandPoses`).
    - Modularização de `XR_UpdatePointerCursor` (CCN 80 $\to$ 28, decomposta em `XR_ProcessMenuToggle`, `XR_TracePointerRayForHand`, `XR_ProcessPointerTriggers`, `XR_ProcessPointerScroll`).
    - Modularização de `XR_InitInput` (decomposta em `XR_CreateAllActions`, `XR_SuggestAllBindings`, `XR_AttachActionSetsAndSpaces`).
    - Validação total com build Waf 100% limpo e **24/24 Monado tests 100% GREEN**.

---

## 🎯 Próximo Desafio Prioritário (Fase 09)

1. **Testes de Campo no Dispositivo Físico Meta Quest 3:**
   - Instalação do APK atualizado via ADB (`adb install -r out/xash3d-vr-quest.apk`).
   - Validação da empunhadura física dos controles Touch Plus nos modelos de armas calibrados pelo `vr_weapons.json`.
   - Verificação da renderização da mão secundária `v_hand.mdl` e resposta tátil de recuo.


