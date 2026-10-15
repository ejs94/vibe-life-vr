# 🥽 Xash3D VR (Half-Life VR) — Native OpenXR Port

[![OpenXR Standard](https://img.shields.io/badge/OpenXR-1.0%2F1.1%20Compliant-blue.svg)](https://www.khronos.org/openxr/)
[![Platforms](https://img.shields.io/badge/Platforms-Meta%20Quest%20Standalone%20%7C%20Linux%20PCVR-brightgreen.svg)]()
[![Target Hardware](https://img.shields.io/badge/Hardware-Quest%201%2F2%2FPro%2F3%2F3S-orange.svg)]()
[![Engine](https://img.shields.io/badge/Engine-Xash3D%20FWGS%20v0.21-purple.svg)](https://github.com/FWGS/xash3d-fwgs)
[![AI-Assisted](https://img.shields.io/badge/Engineering-AI--Assisted%20%28Pair%20Programming%29-indigo.svg)]()

> **Xash3D VR** é a porta de Realidade Virtual para o motor **Xash3D FWGS**, trazendo a experiência completa do clássico **Half-Life** (e mods GoldSrc) para headsets VR utilizando o padrão Khronos **OpenXR puro**.
>
> Projetado com arquitetura C99 moderna e desacoplada, o projeto roda **nativamente no Meta Quest Standalone** (Horizon OS / Android arm64-v8a) e em **Desktop Linux PCVR** (Monado, WiVRn, SteamVR) sem depender de bibliotecas legadas ou proprietárias de fabricantes (zero VrApi, zero dependências fechadas).

---

## 🤖 Engenharia Assistida por Inteligência Artificial (AI-Assisted Engineering)

> [!NOTE]
> **Transparência e Inovação Técnica:**  
> Este projeto é ativamente desenvolvido e mantido com assistência de **Inteligência Artificial de Fronteira** (Pair Programming com modelos avançados do Google DeepMind / Antigravity).

A assistência de IA é empregada continuamente ao longo de todo o ciclo de engenharia do projeto, destacando-se em:
* **Diagnóstico de Drivers Gráficos Móveis:** Identificação cirúrgica de comportamentos não documentados de hardware na arquitetura Qualcomm Adreno TBDR (Snapdragon XR2 Gen 2 no Quest 3S), como fast-clears de GMEM tile memory e a virtualização de tabelas de texturas no GL4ES que desvinculavam FBOs da swapchain do OpenXR gerando telas pretas.
* **Matemática Espacial 3D e Ótica VR:** Dedução e implementação dos vetores de projeção assimétrica por olho (`xrLocateViews`), cálculo trigonométrico do frustum de culling 6DoF sem descarte indevido de nós do mundo, e conversão de quaternions de rastreamento para ângulos de Euler do GoldSrc.
* **Automação e Portões de Qualidade (Quality Gates):** Desenvolvimento de scripts de telemetria em tempo real ([`test_quest_auto.sh`](scripts/test_quest_auto.sh) e [`quest_battery.sh`](scripts/quest_battery.sh)) com leitura direta de buffers de swapchain (`glReadPixels` em PPM/PNG), screencaps do compositor do Meta Horizon OS e validação matemática de canais de cor.

---

## 🚀 Status do Projeto & Roadmap

| Fase | Descrição | Status | Validação Empírica |
| :---: | :--- | :---: | :--- |
| **01** | **OpenXR Baseline & Dual-Platform Bring-Up** | 🟢 **Concluído** | Session state machine, graphics binding (GLX / EGL), swapchains estéreo operacionais. |
| **02** | **Renderização Estéreo, Frustum Assimétrico & 6DoF** | 🟢 **Concluído** | Renderização 3D estéreo com iluminação, geometrias e skybox ativa nos mapas `crossfire` e `c1a0`. Validação via dump de swapchain (`Mean RGB > 60-117`) e screencap do Horizon OS. |
| **03** | **Universal Action Sets, Touch Poses & Locomoção** | 🟡 **Ativo** | Controles Meta Quest Touch, analógicos para smooth/snap turn, botões de ação e locomoção física. |
| **04** | **Desacoplamento de Armas 6DoF & Lanterna Física** | ⚪ Planejado | Mira de armas desacoplada do olhar e lanterna independente na mão secundária. |
| **05** | **UI Espacial no Headset & Menu VR** | ⚪ Planejado | Pointer laser 3D e menu dedicado `CMenuVR` para conforto e calibração em jogo. |
| **06** | **Balística de Servidor & Feedback Háptico** | ⚪ Planejado | Origem física de projéteis e recoil tátil nos controles. |
| **07** | **Presença Imersiva & Áudio 3D HRTF** | ⚪ Planejado | Mãos virtuais com articulação e áudio espacializado via OpenAL Soft. |
| **08** | **Expansões (Opposing Force, Blue Shift)** | ⚪ Planejado | Suporte às campanhas clássicas e mods GoldSrc. |

Para o acompanhamento detalhado de cada fase, consulte o [VR_PORT_PLAN.md](VR_PORT_PLAN.md) e o histórico de resolução em [ISSUES.md](ISSUES.md).

---

## ✨ Recursos Principais

* **Padrão Khronos OpenXR 1.0/1.1 Nativo:** Código C99 modular sem wrappers obsoletos (sem VrApi).
* **Compatibilidade Dual-Platform:**
  * **Meta Quest Standalone:** Quest 1, Quest 2, Quest Pro, Quest 3 e Quest 3S (Horizon OS / Android arm64-v8a).
  * **Desktop PCVR (Linux):** Monado (simulado ou com headset físico), WiVRn, SteamVR e ALVR.
* **Launcher Modernizado para Horizon OS (Kotlin):**
  * Desenvolvido seguindo as **Diretrizes de Design da Meta** (alvos de toque mínimos de 48dp, tipografia ergonômica de 14-18sp, cantos arredondados de 12dp).
  * Painel centrado e delimitado a **960x540dp**, eliminando esticamento lateral excessivo e fadiga visual no headset.
  * **Botão dedicado "TESTAR ARMAS"**: Carrega instantaneamente o mapa de testes (`crossfire`) com todas as armas do Half-Life espalhadas pelo chão para teste imediato de mecânicas e mira.
* **Renderizador Dedicado `ref_gl_vr`:**
  * Apresentação estéreo com cálculo de frustum ótico independente para cada olho.
  * Registro e bypass de texturas externas da swapchain do OpenXR via GL4ES e GLES nativo.
  * Preservação de canais de cor e endurecimento de alfa contra blends indevidos do compositor TimeWarp.
* **Ferramental de Diagnóstico e Saúde:**
  * Monitoramento de bateria em tempo real com voltagem de precisão em mV/V ([`scripts/quest_battery.sh`](scripts/quest_battery.sh)).
  * Pipeline de testes automatizados com extração de buffer e análise de pixels ([`scripts/test_quest_auto.sh`](scripts/test_quest_auto.sh)).

---

## 🛠️ Como Compilar e Executar

### 🥽 1. Meta Quest Standalone (Android arm64)

#### Pré-requisitos:
* Android SDK e NDK configurados (ou Android Studio instalado).
* Headset Meta Quest com Modo Desenvolvedor ativo e conectado via USB ou Wi-Fi ADB.

#### Compilação e Instalação do APK:
```bash
# 1. Compilar o APK Standalone do Quest
./scripts/build_quest_apk.sh

# 2. Instalar no headset via ADB
adb install -r out/xash3d-vr-quest.apk

# 3. Copiar os dados do jogo (pasta valve do Half-Life oficial do Steam)
adb push /caminho/para/Half-Life/valve /sdcard/xash/valve
```

#### Teste Automatizado com Validação de Pixels:
```bash
# Executa 25 segundos no mapa crossfire, extrai o buffer de renderização e confirma pixels coloridos
./scripts/test_quest_auto.sh 25 crossfire
```

---

### 🖥️ 2. Desktop Linux PCVR (Monado / WiVRn / SteamVR)

#### Compilação:
```bash
# 1. Configurar o build com suporte a OpenXR e Renderer VR
./waf configure --enable-openxr --enable-gl-vr

# 2. Compilar e instalar localmente
./waf build
./waf install --destdir=./out
```

#### Execução com WiVRn ou Monado Simulado:
```bash
# Teste automatizado com runtime simulado do Monado
./scripts/test_simulated_monado.sh crossfire

# Ou iniciar o jogo diretamente em VR
./scripts/run_wivrn.sh
```

---

## 📄 Licença & Reconhecimentos

* **Motor Base:** [Xash3D FWGS](https://github.com/FWGS/xash3d-fwgs) — Licenciado sob GNU GPLv3.
* **Valve Corporation:** Criadores do Half-Life e do motor GoldSrc original.
* **Team Beef (Lambda1VR):** Agradecimento especial pelos insights pioneiros sobre arquitetura de FBOs dedicados e tratamento de canais alfa em hardware móvel.
* **Khronos Group:** Pelo padrão aberto OpenXR e especificações do ecossistema de Realidade Estendida.
* **AI Pair Programming:** Desenvolvimento e diagnósticos assistidos por modelos avançados de Inteligência Artificial do Google DeepMind.
