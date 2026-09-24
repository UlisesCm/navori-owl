/** A source of the current time. M5: new src/ code reads time only through this. */
export interface Clock {
  now(): Date;
}

/** The real wall clock. */
export class SystemClock implements Clock {
  now(): Date {
    return new Date();
  }
}

/** A clock fixed at construction, for tests and deterministic day-boundary logic. */
export class FixedClock implements Clock {
  private readonly fixed: Date;

  constructor(fixed: Date) {
    this.fixed = fixed;
  }

  now(): Date {
    return this.fixed;
  }
}
