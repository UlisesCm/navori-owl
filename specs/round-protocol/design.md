# Round protocol — Design

## Approach

Cada ronda es un directorio `rounds/<id>/` que hoy se arma a mano con conocimiento que solo vive en el
spec de F3: qué versiones se miden, cuándo se congelan y qué hay que repetir cuando una cambia. Este
diseño mueve ese conocimiento a tres piezas pequeñas que cualquier ronda reutiliza:

1. **Declaración y verificación de pins.** `round.yaml` gana `cutoff_date` y `pins`; cada variante con
   harness declara `harness.version` y `harness.upstream`. `Round.load` compara pins contra lo instalado
   y lo declarado, igual que hoy compara `agent_version` (R1–R3).
2. **Consulta de vigencia.** `owl pins --round DIR` imprime pin contra última versión publicada. Es
   informativo: nunca corre durante una ronda ni decide nada por sí mismo (R5, R6).
3. **Registro de holdout quemado.** `holdout/burned.yaml` lista las tareas reveladas; el planificador
   rechaza una ronda con `--holdout` que las incluya (R7, R8).

Más un documento, `docs/round-protocol.md`, con la tabla disparador → pasos obligatorios (R9, R10). El
documento es el procedimiento; el código solo hace cumplir lo verificable sin red ni juicio.

**Descartado:**
- *Resolver "la última versión" al planificar la ronda.* Haría la ronda irreproducible: el mismo
  `round.yaml` daría planes distintos según el día. Los pins se fijan a mano en `round.yaml` y el
  comando de vigencia solo informa.
- *Un archivo de lock aparte (`rounds/<id>/pins.lock`).* Duplica `round.yaml`, que ya está bajo el
  chequeo de árbol limpio (R3 de F3) y entra al hash del registro de la ronda.
- *Extraer la versión del harness del script de instalación de cada variante.* Los scripts de
  `navori.yaml` y `gentle-ai.yaml` la llevan en variables de shell distintas; parsearlas es frágil. Un
  campo declarativo es más simple y el smoke ya confirma que lo instalado coincide.

## Components

- `owl/round.py` — `Round.load` lee `cutoff_date` y `pins`, compara la versión instalada de Harbor
  (`importlib.metadata.version("harbor")`) y la `harness.version` de cada variante; reúne todas las
  diferencias antes de salir — covers R1, R3. `round_tasks` consulta el registro de quemados cuando
  `holdout` es verdadero — covers R8.
- `owl/variants.py` — `Variant` gana `version` y `upstream` (desde `harness.version` y
  `harness.upstream`); `Variant.load` los exige cuando hay `plugins` o `init` y valida el esquema de
  `upstream` — covers R2.
- `owl/pins.py` (nuevo) — `latest(source, fetch)` para `pypi:`, `npm:`, `github-release:` y
  `github-commit:`; `pin_rows(round_def, fetch)` arma filas (pin, valor, última, fecha, marca); un
  `Fetcher` inyectable (por defecto `urllib.request` con timeout) — covers R5, R6.
- `owl/tasks.py` — `burned_tasks(holdout_dir)` lee `holdout/burned.yaml` sin abrir nada dentro de
  `holdout/*/` — covers R7, R8.
- `owl/report.py` — el encabezado toma `round_def.id`, `cutoff_date` y `pins`; `PHRASE` deja de citar
  `r1` y se forma con el id de la ronda — covers R4.
- `owl/cli.py` — subcomando `pins --round DIR` — covers R5, R6.
- `docs/round-protocol.md` (nuevo) — procedimiento y tabla de disparadores — covers R9, R10.
- `variants/*.yaml` — `harness.version` y `harness.upstream` en `navori`, `superpowers`, `ponytail` y
  `gentle-ai` — covers R2.

## Decisions

- **P1 — Model y agent_version no se duplican en `pins`.** Ya son claves de primer nivel de
  `round.yaml` y `Round.load` ya exige que cada variante comparta `agent_version`. `pins` solo agrega lo
  que hoy no se verifica: Harbor y los harnesses. `owl pins` sí muestra `agent_version` con su fuente
  (`npm:@anthropic-ai/claude-code` para `claude-code`, `npm:@openai/codex` para `codex`), tomada de
  una tabla fija por agente en `owl/pins.py`.
- **P2 — Todas las diferencias en un solo error.** `Round.load` hoy sale en la primera inconsistencia.
  Para pins junta la lista completa: en un refresco cambian varias versiones a la vez y salir una por
  una obliga a N corridas.
- **P3 — `cutoff_date` obligatorio solo con `pins`.** Un `round.yaml` sin `pins` falla con un mensaje
  que nombra ambas claves; no hay rondas viejas que mantener (`rounds/r1/` aún no existe).
