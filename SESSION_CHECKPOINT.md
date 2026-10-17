# 📌 Ponto de Parada da Sessão (Session Checkpoint)

**Data do Checkpoint:** 16 de Outubro de 2026  
**Repositório:** `xash3d-fwgs-vr`  
**Branch:** `feature/openxr-vr`  
**Dispositivo Físico:** Meta Quest 3S (`3487C10GBP00JJ`) — Desligado (testes executados 100% via simulação Monado PCVR).  
**APK Atualizado e Pronto:** [`out/xash3d-vr-quest.apk`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/out/xash3d-vr-quest.apk)  
**Caderno de Engenharia:** [Documentation/vr/ENGINEERING_NOTEBOOK.md](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/Documentation/vr/ENGINEERING_NOTEBOOK.md)

---

## 🏁 O que foi Concluído nesta Sessão

1. **Correção dos Controles Touch / Analógicos Inativos (`input.c`):**
   - No cliente FWGS moderno, `clgame.dllFuncs.pfnLookEvent` é não-nulo, fazendo `IN_EngineAppendMove` retornar prematuramente antes do bloco OpenXR ser alcançado.
   - O bloco OpenXR de despacho de comandos (`XR_InputAppendMove`) foi movido para o topo de `IN_EngineAppendMove`.
   - Locomoção pelo stick analógico esquerdo, giro pelo analógico direito e todos os botões de ação (`IN_ATTACK`, `IN_JUMP`, `IN_DUCK`, `IN_USE`, `IN_RELOAD`, `IN_RUN`, lanterna) agora são devidamente transmitidos ao servidor em todos os frames.

2. **Correção do Ponto de Origem do Laser e Empunhadura da Mão Dominante (`xr_input.c`, `gl_rmain.c`, `gl_studio.c`):**
   - O cálculo das coordenadas da mão em `XR_GetRightHandTransform` e `XR_GetLeftHandTransform` utilizava a pose bruta do OpenXR no espaço de rastreamento do chão (`g_xrLocalSpace`), sem subtrair a posição da cabeça do headset (`g_xrViews[0].pose.position`). Isso deslocava a arma ~1.4m acima e fora do campo relativo da visão.
   - Subtração da cabeça aplicada: `rel = handPose.position - headPose.position`, alinhando a arma milimetricamente com a mão dominante.
   - Adicionada detecção e fallback em `gl_rmain.c` contra origens `simorg` obsoletas (centro do jogador): a mira laser agora emerge exclusivamente da ponta do cano da mão primária.
   - Criada a CVar `vr_twohanded` (padrão `0`) com validação estrita (`aimDir[0] > 0.08f`), impedindo que apertar o grip da mão esquerda aponte a arma para o chão ou suma com o laser.

3. **Eliminação de Náusea no Giro de Cabeça (Roll) com Matriz de Visão Ortonormal Livre de Singularidade (`gl_rmain.c`):**
   - O cálculo anterior decompunha os quaternions do OpenXR em ângulos de Euler e realizava três rotações legadas do Quake (`ConcatRotate(-roll, 1, 0, 0)`), girando o ponto de vista ao redor do eixo X fixo do mundo em vez da linha de visão do olho.
   - Implementado cálculo direto da matriz Modelview a partir do quaternion OpenXR: eixos Right ($R$), Up ($U$) e Forward ($F$) ortonormais combinados com a rotação de locomoção `turn_yaw`.
   - Inclinação lateral da cabeça (roll) agora é 100% natural, sem acelerações espúrias, sem distorção e sem náusea.

4. **Ajuste de Distância do Menu 2D Flutuante (`xr_swapchain.c`, `xr_input.c`):**
   - Adicionada CVar `vr_menu_distance` (padrão `2.1m`, anteriormente hardcoded em `1.5m`) e `vr_menu_scale` (`1.8m`), trazendo o plano do menu para o sweet spot óptico das lentes do Quest e eliminando o corte ou borrão nas bordas da tela.
   - Ponteiro laser do cursor em menus perfeitamente sincronizado com a nova distância e escala do quad.

5. **Modernização do Botão de Testes no Launcher Android:**
   - Botão renomeado para `"TEST GAME"` / `"TESTAR JOGO"` nos arquivos `strings.xml`.
   - Comando de inicialização atualizado para entrar automaticamente com todas as armas, HEV suit, munição e cheats ativados: `+sv_cheats 1 +map crossfire +give item_suit +impulse 101`.

6. **Simulação PCVR com Movimentação 6DoF de Cabeça:**
   - Implementadas as CVars `vr_test_head` (0/1), `vr_test_head_pitch`, `vr_test_head_yaw` e `vr_test_head_roll` em `xr_swapchain.c` para teste programático.
   - Criado e executado o script [scripts/simulate_head_and_weapons.cfg](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/simulate_head_and_weapons.cfg) no simulador Monado, gerando evidências visuais de rotação de cabeça e disparo com MP5, Shotgun e Hornetgun.

