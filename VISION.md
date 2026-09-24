# navori-owl — visión

> **Una herramienta para medir agentes y harnesses de código.** Pone a cualquier configuración de agente
> (Claude Code vanilla, Claude Code + un harness, otros CLIs o un agente propio) frente a las mismas tareas,
> en sandboxes aislados y con criterios de evaluación explícitos. Luego dice, con estadística honesta, **quién
> gana, en qué tipo de tarea y a qué costo**.
>
> Estado: diseño (2026-09-23). Toda recomendación de este documento se apoya en documentación oficial o en
> proyectos parecidos que ya existen. El detalle y las fuentes están en [`docs/research/`](docs/research/).

---

## 0. En una página

- **El problema.** Hay decenas de harnesses para agentes de código (skills, subagentes, hooks, memoria,
  metodologías como SDD o TDD) y casi ninguno publica evidencia comparable. Con el mismo modelo, el harness puede
  mover el éxito ~24 pp y el costo hasta 40x ([02 §1](docs/research/02-metodologia.md)). Elegir uno "a ojo"
  no alcanza.
- **La respuesta.** Un laboratorio que corre N **variantes** sobre la misma **suite de tareas**. Cada
  **trial** corre en un sandbox limpio, un **grader oculto** califica varias dimensiones (resultado, eficiencia,
  comportamiento) y un **reporte** hace comparaciones pareadas por tarea.
- **Primer caso de uso** (no el único): comparar navori-harness con Claude Code vanilla, gentle-ai
  (Gentleman Programming), superpowers y ponytail. El catálogo de variantes es abierto
  ([04](docs/research/04-catalogo-harnesses.md)).
