# 📓 Caderno de Engenharia & Anotações de Soluções (Xash3D VR)

Este documento registra a genealogia técnica do port **Xash3D VR (Meta Quest & PCVR OpenXR)**, detalhando o que foi desenvolvido como **solução própria e original** através de testes e depuração empírica, o que foi **adaptado ou inspirado** de projetos anteriores (*Lambda1VR*, *CSVR*, *vr-modding-playbook*), e os desafios arquiteturais superados.

---

## 🏛️ 1. Filosofia Arquitetural do Projeto

O objetivo deste projeto não é criar um fork descartável ou uma cópia cega de código legado, mas sim construir um **port limpo, universal e moderno** construído sobre o upstream oficial `xash3d-fwgs`:

| Aspecto | Lambda1VR (Legado) | CSVR | Nosso Port (Xash3D VR) |
| :--- | :--- | :--- | :--- |
| **Padrão VR** | Oculus VrApi (C++ proprietário, descontinuado) | OpenVR / SteamVR clássico | **Khronos OpenXR 1.0/1.1 (C99 universal)** |
| **Plataformas** | Exclusivo Quest 1/2 (32-bit armeabi-v7a) | Exclusivo PC Windows | **Dual-Target: Meta Quest 3S (64-bit arm64-v8a) & PCVR Linux/Windows** |
| **Build System** | Makefiles manuais legados com NDK antigo | MSVC / Visual Studio | **Waf + Python + CMake + Modern Android Gradle (NDK r27c)** |
| **Engine Base** | Xash3D antigo pré-FWGS | Half-Life SDK 2.3 mod | **Upstream Xash3D-FWGS (ramo moderno, multi-arquitetura)** |
| **Testes & CI** | Testes apenas manuais em headset físico | Testes em headset SteamVR | **Simulador Monado Headless com Captura de Framebuffer & CI** |

---

## 💡 2. Soluções 100% Próprias (Desenvolvidas e Depuradas via Testes)

As seguintes soluções foram concebidas, desenvolvidas e validadas empiricamente neste repositório:

### 2.1. Renderização Estéreo sem Tela Preta no Quest 3S (`gl4es` Texture Binding)
* **O Problema:** No Meta Quest 3S (Android / GLES), o renderizador `gl_vr` utiliza a camada de compatibilidade `gl4es` para traduzir chamadas OpenGL desktop para OpenGL ES 3.2. A textura de swapchain retornada pelo runtime OpenXR (`xrEnumerateSwapchainImages`) ficava invisível ou preta porque a textura nativa do driver não estava registrada no dicionário de estados de textura do `gl4es`.
* **Nossa Solução Própria:** 
  - Integramos uma chamada de registro transparente antes de cada passe de desenho estéreo:
    ```c
    gl4es_glBindTexture( GL_TEXTURE_2D, g_xrEyeSwapchains[eye].images[imageIndex] );
    ```
  - Forçamos o anexo direto dos buffers de cor ao Framebuffer Object (`GL_COLOR_ATTACHMENT0`) com sincronização explícita de `xrAcquireSwapchainImage`, `xrWaitSwapchainImage` e `xrReleaseSwapchainImage`.
  - **Evidência:** Resolução definitiva documentada no log e validação com 72-90 FPS contínuos no Quest 3S.

### 2.2. Frustum Culling Estéreo Independente & Desacoplamento da Câmera
* **O Problema:** Ao mover a cabeça fisicamente no Guardian ou inclinar o headset, o motor GoldSrc tradicional (que possui apenas um frustum de câmera monocular centrado no tronco do jogador) calculava o culling incorretamente. Isso causava o desaparecimento repentino de paredes, tetos e chão na visão periférica e no olho secundário.
* **Nossa Solução Própria:**
  - Em `ref/gl_vr/gl_cull.c`, recalculamos os planos de corte do frustum (`RI.frustum`) individualmente por olho no espaço estéreo (`R_ComputeEyeTransform`), somando o deslocamento do headset na sala (`room_forward`, `room_right`, `room_up`) rotacionado pelo ângulo de locomoção (`XR_GetPlayerTurnYaw()`).
  - O jogador agora pode andar livremente dentro do espaço do Guardian de 2 a 5 metros sem cortar a geometria do cenário.

