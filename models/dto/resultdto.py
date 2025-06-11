from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ResultDTO(BaseModel, Generic[T]):
    success: bool
    code: int
    message: Optional[str] = None
    data: Optional[T] = None

    @classmethod
    def ok(cls, data: T = None, message: str = "Success"):
        return cls(success=True, code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int, message: str, data: T = None):
        return cls(success=False, code=code, message=message, data=data)