- **Base técnica recomendada:** construir sobre **[Harbor](https://github.com/harbor-framework/harbor)**, el runner
  de Terminal-Bench 2.0, y agregar lo que le falta: variantes declarativas, gate de contaminación, estadística
  para N variantes y reporte comparativo ([05 §2](docs/research/05-herramientas-y-proyectos-paralelos.md)).

## 1. Glosario

| Término | Significado |
|---|---|
| **Agente** | El programa que recibe una tarea y trabaja solo: Claude Code, Codex CLI, OpenCode o uno propio |
| **Harness** | Todo lo que rodea al modelo y cambia cómo trabaja: prompts, skills, subagentes, hooks, memoria, MCPs, metodología. "Claude Code + superpowers" es un harness |
| **Variante** | Una configuración concreta y reproducible que se evalúa: agente + harness + **versión fijada** + modelo. Se describe en un manifiesto |
| **Baseline** | La variante de referencia, normalmente el agente sin harness (vanilla) |
| **Tarea** | Un problema con instrucción, repo de partida, tests ocultos y una solución de referencia |
| **Trial** | Una ejecución de una variante sobre una tarea. Se repite varias veces porque los agentes no son deterministas |
| **Ronda** | Un experimento completo: tareas × variantes × trials, con reglas fijadas *antes* de correr (pre-registro) |
| **Grader** | El programa que califica el trial. Es "oculto": el agente nunca lo ve |
| **F2P / P2P** | *Fail-to-pass*: tests que deben pasar a verde (la tarea quedó resuelta). *Pass-to-pass*: tests que ya pasaban y deben seguir pasando (no se rompió nada) |
| **Oráculo** | Solución de referencia que demuestra que la tarea tiene solución y que los tests son justos |
| **pass^k** | Probabilidad de que los k intentos salgan bien. Mide **consistencia**; importa más que pass@k (al menos 1 de k) para uso diario |
| **Pareado** | Comparar variantes *tarea por tarea*, no promedios globales. Es la forma correcta cuando hay pocas tareas |
| **Frontera de Pareto** | Las variantes a las que ninguna otra supera a la vez en éxito y en costo |
| **Contaminación** | Que una variante cargue config que no le corresponde, p. ej. el baseline heredando tu `~/.claude` |

## 2. Qué es y qué no es

**Es:**
- Un laboratorio **reproducible**: con el mismo manifiesto, la misma tarea y la misma versión, el experimento se puede repetir.
- **Agnóstico**: cualquier agente o harness entra si se puede describir con un manifiesto.
- **Honesto**: pre-registro, estadística pareada, errores de infraestructura separados de las derrotas.

**No es:**
- Un leaderboard de modelos: el modelo queda fijo por ronda.
- Una herramienta para promocionar un harness en particular, incluido navori. Si un harness pierde, se reporta.
- Un sustituto de leer transcripts: los números dicen *qué* pasó y los transcripts *por qué*.

## 3. Principios (y de dónde salen)

1. **Se mide el par (agente+harness, modelo), nunca "el modelo" solo.** Harness-Bench, Anthropic ([02 §1](docs/research/02-metodologia.md)).
2. **El resultado decide y el proceso explica.** Se califica el estado final; el camino se usa para diagnosticar. Anthropic, Terminal-Bench.
3. **Grader determinista y oculto primero.** El juez LLM se usa solo donde hace falta; siempre ciego a la variante y calibrado con humanos ([02 §6](docs/research/02-metodologia.md)).
4. **El costo es co-métrica de primera clase.** Ganar gastando 3x no es lo mismo que ganar. AI Agents That Matter, HAL.
5. **Pre-registro.** Métrica primaria, tareas, n y reglas quedan escritas antes de ver resultados.
6. **La unidad de análisis es la tarea.** Comparaciones pareadas, nada de CLT con n chico ([02 §3](docs/research/02-metodologia.md)).
7. **El harness no se evalúa sobre sí mismo.** Las tareas no se diseñan a la medida de un harness, y se mantiene un **holdout** (Kapoor et al.).
8. **Aislamiento verificable, no supuesto.** Cada trial prueba qué cargó (gate de contaminación).
9. **Leer los transcripts de las fallas** antes de declarar un veredicto.

## 4. Conceptos y modelo de datos

```
Ronda (pre-registrada: RULES.md)
 ├── Variantes  [vanilla, navori, gentle-ai, superpowers, ponytail, ...]  ← manifiestos
 ├── Tareas     [T01 ... T15] (+ holdout)                                  ← formato Harbor
 └── Trials     variante × tarea × k (k=5), intercalados
        └── Resultado: reward.json multidimensional + métricas + transcript + diff + init
```

## 5. Arquitectura

```
                ┌──────────────────────── navori-owl ────────────────────────┐
 variants/*.yaml│  1. Materializa la variante (install/init, plugins, MCP)   │
 tasks/*        │  2. Planifica trials intercalados (A,B,C,A,C,B,…)          │
 RULES.md  ───▶ │  3. Lanza Harbor ──────────────────────────────────────────┼──▶ Harbor
                │                                                            │    ├ sandbox (docker/daytona/…)
                │  4. Gate de contaminación (system/init + ¿llegó al modelo?)│◀── ├ agente (claude-code/codex/custom)
                │  5. Recolecta: reward.json, stream-json, ATIF, diff        │    └ tests ocultos → reward.json
                │  6. Análisis: pareado por tarea, Holm, bootstrap, Pareto   │
                │  7. Reporte: heatmap, Pareto, matriz pareada, costos       │
                └────────────────────────────────────────────────────────────┘
```

**Qué pone Harbor** (ya existe, [05 §2](docs/research/05-herramientas-y-proyectos-paralelos.md)):
- Sandbox por trial.
- Formato de tarea (`instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/`).
- Verificador con recompensa multidimensional.
- 40+ agentes integrados (claude-code, codex, opencode, gemini-cli, aider…).
- `CLAUDE_CONFIG_DIR` limpio por trial.
- Métricas de tokens y costo.
- Trayectorias ATIF.

**Qué pone owl:**
1. **Manifiesto de variante** (§6), que se traduce a una subclase del adaptador de Harbor. Para Claude Code es `ClaudeCodeHarness(ClaudeCode)`, que añade `--plugin-dir`, un comando de init por variante, `--mcp-config` explícito y `--bare` opcional, porque el adaptador actual no soporta plugins.
2. **Gate de contaminación.** Se lee `system/init` (`plugins`, `plugin_errors`, `mcp_servers`, `mcp_server_errors`) y se compara contra lo que declara el manifiesto. Si hubo algo de más o de menos, el trial se invalida. También se exige al menos una llamada exitosa al modelo: en Qihoo harness-bench #10, un HOME sin credenciales **puntuaba 0.0 en silencio**.
3. **Telemetría por variante:** cada job de Harbor corre una sola variante, y Harbor ya extrae costo y tokens por trial (evento `result` de stream-json + trayectoria ATIF por paso). Eso basta para atribuir el costo por variante. OTel (`OTEL_RESOURCE_ATTRIBUTES=arm=<id>,task=<id>,trial=<n>`) queda para F4, solo si hace falta desglosar por skill o herramienta: OTel reporta los plugins de terceros como `"third-party"`.
4. **Planificador intercalado:** las variantes se alternan para que la caché de prompts y el drift de la API no se confundan con un efecto (intent-as-a-service/harness-bench).
5. **Análisis y reporte** (§9, §11).

## 6. Manifiesto de variante (propuesta)

Un archivo por variante. Todo lo que la variante agrega queda declarado ahí; nada se hereda del entorno.

```yaml
# variants/superpowers.yaml
id: superpowers
agent: claude-code            # adaptador de Harbor (claude-code | codex | opencode | custom:modulo:Clase)
agent_version: "2.1.281"      # versión fijada del CLI
model: claude-sonnet-5        # igual para toda la ronda
harness:
  source: { git: "https://github.com/obra/superpowers", sha: "<sha>" }
  plugins: ["./superpowers"]  # → --plugin-dir
  init: null                  # comando de instalación, si aplica
  mcp: []                     # → --mcp-config explícito
  env: { SUPERPOWERS_DISABLE_TELEMETRY: "1" }
expect:                       # para el gate de contaminación
  plugins: ["superpowers"]
  mcp_servers: []
```

Otros ejemplos, abreviados:
- `vanilla-default`: `harness: {}`, `expect: {plugins: [], mcp_servers: []}`.
- `navori`: `init: "npx navori@<ver> init --yes --recommended --cwd ."`, `mcp: [engram]`.
- `gentle-ai`: `init: "gentle-ai install --agent claude-code --preset full-gentleman --scope workspace"` con el binario fijado por `go install …@vX.Y.Z`.
- Agente propio: `agent: custom:mi_agente:MiAgente` (una clase `BaseAgent` o `BaseInstalledAgent` de Harbor).

`harness.runtime_state` (lista de patrones estilo `.gitignore`, opcional): estado que el propio
harness de la variante escribe en `/app` **durante** la corrida (stamps de hooks, directorios por
sesión, ...) — nunca trabajo del agente. `ClaudeCodeHarness.run` los agrega a
`/app/.git/info/exclude` justo después del commit "variant installed", así
`git ls-files --others --exclude-standard` (de donde `tasks/*/tests/test.sh` mide el scope) deja
de verlos como ediciones del agente, sin tocar ningún archivo versionado. Ejemplo real,
`variants/navori.yaml`: `.claude/.managed-drift-stamp`, `.claude/.routing-watch/`, y el resto de
`EPHEMERAL_HARNESS_PATHS` de navori-harness — lección de un trial real
(`jobs/20260924-162201__00-smoke__navori__r1`) donde esos archivos bajaron el `scope` a 0 sin que
el agente hubiera tocado nada fuera de lo pedido.

**Regla:** `runtime_state` es solo para archivos que el harness escribe **por sí mismo durante la
corrida** — nunca config que cambia el comportamiento del agente (permisos, modelo, etc.), aunque
esa config también aparezca en la lista de "nunca versionado" del harness por otro motivo
(higiene de backup/`.gitignore`, no seguridad de scope). Excluir un archivo de config del scope le
dejaría a un agente editarlo — auto-otorgarse permisos, cambiar el modelo — sin que esa edición
cuente como fuera de scope, lo que anula el propósito de medir scope. Por eso
`.claude/settings.local.json` (que sí está en `EPHEMERAL_HARNESS_PATHS` de navori) se dejó
deliberadamente fuera de `variants/navori.yaml#harness.runtime_state`: los hooks de navori nunca
lo escriben en runtime (es config de usuario editada a mano, no estado operativo generado por el
harness), así que si cambia durante un trial fue el agente, y debe contar como fuera de scope como
cualquier otra edición.

Las instalaciones exactas de cada candidato están en [04 §2](docs/research/04-catalogo-harnesses.md).

## 7. Aislamiento

Receta, respaldada por la doc oficial de Claude Code y por lo que ya hacen Harbor y Quorum ([05 §4](docs/research/05-herramientas-y-proyectos-paralelos.md)):

1. **Contenedor efímero**, usuario no-root (Claude Code rechaza `--dangerously-skip-permissions` como root), versión de Claude Code fijada y `DISABLE_AUTOUPDATER=1`.
2. **`HOME` y `CLAUDE_CONFIG_DIR` vacíos por trial.** Así se evita la contaminación desde `~/.claude`, `~/.engram`, `~/.navori` y los plugins del usuario.
3. **Fixture idéntico para todas las variantes:** commit único, sin remotes, tags ni reflog. Así se cierra la fuga por historial de git (SWE-bench #465).
4. **Tests y oráculo fuera del sandbox** durante la corrida; se montan solo al verificar.
5. **Sin red externa,** salvo la API del modelo y lo que declare el manifiesto.
6. **Auditar la imagen:** que no haya un `/etc/claude-code/managed-settings.json`, porque tiene la precedencia más alta.
7. **No confiar en `--setting-sources`** para aislar (issue abierto #87590).
8. **Memorias persistentes** (engram, claude-mem): se resetean por trial. Si se quiere medir la memoria, se hace con tareas multi-sesión diseñadas para eso.
9. **Mismo modo de permisos y mismos límites** (`max_turns`, `max_budget_usd`, timeout) para todas las variantes. OverEager-Gen mostró que el modo de permisos domina el resultado.

## 8. Criterios de evaluación

Cada trial produce un `reward.json` con varias dimensiones. **Solo una es primaria** (la declara el pre-registro); las demás son secundarias o explicativas.

| Nivel | Dimensión | Cómo se mide | Grader | Precedente |
|---|---|---|---|---|
| **Resultado** (decide) | Éxito | F2P ocultos + P2P (suite existente, typecheck, lint) | Determinista | SWE-bench, Terminal-Bench |
| | Consistencia | pass^k por tarea | Derivado | τ-bench, Anthropic |
| **Eficiencia** | Costo | USD, tokens in/out/cache (stream-json + trayectoria ATIF) | Métrica | HAL, Scaffold Effect |
| | Tiempo y esfuerzo | Wall-clock, turnos, tool calls, subagentes | Métrica | Harness-Bench |
| | Costo por éxito | USD / tarea resuelta | Derivado | AI Agents That Matter |
| **Comportamiento** (donde un harness suele diferenciarse) | Alcance | `git diff --name-only` ⊆ allowlist; archivos señuelo intactos | Determinista | OverEager-Gen |
| | Convenciones | Marcadores verificables (grep/AST/lint) | Determinista | McMillan 2026 |
| | Seguridad | Exploits HTTP + semgrep | Determinista | BaxBench, ponytail |
| | No destruir | Estado final + shims en PATH | Determinista | SABER |
| | No hacer trampa | Hash de tests y configs; tareas imposibles | Determinista | ImpossibleBench |
| | Abstenerse / preguntar | Diff vacío + mensaje final | Determinista + juez | ETH SRI, Ambig-SWE |
| | Resistir inyección | Canary | Determinista | IssueTrojanBench |
| | Calidad de review | Recall de defectos sembrados | Juez por hallazgo | SWR-Bench |
| | Calidad del diff | Pairwise ciego | Juez (secundario) | FullStack-Bench |
| **Proceso** (explica) | ¿Corrió tests? ¿Loops? ¿Activó sus skills? | Trayectoria (ATIF / stream-json) | Determinista | TraceProbe, OpenAI |

Detalle y catálogo de tareas de comportamiento (B1–B13): [03](docs/research/03-evals-de-comportamiento.md).

## 9. Estadística y veredicto

- **Unidad = tarea.** Para cada par (variante, baseline): `d_i = éxito_i(variante) − éxito_i(baseline)`.
- **Test:** sign-flip de permutación sobre los `d_i` (exacto con n chico). IC por **bootstrap jerárquico** (tareas → trials). **Holm** para corregir entre N variantes.
- **Co-métricas:** `log(costo_variante / costo_baseline)` pareado por tarea. Estas sí detectan diferencias con pocas tareas.
- **Equivalencia:** si no hay diferencia significativa, se reporta el intervalo o se usa **TOST** con un margen pre-registrado. Nunca se dice "no hay efecto".
- **Potencia** (simulación propia, [`power.py`](docs/research/power.py)): con 12–15 tareas × 5 trials se detecta ~+27 pp con ~84–93%, y **+10 pp es indetectable**. Consecuencia: el éxito binario actúa como *guardrail* y el costo y el comportamiento cargan la decisión.
- **Veredicto tipo:** "la variante X no empeora el éxito (IC inferior > −10 pp), reduce el costo 30% [IC] y viola alcance en 2/75 trials contra 9/75 del baseline".
- **Bradley-Terry** solo para calidad juzgada por pares, no para el éxito ([05 §6](docs/research/05-herramientas-y-proyectos-paralelos.md)).

## 10. Suite de tareas

**Mezcla** (taxonomía de [01 §3](docs/research/01-benchmarks-publicos.md)):
- Bugfix: sembrados y "accidentales".
- Feature cross-package.
- Refactor con invariante.
- Seguridad.
- Tooling.
- Test/repro.
- Comportamiento B1–B13.

**Tareas que ponen a prueba lo que promete cada harness** ([04 §4](docs/research/04-catalogo-harnesses.md)):

| Tarea | Pone a prueba a |
|---|---|
| Trampas de sobre-ingeniería | ponytail y minimalistas |
| Bug con causa raíz oculta y "test primero" | superpowers y los de TDD |
| Multi-sesión que depende de una decisión previa | harnesses con memoria |
| Feature grande con spec | SDD |
| Trivial de una línea (costo fijo del proceso) | todos |

**Repo "paciente":** monorepo privado y sintético, con convenciones marcador en su `CLAUDE.md` base (igual para todas las variantes) y canary string. Fuentes de partida: RealWorld/Conduit y `harness-test/IncidentHub` ([06 §6](docs/research/06-antecedentes-navori-evals.md)).

**Checklist por tarea** (Terminal-Bench):
- *Specificity*: los tests pasan si y solo si el resultado es aceptable.
- *Solvability*: el oráculo pasa y la base falla.
- *Integrity*: una corrida adversarial "tramposa" no pasa.
- El oráculo corre 5 veces sin flaky.
- Dificultad calibrada con un piloto: el baseline entre 30% y 70%.

## 11. Reportes

1. **Tabla por tarea** (siempre): éxitos por variante, costo y alertas de comportamiento.
2. **Heatmap tarea × variante.**
3. **Frontera de Pareto** costo vs éxito con IC en ambos ejes.
4. **Matriz de diferencias pareadas** con p ajustado por Holm.
5. **Desglose de costo** main vs subagentes (`query_source`).
6. **Errores de infraestructura y trials invalidados** por el gate, aparte.
7. Radar solo como resumen visual.

## 12. Decisiones recomendadas (fichas)

Cada ficha incluye opciones, la recomendada, la evidencia y lo que se pierde. Se pueden revisar antes de la ronda 1.

| # | Decisión | Opciones | **Recomendada** | Evidencia | Qué se pierde |
|---|---|---|---|---|---|
| D1 | Base del runner | Harbor · Inspect · runner propio | **Harbor** | Runner oficial de Terminal-Bench 2.0; 40+ agentes; `CLAUDE_CONFIG_DIR` limpio ya implementado. Inspect sobrescribe settings y no acepta plugins; un runner propio reimplementa todo ([05 §2–3](docs/research/05-herramientas-y-proyectos-paralelos.md)) | Dependencia de Python/Harbor; hay que subclasear el adaptador |
| D2 | Baseline | vanilla-default · vanilla-bare · ambos | **Ambos; `vanilla-default` es el principal** | `--bare` es lo que Anthropic recomienda para scripts, pero omite hasta el `CLAUDE.md` del proyecto y exige API key. `default` es el producto tal como se usa | Una variante más por ronda (+costo) |
| D3 | Cómo cargar cada harness | Instalar en `~/.claude` · `--plugin-dir` + init en el workspace | **`--plugin-dir` para plugins; init en el workspace para los demás; siempre con HOME efímero** | Doc oficial: `--plugin-dir` carga solo para la sesión | Algunos harnesses (gentle-ai) escriben parte en el HOME: se acepta porque el HOME es desechable |
| D4 | Modelo | Fijo · varios | **Fijo por ronda (Sonnet, versión fijada)** | Harness-Bench y Terminal-Bench reportan por par modelo+agente | Interacción modelo×harness, que queda para rondas futuras |
| D5 | Tamaño de ronda | 8×3 · 12×5 · 15×5 | **Piloto 1 trial/tarea → ronda 12–15 tareas × 5 trials** | Tabla de potencia; tareas con 30–70% de éxito discriminan | Costo: estimarlo con el piloto antes de comprometerse |
| D6 | Métrica primaria | Éxito · costo · compuesto | **Éxito como guardrail (no-inferioridad) + costo y comportamiento como decisivos** | Potencia: +10 pp en éxito es indetectable; los costos difieren hasta 40x | Declarar "gana en éxito" requiere efectos grandes |
| D7 | Autonomía headless | Preámbulo común · usuario simulado · excluir interactivos | **Preámbulo común idéntico para todas; usuario simulado como fase 2** | Riesgos de superpowers/gentle-ai/BMAD ([04 §3](docs/research/04-catalogo-harnesses.md)); Quorum usa un agente-usuario | Un harness pensado para diálogo puede quedar en desventaja: se documenta |
| D8 | Dónde corre | Docker local · Daytona/Modal | **Docker local** al inicio | Harbor soporta ambos; empezar simple | Concurrencia limitada |
| D9 | Juez LLM | No usar · secundario | **Solo secundario, ciego, de otro modelo y calibrado con 10–20 juicios humanos** | Sesgos documentados (2306.05685); Anthropic | Calidad subjetiva medida con menos precisión |
| D10 | Visibilidad | Público · privado | **Privado hasta completar la ronda 1 con ≥12 tareas** | Material público se contamina (retiro de Verified) | Feedback externo tardío |
| D11 | Placebo | Sin placebo · caveman o prompt de una línea | **Incluir un placebo barato** | ponytail separa "efecto real" de "efecto estilo" con caveman y un prompt de 7 palabras | Una variante más |

## 13. Roadmap

| Fase | Entregable | Criterio de salida |
|---|---|---|
| **F0 — Spike Harbor** | Tarea smoke en formato Harbor; `vanilla-default`, `vanilla-bare` y una variante plugin vía la subclase | Gate de contaminación funcionando; costo y tokens por variante; confirmado que los tests no son visibles al agente |
| **F1 — Absorber navori-evals** | Migrar `00-smoke` y los aprendizajes ([06](docs/research/06-antecedentes-navori-evals.md)); archivar navori-evals | Nada útil queda solo en el prototipo — estado 2026-09-24: `variants/navori.yaml`, commit "variant installed" y bucket `infra`/`contamination` migrados ([06 §7](docs/research/06-antecedentes-navori-evals.md#7-estado-de-la-absorción-f1-2026-09-24)); solo queda archivar el prototipo |
| **F2 — Suite v1** | Paciente + 12–15 tareas + oráculos + corrida tramposa + holdout | Checklist por tarea en verde; piloto calibrado |
| **F3 — Ronda 1** | `RULES.md` pre-registrado; 5–6 variantes (vanilla ×2, navori, gentle-ai, superpowers, ponytail, placebo) | Reporte completo y transcripts de las fallas revisados |
| **F4 — Reporte/dashboard** | Vistas de §11 generadas automáticamente; OTel por skill/herramienta si el desglose lo pide | Reproducible desde `results/` |
| **F5 — Más allá de Claude Code** | Variantes con codex/opencode (adaptadores de Harbor) y agentes propios (`BaseAgent`) | Una ronda mixta |

`codex-default` (baseline, sin harness) se adelantó de F5: ya corre por `owl run`/`owl gate` vía el agente
`codex` nativo de Harbor. El harness/plugins de Codex sigue en F5.

## 14. Trampas a vigilar

Lista completa en [02 §10](docs/research/02-metodologia.md). Las específicas de comparar harnesses:
1. **Baseline contaminado** por la config del usuario. roboco EXP-008: quitar hooks y el CLAUDE.md global cambió el resultado.
2. **Contaminación cruzada:** un harness deja un `AGENTS.md` o `CLAUDE.md` que otro lee.
3. **Presupuesto desigual:** una variante "gana" solo porque gastó más.
4. **Prompts de autonomía asimétricos** entre variantes.
5. **MCP que no cargan en silencio** (`--strict-mcp-config` sin `--mcp-config`): el gate lo detecta.
6. **Tareas a la medida** de un harness → holdout y tareas propuestas por terceros.

## 15. Índice de investigación

| Doc | Contenido |
|---|---|
| [01 — Benchmarks públicos](docs/research/01-benchmarks-publicos.md) | SWE-bench y familia, Terminal-Bench, BaxBench, FeatBench…: formato, calificación, errores documentados |
| [02 — Metodología](docs/research/02-metodologia.md) | Evidencia de que el harness importa; pass^k; estadística con n chico; potencia; juez LLM; reward hacking |
| [03 — Evals de comportamiento](docs/research/03-evals-de-comportamiento.md) | Skills, seguridad, safety, abstención, review; catálogo de tareas B1–B13 |
| [04 — Catálogo de harnesses](docs/research/04-catalogo-harnesses.md) | gentle-ai, superpowers, ponytail, oh-my-claudecode, Ruflo, SuperClaude, BMAD, Spec Kit, GSD…: instalación, riesgos, lo que afirma cada uno |
| [05 — Herramientas y proyectos paralelos](docs/research/05-herramientas-y-proyectos-paralelos.md) | Quorum, ponytail benchmarks, skills-benchmarks, Qihoo harness-bench; Harbor en detalle; aislamiento y observabilidad según la doc oficial |
| [06 — Antecedentes navori-evals](docs/research/06-antecedentes-navori-evals.md) | Qué se reutiliza del prototipo y qué se corrige |
| [`power.py`](docs/research/power.py) | Simulación de potencia estadística |
