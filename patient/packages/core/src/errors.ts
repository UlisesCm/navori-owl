/** Base class for every error `packages/api/src` throws (M2). Carries an HTTP status and a
 * machine-readable code so route handlers never have to string-match a message. */
export class AppError extends Error {
  readonly statusCode: number;
  readonly code: string;

  constructor(code: string, message: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

export class NotFoundError extends AppError {
  constructor(message = "not found") {
    super("not_found", message, 404);
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super("validation_error", message, 400);
  }
}

export class ForbiddenError extends AppError {
  constructor(message = "forbidden") {
    super("forbidden", message, 403);
  }
}

export class UnauthorizedError extends AppError {
  constructor(message = "unauthorized") {
    super("unauthorized", message, 401);
  }
}

export class ConflictError extends AppError {
  constructor(message = "conflict") {
    super("conflict", message, 409);
  }
}
