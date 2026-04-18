class AppError(Exception):
    """Base application exception."""

    status_code = 400
    error_code = "application_error"

    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "resource_not_found"


class ConflictError(AppError):
    status_code = 409
    error_code = "resource_conflict"
