import { SystemClock } from "./clock.ts";

/** M1: structured logging. src/ code calls log.event(...), never console.log. */
export interface LogFields {
  [key: string]: string | number | boolean | undefined;
}

// M5: the log record's own timestamp goes through Clock too, like every other new src/ read of
// the current time — a module-level SystemClock (never test-injected; log lines aren't asserted
// on by any task) rather than a per-call Clock parameter, since that would force every caller of
// log.event/log.error across every package to thread one through just for a log line.
const clock = new SystemClock();

function emit(level: string, event: string, fields: LogFields): void {
  const record = { level, event, ts: clock.now().toISOString(), ...fields };
  process.stdout.write(JSON.stringify(record) + "\n");
}

export const log = {
  event(event: string, fields: LogFields = {}): void {
    emit("info", event, fields);
  },
  error(event: string, fields: LogFields = {}): void {
    emit("error", event, fields);
  },
};