### 2.3. Simulador de Ações Automatizadas Monado PCVR & Dump de Olho (`vr_dumpeye`)
* **O Problema:** Desenvolver para VR frequentemente cria um gargalo doloroso de "colocar o headset, tirar o headset, transferir APK, carregar bateria".
* **Nossa Solução Própria:**
  - Criamos o harness de teste automatizado [scripts/test_simulated_monado.sh](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/scripts/test_simulated_monado.sh) executando o runtime OpenXR Monado em modo mock.
  - Implementamos o comando nativo `vr_dumpeye [nome.ppm]` em [ref/gl_vr/gl_rmain.c](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/ref/gl_vr/gl_rmain.c) que extrai o framebuffer estéreo diretamente da memória GPU e o converte para PNG.
  - Implementamos CVars de simulação 6DoF de mãos (`vr_test_hands 1`, `vr_test_hand_pitch`, `vr_test_hand_yaw`), permitindo testes programáticos completos de mira para cima, para baixo, troca de armas e locomoção em ambiente headless.

### 2.4. Estabilizador Físico de Duas Mãos com Geometria GoldSrc
* **O Problema:** Implementações anteriores em outros ports usavam aproximações empíricas ou matrizes do VrApi que falhavam em rotações verticais extremas.
* **Nossa Solução Própria:**
  - Em [engine/platform/openxr/xr_input.c](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/engine/platform/openxr/xr_input.c), formalizamos a matemática de estabilização diretamente no espaço vetorial do GoldSrc:
    $$aimDir = frontHand - rearHand$$
    $$\Delta X = (rear.z - front.z), \quad \Delta Y = (rear.x - front.x), \quad \Delta Z = (front.y - rear.y)$$
  - Condicionamos a ativação ao Grip da mão de apoio (`grip > 0.4f`) e a um raio físico ergonomicamente plausível (entre 12 cm e 55 cm de distância entre as mãos).
  - O vetor resultante recalcula os ângulos Euler e transmite-os tanto para o servidor quanto para o cano da arma e a mira a laser.

### 2.5. Suporte Universal e Dinâmico a Canhotos (`vr_lefthanded`)
* **O Problema:** A maioria dos ports exige reinicialização do aplicativo ou possui lógica de canhoto fixa que quebra os analógicos de locomoção.
* **Nossa Solução Própria:**
  - Desenvolvemos as abstrações universais `XR_GetPrimaryHandTransform()` e `XR_GetPrimaryHandVelocity()` em `xr_input.c`.
  - A CVar `vr_lefthanded` inverte dinamicamente em tempo de execução:
    * Os analógicos de locomoção e rotação;
    * Os gatilhos de tiro primário e secundário;
    * A mão de ancoragem da arma no renderizador `gl_studio.c`;
    * A mão de emissão da lanterna física e da mira laser.

### 2.6. Registro Antecipado de CVars no `Host_Init`
* **O Problema:** Quando `config.cfg` ou parâmetros de linha de comando tentavam configurar CVars de VR durante o boot, o console emitia avisos de `Unknown command "vr_*"` porque o subsistema OpenXR só inicializava mais tarde durante o carregamento do renderizador.
* **Nossa Solução Própria:**
  - Criamos a função antecipada `XR_RegisterCVars()` exposta por `xr_core.c` e invocada logo na inicialização principal do host em [engine/common/host.c](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/engine/common/host.c), garantindo que todas as opções de VR estejam arquivadas e disponíveis no console desde o primeiro milissegundo de execução.

---

## 🔄 3. Soluções Inspiradas e Adaptadas de Projetos Anteriores

Aqui estão as ideias que analisamos a partir do *Lambda1VR*, *CSVR* e do *vr-modding-playbook*, indicando como as adaptamos para a nossa arquitetura OpenXR:

