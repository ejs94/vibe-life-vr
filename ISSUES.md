# 📋 Xash3D VR — Render Issues & Technical Backlog

Este documento compila os problemas críticos de renderização identificados no Meta Quest 3S (Horizon OS / Android arm64) no branch `feature/openxr-vr`, com a análise de causa raiz e a especificação técnica para a próxima iteração.

---

## ✅ Issue #1: Menu Principal 2D (`mainui`) Invisível / Tela Preta na Inicialização [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `ref/gl_vr/gl_rmain.c`, `ref/gl_vr/gl_opengl.c`, `engine/client/cl_scrn.c`, `engine/client/cl_view.c`
- **Solução Implementada:** 
  1. No `ref/gl_vr/gl_opengl.c`, ativada a detecção e habilitação direta de `GL_FRAMEBUFFER_OBJECT_EXT` e `GL_FRAMEBUFFER_BLIT_EXT` em compilações estáticas (`XASH_GL_STATIC` / `GL4ES`), garantindo que o render target offscreen `tr.targets.screen.fbo` seja alocado com sucesso.
  2. Em `R_RenderXRMenu()`, adicionada verificação/fallback dinâmico garantindo que `GL_CheckRenderTargets()` esteja ativo e `tr.targets.screen` seja blitado diretamente na swapchain Eye 0 do OpenXR antes do encerramento do frame com desvinculação limpa do framebuffer.

---

## ✅ Issue #2: Quad Layer do Menu/HUD Ancorado no Chão da Sala (`STAGE` Space vs `VIEW` Space) [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `engine/platform/openxr/xr_core.c`, `engine/platform/openxr/xr_swapchain.c`
- **Solução Implementada:**
  1. Criado `g_xrViewSpace` com `XR_REFERENCE_SPACE_TYPE_VIEW` na inicialização da sessão OpenXR em `xr_core.c`.
  2. Atualizadas as Quad Layers do menu (`XR_EndMenuFrame`) e HUD (`XR_EndFrame`) em `xr_swapchain.c` para utilizar preferencialmente `g_xrViewSpace` com pose frontal fixa em `z = -1.5f`, mantendo o menu confortavelmente centralizado e flutuando à frente do headset independente da orientação do jogador ou calibração do chão da sala.

---

## ✅ Issue #3: Tela Preta na Cena 3D em Jogo (Áudio Ativo, Imagem Ausente) [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `ref/gl_vr/gl_rmain.c`, `ref/gl_vr/gl_frustum.c`, `ref/gl_vr/gl_frustum.h`, `ref/gl_vr/gl_rsurf.c`
- **Solução Implementada:**
  1. Criada a função unificada `R_ComputeEyeTransform()` em `ref/gl_vr/gl_rmain.c`, combinando translação 6DoF da cabeça, orientação dos olhos e ângulo de locomoção `s_playerTurnYaw`. Adicionado fallback de altura padrão de 1.65m para `s_standingEyeHeight`, impedindo que o ponto de visão seja empurrado 66 unidades para dentro do teto do trem em `c1a0` no frame inicial.
  2. Implementada `GL_FrustumInitVR()` em `ref/gl_vr/gl_frustum.c` e declarada em `ref/gl_vr/gl_frustum.h`, calculando com precisão os 5 planos de corte a partir dos ângulos ópticos assimétricos (`angleLeft, angleRight, angleDown, angleUp`) fornecidos por `XR_GetEyeFrustum()`.
  3. Atualizados `R_SetupFrustum()`, `R_FindViewLeaf()` e `R_SetupFrame()` para calcular e inspecionar a visibilidade a partir de `RI.cullorigin` e dos vetores de visão do olho estéreo ativo (`g_vr_eye`), eliminando o descarte incorreto da geometria do mapa pelo frustum culling não-VR.

---

## ✅ Issue #4: Falta de `glFlush()` antes de `xrReleaseSwapchainImage` [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `engine/platform/openxr/xr_swapchain.c`
- **Solução Implementada:**
  - Em `XR_EndEye()` (`xr_swapchain.c`), adicionado despacho imediato de `glFlush()` via `GL_GetProcAddress("glFlush")` antes da chamada `xrReleaseSwapchainImage()`, assegurando conformidade com OpenXR §10.3 e eliminando atrasos de sincronização de textura nos drivers assíncronos do Quest sem introduzir dependências de link rígidas.

---

## ✅ Issue #5: Fechamento Prematuro do Frame OpenXR e Desconexão do HUD 2D em Jogo [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `ref/gl_vr/gl_rmain.c`, `ref/gl_vr/gl_fbo.c`, `ref/gl_vr/gl_local.h`
- **Solução Implementada:**
  1. Em `ref/gl_vr/gl_fbo.c` e `ref/gl_vr/gl_local.h`, implementada a função `GL_BlendTargetQuad()`, que renderiza o conteúdo de um target offscreen diretamente sobre o framebuffer ativo com mesclagem alfa (`GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`).
  2. Em `ref/gl_vr/gl_rmain.c`, o encerramento da submissão estéreo (`XR_EndEye` e `XR_EndFrame`) foi desacoplado de `R_RenderFrame()` e movido para `R_EndFrame()`.
  3. `R_RenderFrame()` processa a cena 3D nos FBOs de ambos os olhos e limpa `tr.targets.screen.fbo` para `(0, 0, 0, 0)`.
  4. O ciclo do motor chama `V_PostRender()` em seguida, desenhando mira, vida, munição, textos e console sobre `tr.targets.screen.fbo`.
  5. `R_EndFrame()` faz o blend de `tr.targets.screen` sobre os FBOs dos olhos esquerdo e direito, restaura o canal alfa para 1.0f via máscara de cor, chama `XR_EndEye()` para ambos os olhos e finaliza o frame OpenXR com `XR_EndFrame()`.

