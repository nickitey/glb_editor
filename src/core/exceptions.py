import typing as t

from fastapi import HTTPException, status


class GLBEditorException(HTTPException):
    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An error occurred"

    def __init__(
        self,
        status_code: t.Optional[int],
        detail: t.Optional[t.Any],
        headers: t.Optional[dict[str, str]] = None,
    ) -> None:
        status_code = status_code or self.default_status_code
        detail = detail or self.default_detail
        super().__init__(status_code, detail, headers)
