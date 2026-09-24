<div align="center">

# navori-owl 🦉

**Benchmark reproducible para agentes y harnesses de código.**

[![status](https://img.shields.io/badge/status-dise%C3%B1o-f59e0b)](./VISION.md)
[![license](https://img.shields.io/badge/license-MIT-8b5cf6)](./LICENSE)

</div>

`navori-owl` pone a competir configuraciones de agentes de código en igualdad de condiciones:
Claude Code vanilla, Claude Code con un harness (skills, subagentes, hooks, memoria, metodologías SDD/TDD),
otros CLIs o tu propio agente. Todos reciben **las mismas tareas**, cada corrida ocurre en un **sandbox
limpio** y un **grader oculto** califica **varias dimensiones**. El resultado responde a:

> **¿Qué harness me conviene, en qué tipo de tarea y a qué costo?**

---

## El problema

Hay decenas de harnesses para agentes de código y casi ninguno publica evidencia comparable. La
investigación dice que el harness pesa tanto como el modelo: con el **mismo modelo**, cambiar de harness
mueve el éxito ~24 pp ([Harness-Bench](https://arxiv.org/abs/2605.27922)) y los tokens hasta **40x**
([The Scaffold Effect](https://arxiv.org/abs/2607.22585)). Elegir uno "porque se siente mejor" no alcanza, y
comparar a mano tiene trampas: config del usuario que contamina el baseline, pocas corridas, tests que el
agente puede leer, variantes que "ganan" solo porque gastaron más.

## Cómo funciona

```
 variants/*.yaml ─┐
 tasks/*        ──┼─▶ navori-owl ─▶ Harbor (sandbox por trial) ─▶ grader oculto ─▶ reward.json
 RULES.md       ──┘        │                                                        │
                           └──── gate de contaminación · métricas · estadística ◀───┘
                                              │
                                              ▼
                      reporte: tabla por tarea · Pareto costo/éxito · diferencias pareadas
```

- **Variante** = agente + harness + versión fijada + modelo, descrita en un manifiesto. Nada se hereda del
  entorno: si no está en el manifiesto, no se carga. Un gate lo verifica en cada corrida.
- **Tareas** en formato [Harbor](https://github.com/harbor-framework/harbor)/Terminal-Bench: instrucción,
  entorno, tests ocultos y solución de referencia.
- **Criterios**:
  - **Resultado:** éxito y consistencia (pass^k).
  - **Eficiencia:** USD, tokens, tiempo y turnos.
  - **Comportamiento:** alcance, convenciones, seguridad, acciones destructivas, reward hacking, saber cuándo preguntar o abstenerse.
  - **Proceso:** solo explicativo.
- **Estadística honesta**:
  - Pre-registro.
  - Comparación pareada por tarea.
  - Corrección por comparaciones múltiples.
  - Errores de infraestructura separados de las derrotas.

## Primeras variantes

El catálogo es abierto: cualquier agente o harness entra si se puede describir con un manifiesto. La primera
ronda apunta a:

| Variante | Qué es |
|---|---|
| Claude Code vanilla | Baseline, en modo por defecto y en modo `--bare` |
| [navori-harness](https://github.com/UlisesCm/navori-harness) | Harness multi-agente + SDD |
| [gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) | Harness de Gentleman Programming (SDD, Engram, skills) |
| [superpowers](https://github.com/obra/superpowers) | Skills de brainstorming, TDD, debugging sistemático y review |
| [ponytail](https://github.com/DietrichGebert/ponytail) | Skill de minimalismo (YAGNI) |
| Placebo | Un cambio de estilo barato, para separar el efecto real del efecto de estilo |

Más adelante: otros CLIs (Codex, OpenCode, Gemini CLI) y agentes propios.

## Estado

🚧 **Diseño.** Hoy el repo contiene la visión y la investigación. Siguiente paso: **F0**, un spike sobre Harbor
que valide el gate de contaminación, la telemetría por variante y que los tests queden ocultos al agente.

| Fase | Qué |
|---|---|
| F0 | Spike Harbor: smoke + vanilla + una variante plugin |
| F1 | Absorber el prototipo `navori-evals` |
| F2 | Suite v1: repo paciente + 12–15 tareas + oráculos |
| F3 | Ronda 1 pre-registrada |
| F4 | Reportes / dashboard |
| F5 | Agentes no-Claude y agentes propios |

## Documentación

- 📐 [**VISION.md**](./VISION.md): qué es, principios, arquitectura, criterios, estadística y las decisiones
  recomendadas con su evidencia.
- 🔬 [`docs/research/`](./docs/research/): investigación con fuentes.
  - [01 Benchmarks públicos](./docs/research/01-benchmarks-publicos.md)
  - [02 Metodología](./docs/research/02-metodologia.md)
  - [03 Evals de comportamiento](./docs/research/03-evals-de-comportamiento.md)
  - [04 Catálogo de harnesses](./docs/research/04-catalogo-harnesses.md)
  - [05 Herramientas y proyectos paralelos](./docs/research/05-herramientas-y-proyectos-paralelos.md)
  - [06 Antecedentes](./docs/research/06-antecedentes-navori-evals.md)

## Inspiración

[Terminal-Bench 2.0 / Harbor](https://www.tbench.ai) ·
[superpowers-evals (Quorum)](https://github.com/prime-radiant-inc/superpowers-evals) ·
[ponytail benchmarks](https://github.com/DietrichGebert/ponytail/tree/main/benchmarks) ·
[LangChain skills-benchmarks](https://github.com/langchain-ai/skills-benchmarks) ·
[Harness-Bench](https://github.com/Qihoo360/harness-bench) ·
[Demystifying evals for AI agents (Anthropic)](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

## Licencia

[MIT](./LICENSE) © 2026 Ulises Ciprés