---

## ✅ Issue #6: OpenXR Graphics Binding GLX no Desktop (`glxFBConfig` Nulo no Monado) [RESOLVIDO]

- **Status:** ✅ Resolvido
- **Módulos Afetados:** `engine/platform/openxr/xr_graphics.c`, `engine/wscript`, `scripts/test_simulated_monado.sh`
- **Solução Implementada:**
  1. Em `engine/platform/openxr/xr_graphics.c`, implementada a recuperação dinâmica de `glxFBConfig` via `glXQueryContext` (`GLX_FBCONFIG_ID`) com fallback para `glXChooseFBConfig`, e consulta de `visualid` via `glXGetFBConfigAttrib(..., GLX_VISUAL_ID, ...)`.
  2. Em `engine/wscript`, adicionadas as bibliotecas `-lGL -lX11` às flags de link do desktop para OpenXR.
  3. Em `scripts/test_simulated_monado.sh`, configuradas as variáveis de ambiente para render offload da NVIDIA e Vulkan ICD correspondente, prevenindo conflito de memória opaca entre drivers em GPUs híbridas (Intel + NVIDIA), além de `XRT_NO_STDIN=true` para execução limpa do daemon em background.

---

# 🚀 Fluxo de Trabalho Recomendado para o Próximo Agente (Agentic Workflow)

Este fluxo foi preparado para permitir iteração rápida, sem depender de bateria de headset físico a cada teste ou compilação demorada de APK.

### 1. Visão Geral da Infraestrutura Pronta
- **Simulador Monado Compilado e Operacional:**
  - Binário do serviço: [`/home/ejs94/Documentos/Repos/monado/build/src/xrt/targets/service/monado-service`](file:///home/ejs94/Documentos/Repos/monado/build/src/xrt/targets/service/monado-service)
  - Manifest OpenXR ativo: [`/home/ejs94/Documentos/Repos/monado/build/openxr_monado-dev.json`](file:///home/ejs94/Documentos/Repos/monado/build/openxr_monado-dev.json)
  - CLI de testes: [`/home/ejs94/Documentos/Repos/monado/build/src/xrt/targets/cli/monado-cli`](file:///home/ejs94/Documentos/Repos/monado/build/src/xrt/targets/cli/monado-cli)
  - Drivers ativados: `DRIVER_SIMULATED` (Headset virtual 6DoF), `DRIVER_QWERTY` (controle por teclado/mouse), `OPENGL_GLX` e `FEATURE_OPENXR`.
- **Script de Automação Rápida:**
  - [`scripts/test_simulated_monado.sh`](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/test_simulated_monado.sh): Executa o serviço em background, roda o Xash3D com timeout controlado de 10s e gera evidências em `out/evidence/monado_<timestamp>/`.

### 2. Validação Realizada com Sucesso

- **Simulador Monado (Desktop Linux):**
  - Executado via `./scripts/test_simulated_monado.sh c1a0` sem crashes.
  - Confirmada inicialização de `XrSession`, alocação de swapchains estéreo GLX e submissão contínua de frames com HUD composto.
- **Meta Quest 3S Físico (Horizon OS / Android arm64):**
  - APK compilado via `./scripts/build_quest_apk.sh` gerando `out/xash3d-vr-quest.apk`.
  - Executado `./scripts/test_quest_auto.sh 35 c1a0` no dispositivo `3487C10GBP00JJ`.
  - Execução estável por 35s ininterruptos no trem do Half-Life sem crash, sem descarte de geometria no frustum e com áudio e vídeo sincronizados.

---

## 📌 Backlog & Próximos Passos de Desenvolvimento

### 🎯 Issue #7: Escala, Margem e Conforto do HUD 2D em VR
- **Severidade:** 🟢 Minor / Conforto do Usuário
- **Módulos Afetados:** `ref/gl_vr/gl_rmain.c`, `engine/client/cl_scrn.c`
- **Contexto:** Com a composição direta do HUD em `tr.targets.screen` sobre os FBOs estéreo, elementos nos cantos da tela (ex: vida à esquerda, munição à direita) podem ficar próximos do limite periférico das lentes Fresnel/Pancake.
- **Objetivo:** Adicionar cvar de margem/escala (`vr_hud_scale` e `vr_hud_offset`) ou suporte alternativo para desenhar o HUD projetado como uma Quad Layer flutuante no espaço 3D à frente do jogador.

### 🎯 Issue #8: Alinhamento de Ângulos de Visada do Viewmodel (Armas 6DoF)
- **Severidade:** 🟡 Medium / Gameplay VR
- **Módulos Afetados:** `engine/platform/openxr/xr_input.c`, `ref/gl_vr/gl_studio.c`
- **Contexto:** Cada arma (pistola 9mm, pé de cabra, shotgun, SMG) possui um centro de pivô e angulação diferente no modelo original GoldSrc.
- **Objetivo:** Calibrar offsets angulares e posicionais por classe de arma (`v_model`) para alinhar naturalmente o cano das armas com a pegada física do controle Meta Quest Touch Plus / Pro.

### 🎯 Issue #9: Feedback Háptico Abrangente
- **Severidade:** 🟢 Minor / Imersão
- **Módulos Afetados:** `engine/platform/openxr/xr_input.c`
- **Contexto:** Suporte a vibração háptica (`XR_Haptic_f`) já está implementado via comando de console.
- **Objetivo:** Disparar pulsos hápticos automaticamente no evento de disparo de armas (`IN_ATTACK`), recebimento de dano e acionamento de alavancas/botões.

