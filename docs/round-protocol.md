# Protocolo de ronda

Cómo se prepara una ronda N de navori-owl. Spec: `specs/round-protocol/`. La primera instancia es
`specs/r1-refresco/`; cada ronda nueva abre su propio `specs/r<N>-refresco/` con los mismos pasos.

## Secuencia

1. **Corte.** Fijar `cutoff_date` en `rounds/<id>/round.yaml`: el día en que se eligen los pins.
2. **Pins.** Correr `owl pins --round rounds/<id>` y subir cada pin a la última versión estable publicada
   en o antes del corte: Harbor (`pins.harbor` y `pyproject.toml`), la versión del agente
   (`agent_version` de la ronda y de cada variante) y cada harness (`harness.version` de la variante y
   `pins.variants`). `Round.load` rechaza la ronda si algo no coincide.
3. **Spike.** Para cada harness que cambió de versión mayor o de flujo documentado: instalación gratis y
   sin modelo sobre `owl-patient:local` (flags de instalación, archivos fuera de `/app`, telemetría,
   hooks, versión de engram esperada).
4. **Auditoría de prefijos.** Un `auditor` en contexto fresco, que no escribió los manifiestos, audita los
   `artifacts` de cada harness que cambió (criterios de T14 de F3).
5. **Precios.** Si cambió el modelo: las cinco claves de `prices_usd_per_mtok` desde la tabla oficial,
   con fuente y fecha.
6. **Piloto.** Si cambió el modelo: 24 trials de la variante base (cada tarea dev dos veces) fuera de la
   ronda; el estimador de costo debe reproducir `total_cost_usd` al 0.1% en cada uno.
7. **Smoke.** Las variantes de la ronda sobre `tasks/00-smoke` con los pins finales, más los forzados de
   límite.
8. **Holdout.** `cp owl/verifier/lib.sh` a cada `tasks/*/tests/owl-lib.sh` y `holdout/*/tests/owl-lib.sh`
   (sin leer nada de `holdout/`) y `owl validate --suite --holdout` en verde.
9. **Pre-registro.** `RULES.md`, `round.yaml` y `preamble.md`; el usuario aprueba `RULES.md` antes del
   commit. Ninguna tarea de `holdout/burned.yaml` entra como holdout.

## Disparadores

| Disparador | Pasos obligatorios antes del siguiente trial |
|---|---|
| Un harness cambia de versión mayor o de flujo documentado | Spike (3), auditoría de prefijos (4), smoke (7), holdout (8) |
| Cambia el modelo | Precios (5), piloto (6), smoke (7) |
| Cambia `owl/verifier/lib.sh` o un prefijo de `artifacts` | Holdout (8) |
| Cambia cualquier pin | Smoke (7) |

## Cambio de pin después del corte

Un pin cambia después de `cutoff_date` solo con el motivo escrito en `RULES.md` (por ejemplo, una
corrección de seguridad o un retiro del modelo) y repitiendo todos los pasos que pida su disparador antes
del siguiente trial. Un pin que se queda anterior a la versión vigente en el corte también se justifica en
`RULES.md`.

## Holdout revelado

Al revelar una tarea holdout (con el OK del usuario, después del commit del reporte), se agrega a
`holdout/burned.yaml` con la ronda y la fecha. El planificador rechaza cualquier ronda con `--holdout` que
la incluya.
