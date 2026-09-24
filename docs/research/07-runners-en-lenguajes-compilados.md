# 07 — ¿Hay un equivalente a Harbor en Rust o Go?

> Fecha de corte: 2026-09-24. Búsqueda en GitHub (`gh search repos`, `gh repo view`) y web. Estrellas y
> `pushedAt` verificados con `gh` el mismo día salvo donde se marca **UNVERIFIED**. No se repite lo ya cubierto
> en `05-herramientas-y-proyectos-paralelos.md` (Harbor, Inspect AI, promptfoo, `claude plugin eval`).

## Pregunta y criterio de búsqueda

¿Existe, en Rust/Go/otro lenguaje compilado, un runner que cubra las mismas cinco piezas que Harbor:
**formato de tarea + verificadores/tests ocultos + ejecución en sandbox/contenedor + adaptadores para
múltiples CLIs de agentes + costo/tokens/trayectoria por trial**?

Búsqueda con `gh search repos`, `WebSearch` y lectura de READMEs (`WebFetch`) sobre variaciones de:
"Rust/Go coding agent benchmark harness sandbox hidden tests", "task.toml hidden tests rust github",
"agent evaluation harness multi-agent adapters docker sandbox 2026", más los nombres que fueron
apareciendo (goagentbench, agentbox, oharness, majiayu000/harness). Cobertura de la negativa: esa
combinación de queries sobre GitHub y la web pública, no un catálogo exhaustivo de todo GitHub.

## Veredicto corto

**No hay nada en Rust o Go que cubra las cinco piezas con una madurez comparable a Harbor** (5,555★,
40+ agentes, 25+ backends de sandbox — cifras de `05`). El candidato más completo en features
(`sample-agent-cost-bench`) está en **Python**, no en un lenguaje compilado. Lo que sí existe en Rust/Go
son piezas sueltas — un runner Go muy acotado a un solo lenguaje, una librería de sandbox de proceso, un
orquestador de flotas sin verificador, y un crate Rust de plomería publicado el mismo día de este corte.
Ninguna reemplaza a Harbor; alguna podría ser útil como pieza adyacente. Detalle abajo.

## 1. Candidatos evaluados como "¿reemplaza a Harbor?"

| Proyecto | Lenguaje | ★ / último push | Formato de tarea | Tests ocultos | Sandbox | Adaptadores multi-agente | Costo/tokens | Stats/reporte |
|---|---|---|---|---|---|---|---|---|
| **Harbor** (referencia, ver `05`) | Python | 5,555★ / 2026-09-24 | `task.toml` + `instruction.md` + `tests/` | Sí (no documentado explícito, UNVERIFIED en `05`) | Docker/Podman/Daytona/E2B/Modal… (25+) | 40+ CLIs | Sí, por trial | `harbor view`, sin comparación N-brazos nativa |
| **codalotl/goagentbench** https://github.com/codalotl/goagentbench | Go | 11★ / 2026-03-14 | `scenario.yml` sobre un repo Go real + commit fijo | Sí por defecto ("the agent does not see failing test cases"; excepción con `sees-failing-tests: true`) | Docker (`docker_dev.sh`) | Solo 3: codex, codalotl, grok — **sin Claude Code** | Parcial: algunos agentes exigen entrada manual de costo | Success rate, costo promedio, tiempo; sin estadística pareada |
| **aws-samples/sample-agent-cost-bench** https://github.com/aws-samples/sample-agent-cost-bench | **Python** (no compilado — se incluye solo por ser el más completo en features) | 82★ / 2026-09-18 | `task.yaml` (prompt + esfuerzo) + `verify/` | Sí: "the model never sees them" | Workspace desechable por corrida; Docker para verificación; clona repos reales para brownfield | 9: Kiro, Claude Code, Copilot, Cursor, Codex, Antigravity, OpenCode, Devin, pi | Sí, USD + unidades nativas (créditos/tokens) por CLI | HTML + JSON, pass rate + costo + latencia, blend de rúbrica LLM y tests |
| **oharness_eval / oharness_bench_swe** (crate Rust de `aishfenton`) https://docs.rs/oharness-eval/latest/oharness_eval/ · https://docs.rs/oharness-bench-swe/latest/oharness_bench_swe/ | Rust | Sin repo GitHub público encontrado (**UNVERIFIED** madurez); crate publicado 2026-09-24 (el mismo día de este corte) | Carga SWE-bench Lite como `Benchmark` | Implícito (aplica el patch de test y compara `FAIL_TO_PASS`/`PASS_TO_PASS`) | No implementado aún — depende de infraestructura externa | No — la propia doc lo llama "prerequisite plumbing"; el hito declarado (M2) es apenas "≥5 tareas SWE-bench-lite pasando end-to-end" | No | No |

**Lectura de la tabla:** `goagentbench` es la única pieza Go que se parece a un Harbor en miniatura, pero
está acotada a tareas Go, tiene 3 adaptadores (ninguno es Claude Code) y lleva sin push desde marzo 2026 —
un mantenedor, sin señales de comunidad. `sample-agent-cost-bench` es hoy el proyecto que más se parece a
lo que pide la pregunta original (task format + tests ocultos + sandbox + 9 adaptadores + costo/tokens +
reporte), pero está en Python — no responde "Rust o Go". El crate Rust `oharness` es de plomería, un solo
dev, publicado el mismo día de este corte: demasiado temprano para evaluarlo como candidato, se incluye
solo porque apareció en la búsqueda y para dejar constancia de que se revisó.

