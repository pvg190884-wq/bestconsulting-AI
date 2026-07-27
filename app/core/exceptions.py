"""Кастомные исключения."""

class BestConsultingException(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(self.message)

class LLMUnavailableException(BestConsultingException):
    def __init__(self, provider: str):
        super().__init__(
            message=f"Провайдер {provider} временно недоступен.",
            status_code=503,
            code="LLM_UNAVAILABLE",
        )

class ChannelException(BestConsultingException):
    def __init__(self, channel: str, detail: str):
        super().__init__(
            message=f"Ошибка канала {channel}: {detail}",
            status_code=502,
            code="CHANNEL_ERROR",
        )

class KnowledgeBaseException(BestConsultingException):
    def __init__(self, detail: str):
        super().__init__(
            message=f"Ошибка базы знаний: {detail}",
            status_code=500,
            code="KB_ERROR",
        )
