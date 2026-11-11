# Quest field reports triage

**Status:** working backlog. No item below is claimed fixed.

This page preserves the two Quest reports from 2026-10-18 and 2026-10-22 and
turns them into verifiable work. The original loose note lived outside the
repository and was removed after this triage. Quotes are kept verbatim in the
reporter's language; the classification is the project's.

How to read `State`:

- `verify` - a later commit may have changed the behaviour; reproduce on the
  current APK before opening work.
- `open` - no code path is known to address it.
- `tooling` - the request is about the asset/authoring workflow, not gameplay.

## Report of 2026-10-18

| # | Verbatim report | State | Area | Next action |
|---|---|---|---|---|
| 1 | "Os 3 vetores estão certos para algumas armas, há armas que ainda está saindo a balistica do centro de um olho." | verify | firing line | Reproduce on the headset; `D-024` changed the direction source, HIL validation is still pending in [`STATUS.md`](../STATUS.md). |
| 2 | "Armas como Tau Cannon, Gluon Gun, Hornet Gun / Hivehand, estão vesgas em relação ao laser e de onde sai os projeteis." | verify | firing line | Check `muzzle_pos`/`muzzle_pos2` on those three models; models without `muzzle_pos2` fall back to `muzzle_pos - grip`. |
| 3 | "O menu ... está flutuando muito longe e não centraliza quando aberto o botão para recentralizar." | verify | VR UI | `897514c4` and `5a12eabb` changed the menu anchor space; reproduce with recenter. |
| 4 | "O roll das armas estão invertidas ... do que estou girando minha mão normal." | verify | pose | `84be66ec` mirrors left-handed grip rotation; confirm right-handed roll is unchanged. |
| 5 | "Não existe mãos flutuantes, a offhand sempre está atrelada a arma." | verify | hands | `b4273467` rebuilt the standalone hands; check `vr_hands_always_visible` and the offhand layer. |
| 6 | "A posição das armas ainda está descentralizada de onde fica o controle." | verify | pose | Compare grip pose and viewmodel anchor; do not add a second offset (D-002). |
| 7 | "O personagem não consegue subir escada e fica preso." | open | locomotion | Candidate for the Box3D character mover stage (S4 in [`BOX3D.md`](BOX3D.md)). |
| 8 | "Algumas vezes quando estou andando com o analogico parece que ele se perde na direção e vai pra uma direção oposta." | open | locomotion | Same class as item 12; add a deterministic stick regression. |
| 9 | "O pé de cabra está muito deslocado, e não faz o ataque quando o balanço com certa velocidade." | open | melee | `XR_ProcessPhysicalMeleeSwing` exists; reproduce the displacement and the swing threshold. |
| 10 | "Laser trip mine está invisivel, com duas mãos flutuantes onde ele deveria estar." | open | viewmodel | Check the tripmine model route and the offhand-only draw path. |
| 11 | "Não há uma forma de chamar a mira telescopia do crossbow." | verify | interaction | `XR_ProcessProximityScope` exists; confirm the crossbow reaches it. |
| 12 | "O RPG está invisivel" | open | viewmodel | Check the RPG native route and its draw path. |

## Report of 2026-10-22

| # | Verbatim report | State | Area | Next action |
|---|---|---|---|---|
| 13 | "se mudo a posição da cabeça, olho para os lados, o movimentos dos analogicos de movimentação dão uma invertida." | open | locomotion | Likely the head-relative versus world-relative move vector; add a head-turn assertion. |
| 14 | "A ferramenta de ajuste de posição em runtime precisa ser revista, um dos eixos de rotação estava alterando a referencia das luvas sempre presentes." | open | debug tool | Audit the runtime offset cvars so they cannot move the persistent hand reference. |
| 15 | "Animação do crowbar precisa ser revista ... faz um movimento de dano que não vai funcionar em vr." | open | animation | Melee animation ownership; see the hard rules in [`AGENTS.md`](../../../AGENTS.md). |
| 16 | "Pesquisar se tem como ter o controle no blender como referencia." | tooling | asset pipeline | Blender review harness already exists; add a controller reference object. |
| 17 | "As armas não tem clip, quando proxima das paredes a ilusão de immersão quebra, talvez ... transformar elas em fisicas." | open | physics | Weapon-vs-wall is the first Box3D query use case; see [`HAND_IK_AND_PHYSICS.md`](HAND_IK_AND_PHYSICS.md). |
| 18 | "O crossbow agora tem elementos que não aparecem." | verify | viewmodel | Check bodygroups and `vr_hide_arms`; a replacement model may drop parts. |
| 19 | "Ainda não tem uma forma de mirar com o crossbow." | verify | interaction | Same path as item 11. |
| 20 | "A duplicidade de função para o tiro secundario e falta um botão de recarregar." | open | input | Map secondary fire and reload explicitly; document the binding. |
| 21 | "Ainda não é possivel subir as escadas." | open | locomotion | Same as item 7. |
| 22 | "Botão de pulo no mesmo lugar do analogico de movimento, não é ergonomico." | open | input | Controller ergonomics; keep the existing accessibility fallback. |
| 23 | "Verificar forma de deixar escuro a parte de dentro das luvas." | open | assets | Material/backface pass on `v_hand.mdl`; no vertex reshaping. |

## Prioritisation

1. Items 1 and 2 are the firing-line blocker and already have a code change
   waiting for headset validation. Do not open parallel pose work first.
2. Items 5, 6, 10, 12 and 18 are visibility/pose regressions that a single
   `A4`-style capture sweep can confirm or dismiss.
3. Items 7, 8, 13 and 21 are locomotion; they share a test harness and should
   be triaged together.
4. Item 17 is the natural first Box3D query target because it needs no
   gameplay change: it is a wall test for an existing weapon pose.

## Related

- [`../STATUS.md`](../STATUS.md) - current blockers and gate state.
- [`BOX3D.md`](BOX3D.md) - physics dependency and staged integration.
- [`HAND_IK_AND_PHYSICS.md`](HAND_IK_AND_PHYSICS.md) - hand IK and spatial
  reload plan.