No encontré, ni en GitHub ni en la web pública consultada el 2026-09-24, ningún runner en Rust o Go que
declare explícitamente las cinco piezas (formato de tarea, tests ocultos, sandbox, multi-agente, costo)
con una madurez de comunidad (issues, contribuidores, releases) equivalente a Harbor. Esto es una negativa
acotada a las búsquedas hechas arriba, no una afirmación sobre todo GitHub.

## 2. Piezas adyacentes en Rust/Go (útiles aunque no reemplacen a Harbor)

| Proyecto | Lenguaje | ★ / último push | Qué es | Por qué podría servirle a owl | Por qué NO es un reemplazo de Harbor |
|---|---|---|---|---|---|
| **firecracker-microvm/firecracker** https://github.com/firecracker-microvm/firecracker | Rust | 36,920★ / 2026-09-24 | microVM (AWS), aislamiento de kernel dedicado, boot <125ms | Ya es la base de facto de varios backends de sandbox que Harbor soporta (Daytona, Modal, Fly-style runners usan Firecracker o algo similar por debajo) | No expone tareas, verificadores ni adaptadores de agente — es infraestructura de virtualización pura |
| **google/gvisor** (runsc) https://github.com/google/gvisor | Go | 19,412★ / 2026-09-24 | Application kernel en user-space, runtime OCI (`runsc`) | Si el gate de seguridad de owl (ver `05` §4) necesitara aislamiento más fuerte que Docker plano para un agente con `--dangerously-skip-permissions`, `runsc` es un `runtimeClass` intercambiable sin tocar el resto de la imagen | Es un runtime de contenedor, no un runner de evals |
| **containers/youki** https://github.com/youki-dev/youki | Rust | 7,613★ / 2026-09-24 | Runtime OCI alternativo a `runc`, escrito en Rust | Reduce overhead de arranque por trial si owl termina con miles de contenedores efímeros; drop-in para Docker/Podman | Igual que gVisor: capa de runtime, no de evaluación |
| **zhangyunhao116/agentbox** https://github.com/zhangyunhao116/agentbox | Go | 7★ / 2026-04-09 | Librería (no runner) de aislamiento a nivel de proceso — namespaces+Landlock en Linux, Seatbelt en macOS, sin Docker, sin CGo | Aislamiento ligero para trials locales/CI sin pagar el costo de un contenedor completo | Proyecto muy joven (7★, un contribuidor visible), no resuelve tests ocultos ni adaptadores; es una librería, no un harness |
| **majiayu000/harness** https://github.com/majiayu000/harness | Rust | 74★ / 2026-09-21 | "Control plane" para correr flotas de Claude Code/Codex en paralelo: política tipo Starlark, revisión cruzada entre agentes, OpenTelemetry, requiere Postgres+Docker | Ideas de diseño reusables para la capa de orquestación de variantes de owl (policy engine, OTel) | No tiene concepto de tarea con verificador oculto ni de "reward" — es gobernanza de agentes trabajando en un repo real, no un benchmark |
| **daytonaio/daytona** https://github.com/daytonaio/daytona | Mixto (CLI Go, resto no puramente Go — `primaryLanguage` no resuelve a uno solo, **UNVERIFIED** el desglose exacto) | 71,716★ / último push 2026-07-24 (**nota**: sin push reciente, revisar si el desarrollo activo migró a otro repo antes de asumir mantenimiento vivo) | Infra de sandboxes elásticos, ya es uno de los 25+ backends que soporta Harbor (ver `05`) | Nada nuevo que agregar: ya está dentro del ecosistema Harbor | No es un runner independiente, es un backend que Harbor ya sabe usar |

## 3. Lo que NO se encontró

- Ningún fork o clon directo de Harbor/Terminal-Bench reescrito en Rust o Go.
- Ningún proyecto Rust con adaptadores para más de un CLI de agente (Claude Code, Codex, Gemini CLI, etc.)
  y verificador oculto simultáneamente — el único candidato Rust (`oharness`) es de un solo dev, del mismo
  día del corte, y explícitamente pre-M2.
- Ningún procesador de trayectorias (ATIF o similar) en Rust/Go equivalente al visor `harbor view` o a
  ccusage (mencionado en `05`, que además no es Rust/Go).

## 4. Veredicto

**Quedarse en Harbor.** Ninguna alternativa en Rust/Go cubre las cinco piezas con madurez comparable; el
único proyecto que sí las cubre todas (`sample-agent-cost-bench`) está en Python y no responde a "lenguaje
compilado". Cambiar de runner hoy cambiaría certidumbre (40+ agentes, 25+ backends, visor, comunidad) por
una apuesta sin ecosistema.

**Sí vale la pena considerar, como piezas puntuales dentro de Harbor, no como reemplazo:**
- **`runsc` (gVisor) o `youki`** para el backend de sandbox, **solo si** el spike F0 de owl (ver `05` §4,
  punto 5 "gate automático") encuentra que Docker plano no aísla lo suficiente para correr agentes con
  `--dangerously-skip-permissions` sin supervisión, o si el overhead de arranque por trial se vuelve
  significativo a la escala que owl necesite. Ambos son swaps de runtime OCI compatibles con los backends
  Docker/Podman que Harbor ya soporta — no requieren cambiar de runner.
- **`majiayu000/harness`** como referencia de diseño (policy engine, OTel) si owl construye su propia capa
  de orquestación de variantes sobre Harbor — no como dependencia.

No hay razón para invertir tiempo evaluando `goagentbench` (acotado a Go, sin Claude Code, dormido desde
marzo) ni `oharness` (plomería de un día) como candidatos serios hoy.
