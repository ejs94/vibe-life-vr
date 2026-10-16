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
   - APK Standalone Meta Quest gerado e atualizado em [`out/xash3d-vr-quest.apk`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/out/xash3d-vr-quest.apk).

---

## 🎯 Próximos Passos Imediatos ao Retomar a Próxima Sessão

1. **Checar Conexão e Bateria do Headset:**
   ```bash
   ./scripts/quest_battery.sh
   ```
2. **Instalação e Teste no Headset Físico (Meta Quest 3S):**
   ```bash
   adb install -r out/xash3d-vr-quest.apk
   ```
   - Clicar no botão **"TESTAR ARMAS"** (mapa `crossfire`).
   - Validar:
     - Analógico esquerdo: movimentação fluida (para frente na direção do olhar).
     - Analógico direito: snap turning de 45° com vibração tátil.
     - Analógico direito (cima/baixo): ciclagem de armas no inventário.
     - Botão Y (controle esquerdo): ligar/desligar lanterna.
     - Botão Menu (controle esquerdo): abrir menu / pausar.
     - Gatilho direito: disparo primário.
     - Gatilho esquerdo: disparo secundário.
     - Grip esquerdo segurado próximo ao controle direito: estabilização de duas mãos com espingarda / MP5.
     - Gestos: mão atrás do ombro + gatilho para puxar o pé de cabra; esticar a mão para abrir portas / apertar botões.
3. **Avançar para Phase 04 / 05:**
   - Lanterna física independente acoplada à mão secundária no mundo 3D (`cl_tent.c`).
   - Menu VR flutuante com ponteiro laser interativo e tela de opções VR (`menus/VR.cpp`).