### 3.1. Conversão de Espaços de Coordenadas (OpenXR $\leftrightarrow$ GoldSrc)
* **Origem da Referência:** *Lambda1VR* (`convertFromVRtoHL` em `cl_view.c`).
* **Como Adaptamos:**
  - No Lambda1VR, a conversão vinha do Oculus VrApi. No nosso código, adaptamos a convenção de conversão matricial para OpenXR:
    $$\text{GoldSrc } X (\text{Frente}) = - \text{OpenXR } Z$$
    $$\text{GoldSrc } Y (\text{Esquerda}) = - \text{OpenXR } X$$
    $$\text{GoldSrc } Z (\text{Cima}) = \text{OpenXR } Y$$
  - Escalonamento linear com a CVar `vr_worldscale` (padrão 40.0 unidades GoldSrc por metro real).

### 3.2. Mira a Laser 3D no Renderizador
* **Origem da Referência:** *Lambda1VR* (`gl_rmain.c` laser sight) e *CSVR*.
* **Como Adaptamos:**
  - Implementamos em [ref/gl_vr/gl_rmain.c](file:///home/ejs94/Documentos/Repos/xash3d-fwgs-vr/ref/gl_vr/gl_rmain.c) a emissão de um feixe de luz usando `GL_LINES` com `GL_BLEND` aditivo (`GL_SRC_ALPHA`, `GL_ONE`) que parte do cano da mão primária (`XR_GetPrimaryHandTransform`) e se estende por 2048 unidades GoldSrc no vetor `forward`.
  - Corrigimos a rotação da origem e do feixe pelo `turn_yaw` do jogador para manter coerência espacial em 360°.

### 3.3. Locomoção Snap Turn & Desacoplamento de Olhar vs Controle
* **Origem da Referência:** Prática consagrada documentada em *vr-modding-playbook* e presente em *Lambda1VR*.
* **Como Adaptamos:**
  - Criamos uma máquina de estados de debouncing de analógico para snap turn de 45° (`vr_snap_angle`) com feedback de vibração háptica Khronos OpenXR (`XR_TriggerHapticEffect`).
  - Implementamos a opção `vr_walkdirection`:
    - `0`: Orientado pelo Headset (direção do olhar no mundo);
    - `1`: Orientado pelo Controle (direção para onde o controle está apontando).

---

## 🎯 4. Desafio Atual: A Ancoragem de Armas (Grip vs Aim) e o Áudio

Nossos testes recentes evidenciaram dois detalhes cruciais que foram investigados:

### 4.1. O Problema da Geometria dos Modelos de Arma de 1998
* **Diagnóstico:** No Half-Life original de 1998, os modelos de visão em 1ª pessoa (`models/v_*.mdl`) foram modelados com a câmera na origem $(0,0,0)$ e um braço rígido estendido para frente.
* **Como o Lambda1VR contornou:** O Lambda1VR utilizou assets 3D substituídos (`models/v_shotgun.mdl`, `models/v_hand.mdl`, etc.), onde a origem da malha foi re-exportada para o cabo da arma.
* **Nossa Estratégia Planejada:**
  1. Para preservar total compatibilidade com qualquer mod ou cópia limpa do Half-Life sem depender de mods externos de assets: implementar um sistema de **Grip Offsets** configurável por arma (`vr_weapon_offset_forward`, `vr_weapon_offset_right`, `vr_weapon_offset_up`, `vr_weapon_pitchadjust`) que translada a malha do modelo de 1998 para encaixar a empunhadura no controle físico.
  2. Oferecer suporte automático para os modelos remodelados de VR caso estejam presentes na pasta `valve/models/`.

### 4.2. O Problema dos Delays de Deploy e Áudio
* **Diagnóstico:** O motor Half-Life possui travas rígidas de animação de saque (`m_flNextPrimaryAttack = time + 1.5s`). Comandos rápidos de `+attack` em scripts automatizados sem intervalo eram descartados pela DLL de jogo, impedindo a reprodução dos sons `.wav`.
* **Solução:** Ajuste dos scripts de simulação e controle para respeitar o tempo de deploy de cada arma antes de disparar.

---

*Caderno mantido atualizado a cada avanço relevante da engenharia do port VR.*
