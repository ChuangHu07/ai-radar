class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        super().__init__(message)

    def payload(self):
        return {"code": self.code, "message_key": self.code, "details": self.message,
                "material_id": None, "retryable": self.retryable}