- **P4 — `harness.version` es texto libre, comparado por igualdad.** Para fuentes git se escribe
  `v7.0.1@2ce8aa15` o `main@09c434ab` (release o rama, más el prefijo del commit). La compatibilidad
  entre `version` y el `ref` del plugin la confirma el smoke, no un parser.
- **P5 — La vigencia nunca bloquea.** `owl pins` sale con 0 aunque haya pins viejos o fuentes caídas;
  la decisión de subir o justificar un pin es humana y queda en `RULES.md` (R40 de F3).
- **P6 — El registro de quemados vive fuera de las tareas.** `holdout/burned.yaml` está en la raíz de
  `holdout/`, no dentro de una tarea, así que leerlo no toca contenido holdout. Lo escribe a mano quien
  registra la revelación (T26 de F3), con fecha y ronda.

## Contracts

`rounds/<id>/round.yaml` (claves nuevas):
```yaml
cutoff_date: 2026-10-28
pins:
  harbor: "0.25.0"
  variants:
    navori: "0.12.3"
    superpowers: "v7.0.1@2ce8aa15"
    ponytail: "main@09c434ab"
    gentle-ai: "v4.3.1"
```

Variante con harness (`variants/superpowers.yaml`, claves nuevas):
```yaml
harness:
  version: "v7.0.1@2ce8aa15"
  upstream: github-release:obra/superpowers
```

`holdout/burned.yaml`:
```yaml
- task: holdout/30-tenant-filter-leak
  round: r1
  revealed: 2026-11-15
```

`owl pins --round rounds/r1` (stdout, una fila por pin):
```
pin           pinned            latest     date        mark
harbor        0.25.0            0.25.0     2026-10-25
agent         2.1.312           2.1.315    2026-10-30  newer
superpowers   v7.0.1@2ce8aa15   v7.0.1     2026-10-21
gentle-ai     v4.3.1            ?          ?           unknown
```

## Failure modes

- **Fuente caída o con rate limit** (PyPI, npm, GitHub). La fila sale `unknown` y las demás siguen
  (R6). El fetcher usa un timeout corto por fuente para que una caída no bloquee el comando.
- **Prerelease publicado como "último".** `latest` descarta versiones con sufijo de prerelease
  (`dev`, `rc`, `beta`, `alpha`) en PyPI y npm, y releases marcados `prerelease` en GitHub.
- **Harbor no instalado o instalado desde otra ruta.** `importlib.metadata` falla y `Round.load`
  reporta la versión como ausente dentro de la lista de diferencias.
- **Registro de quemados mal formado.** `burned_tasks` falla cerrado: un YAML inválido rechaza
  cualquier plan con `--holdout`.

## Testing strategy

Cada prueba lleva `# Covers: R<n>`; ninguna toca la red (fetcher falso).

| Riesgo | Prueba |
|---|---|
| Ronda corre con Harbor distinto del declarado | `tests/test_round.py::test_round_refuses_harbor_mismatch` (R1, R3) |
| Variante con harness sin versión declarada pasa | `tests/test_variants.py::test_harness_version_required_with_plugins_or_init` (R2) |
| Varias diferencias y solo se ve la primera | `tests/test_round.py::test_round_lists_every_pin_mismatch` (R3) |
| Reporte de r2 dice "r1" | `tests/test_report.py::test_header_uses_round_id_and_pins` (R4) |
| Pin viejo sin marca | `tests/test_pins.py::test_marks_newer_and_major` (R5) |
| Fuente caída rompe todo el comando | `tests/test_pins.py::test_unreachable_source_is_unknown` (R6) |
| Prerelease tomado como último | `tests/test_pins.py::test_skips_prereleases` (R5) |
| Tarea revelada vuelve como holdout | `tests/test_round.py::test_plan_refuses_burned_holdout` (R7, R8) |
| Registro roto deja pasar holdout | `tests/test_tasks.py::test_burned_registry_fails_closed` (R7, R8) |
| Procedimiento incompleto | `tests/test_docs.py::test_round_protocol_has_trigger_table` (R9, R10) |

## NOT in scope

- **Subir versiones automáticamente.** `owl pins` informa; el cambio de pin es un commit revisado.
- **Modelo en `owl pins`.** No hay una fuente estable de "último modelo"; el cambio de modelo es una
  decisión del usuario registrada en el spec de la ronda.
- **Rondas en paralelo o sandboxes remotos.** Escalar la ejecución queda fuera; esto escala la
  repetición de rondas.
- **Migrar `specs/f2-suite-v1/`.** Está cerrado; no se reescribe.