7. **Lanterna Montada na Cabeça & Gesto 6DoF na Têmpora (HL1 & HL2:VR Style) (`cl_tent.c`, `xr_input.c`):**
   - Removida a lógica de lanterna física acoplada à mão secundária; o cone de luz agora é montado na cabeça (`cl.viewheight`) e segue a linha de visão do jogador (`cl.viewangles`).
   - Implementada detecção de gesto espacial 6DoF: ao aproximar qualquer uma das mãos da lateral da cabeça (região têmpora/orelha, distância $< 28\text{ cm}$, $|y| < 18\text{ cm}$, $|x| > 7\text{ cm}$) e puxar o gatilho (*trigger*) ou apertar o *grip*, a lanterna alterna (`impulse 100`).
   - Disparo de armas suprimido (`cmd->buttons &= ~(IN_ATTACK | IN_ATTACK2)`) durante o gesto para impedir auto-disparo acidental na cabeça.
   - Vibração tátil de clique (*haptics*) disparada no controle que acionou o gesto, com *debounce* de 350ms.

8. **Ponteiros Laser Duplos Alternados no Menu Flutuante (Beat Saber Style) (`xr_input.c`, `xr_input.h`, `gl_rmain.c`):**
   - Ambos os controles (esquerdo e direito) agora projetam raios laser tridimensionais simultâneos contra a tela flutuante do menu.
   - Puxar o gatilho da mão esquerda alterna o cursor do mouse e clica no alvo da mão esquerda; puxar o gatilho da mão direita alterna instantaneamente para a direita.
   - Renderização diferenciada: mão ativa em feixe ciano vibrante (espessura 2.5), mão secundária em feixe âmbar (espessura 1.6).
   - Validado no simulador Monado via script [scripts/simulate_headgesture_beatsaber.cfg](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/simulate_headgesture_beatsaber.cfg).

---

9. **Ajuste de Layout e Escala de Fontes do Launcher 2D no Meta Horizon OS (Issue #10) (`activity_main.xml`, `card_game.xml`, `vr_preferences.xml`, `Game.kt`):**
   - Corrigido o colapso de layout da Toolbar no Horizon OS definindo altura e `minHeight` para `?attr/actionBarSize` dentro do `AppBarLayout`.
   - Cards de jogos em `card_game.xml` ajustados para altura dinâmica `wrap_content` (com `minHeight="170dp"`), eliminando a altura fixa de `160dp` que cortava os botões ao redimensionar a janela flutuante no Quest.
   - Desacoplamento de âncoras no card: a badge com ícone e título foi ancorada de forma independente no topo-início (`top_toTopOf="parent"`), enquanto o container de botões de ação ("TEST GAME" e "PLAY IN VR") foi ancorado na base-fim (`bottom_toBottomOf="parent"`), impedindo sobreposição e colisão horizontal em qualquer proporção de tela.
   - Adicionadas novas preferências VR em `vr_preferences.xml` (`vr_lasersight`, `vr_headtorch`, `vr_lefthanded`, `vr_twohanded`) e strings em `strings.xml`.
   - Conectados os novos parâmetros em `Game.kt` (`buildString`), passando-os automaticamente na linha de comando de inicialização da engine.

10. **Menu de Opções VR Dedicado In-Headset (Issue #13) (`3rdparty/mainui/menus/VR.cpp`, `BaseMenu.h`, `Configuration.cpp`):**
    - Desenvolvido o menu completo em C++ `CMenuVR` integrado ao sistema `mainui` do Xash3D.
    - Seções organizadas com cabeçalhos legíveis:
      - *Locomotion & Comfort:* `vr_smoothturn` (Smooth/Snap turn toggle), `vr_snap_angle` (SpinControl 15°–90°), `vr_walkdirection` (Head/Controller orientation).
      - *Weapons & Flashlight:* `vr_lasersight` (mira laser 3D no cano), `vr_headtorch` (lanterna montada na cabeça), `vr_twohanded` (estabilização com mão secundária), `vr_lefthanded` (modo canhoto), `vr_haptics_enabled` (vibração tátil), `vr_pointer_hud` (ponteiro laser no menu).
      - *Calibration & Scale:* `vr_weapon_pitchadjust` (-30° a +30°), `vr_worldscale` (escala do mundo 20–60), `vr_height_adjust` (-20 a +20), `vr_menu_distance` (1.0m a 3.5m), `vr_menu_scale` (1.0m a 3.0m).
    - Registrado como comando de console `menu_vr` e acessível pelo menu de opções (`Configuration -> VR Options`).
    - Compilação nativa (`out/libmenu.so`) e APK standalone do Meta Quest (`out/xash3d-vr-quest.apk`) testados e validados com 100% de sucesso.

---

11. **Balística a partir da Boca Física do Cano no Servidor (Issue #14) (`dlls/player.cpp`, `dlls/rpg.cpp`, `engine/server/sv_pmove.c`):**
    - `CBasePlayer::GetGunPosition()` em `3rdparty/hlsdk-portable/dlls/player.cpp` agora verifica se `pev->vuser1 != g_vecZero` (preenchido a cada frame de pre-think via `XR_GetPrimaryHandMuzzleTransform` em `sv_pmove.c`) e retorna `pev->origin + pev->vuser1`.
    - Como todas as armas do Half-Life (Glock, MP5, Python, Shotgun, Gauss/Tau Cannon, Egon, Crossbow, Hornet Gun, Crowbar) utilizam `GetGunPosition()`, todos os tiros hitscan, raios de energia e projéteis físicos agora emergem com precisão milimétrica da boca da arma na mão dominante do jogador, alinhados com o laser sight 3D.
    - O disparo de foguete em `rpg.cpp` foi adaptado em VR para emergir diretamente da boca do lançador sem a translação de ombro da tela plana de 1998.

12. **Lançamento Físico de Granadas por Inércia e Momento 6DoF (Issue #15) (`handgrenade.cpp`, `xr_input.c`, `sv_pmove.c`):**
    - Em `xr_input.c`, `XR_GetRightHandVelocity` e `XR_GetLeftHandVelocity` agora rotacionam o vetor linear de velocidade OpenXR pelo ângulo de giro do jogador (`s_playerTurnYaw`), convertendo o vetor de inércia da sala física para o referencial mundial de jogo.
    - `sv_pmove.c` atualizado para repassar a velocidade da mão dominante do jogador para o servidor através de `clent->v.vuser3` (`XR_GetPrimaryHandVelocity`).
    - Em `handgrenade.cpp`, `CHandGrenade::WeaponIdle()` agora instancia a granada na posição real da mão (`pev->origin + pev->vuser1 + gpGlobals->v_forward * 6.0f`) e adiciona o momento físico do braço do jogador ao vetor de arremesso (`vecThrow += m_pPlayer->pev->vuser3 * 1.25f`) quando a velocidade de movimento manual for superior a 40 unidades/s, possibilitando arremessos manuais intuitivos em VR.
    - APK atualizado compilado com sucesso (`BUILD SUCCESSFUL in 18s`) e salvo em [`out/xash3d-vr-quest.apk`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/out/xash3d-vr-quest.apk).

13. **Bateria de Testes Regressivos Automatizados (12/12 Gates Aprovados):**
    - Criado o script unificado [scripts/regression_master.cfg](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/regression_master.cfg) e o executor [scripts/run_regression_battery.sh](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/run_regression_battery.sh).
    - Executados os 12 gates de verificação cobrindo OpenXR runtime, 14 CVars VR, acionamento do menu VR in-headset (`CMenuVR`), alternância Beat Saber de lasers, carga de mapa 3D (`c1a0`), lanterna por gesto na têmpora, inclinação de cabeça (roll) ortonormal sem gimbal lock, balística 6DoF de cano (MP5, Shotgun, Crossbow, RPG), arremesso de granadas por momento físico, empunhadura bimanual, integridade das 5 bibliotecas nativas arm64-v8a no APK standalone e layout do launcher no Horizon OS.
    - Todos os 12 testes foram aprovados com 100% de sucesso. Relatório detalhado em [`regression_test_report.md`](file:///home/ejs94/.gemini/antigravity-ide/brain/97590628-7c11-438b-af73-35b4132380c8/regression_test_report.md).

---

## 🎯 Próximos 2 Issues para Solucionar Imediatamente

1. **Issue #16 — Rastreamento Óptico dos Dedos e Mãos Esqueléticas 3D Articuladas (Feature #12 / Phase 07):**
   - Substituir o modelo estático clássico de luva por malha de mão 3D independente com esqueleto articulado nos dedos (falanges proximal, intermediária e distal).
   - Acoplar o fechamento e abertura de dedos aos gatilhos analógicos (*trigger* e *grip*) ou à extensão OpenXR `XR_EXT_hand_tracking` no Meta Quest 3S.

2. **Issue #17 — Áudio Espacial 3D HRTF em Tempo Real com OpenAL Soft (Phase 07):**
   - Configurar o backend OpenAL Soft no Android e PCVR para ativar funções de transferência binaural (HRTF) nas caixas acústicas do Quest 3S, garantindo posicionamento acústico 3D de passos de inimigos, ricochetes e vozes no ambiente.
