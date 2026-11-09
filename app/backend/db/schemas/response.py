import re
from typing import Any, Generic, List, Optional, TypeVar
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standardized API response envelope."""
    success: bool = Field(..., description="Whether the request succeeded or failed")
    message: str = Field(..., description="Human-readable response message")
    data: Optional[T] = Field(default=None, description="Response payload data")
    errors: List[str] = Field(default_factory=list, description="List of error details, if any")


def success_response(
    data: Any = None,
    message: str = "Operation successful",
    status_code: int = 200,
    **extra: Any,
) -> JSONResponse:
    """Helper to return a standardized success JSONResponse."""
    content = {
        "success": True,
        "message": message,
        "data": data,
        "errors": [],
        **extra,
    }
    return JSONResponse(status_code=status_code, content=content)


def error_response(
    message: str = "An error occurred",
    errors: Optional[List[str]] = None,
    status_code: int = 400,
    data: Any = None,
    **extra: Any,
) -> JSONResponse:
    """Helper to return a standardized error JSONResponse."""
    err_list = errors or []
    content = {
        "success": False,
        "message": message,
        "data": data,
        "errors": err_list,
        "detail": message,  # Preserved for backward compatibility with clients and tests
        **extra,
    }
    return JSONResponse(status_code=status_code, content=content)


def parse_integrity_error(exc: Exception) -> tuple[str, List[str]]:
    """
    Parse an IntegrityError or DB conflict exception to produce a clean, user-friendly
    error message specifically identifying whether a record already exists or a foreign key is invalid.
    """
    orig = str(getattr(exc, "orig", exc))

    # 1. PostgreSQL unique constraint violation: e.g. Key (name)=(Admin) already exists.
    pg_match = re.search(r"Key \((.*?)\)=\((.*?)\) already exists", orig)
    if pg_match:
        field, val = pg_match.group(1), pg_match.group(2)
        field_name = field.replace("_", " ").capitalize()
        msg = f"A record with {field_name} '{val}' already exists."
        return msg, [f"{field}: Value '{val}' is already in use. Please enter a unique value."]

    # 2. SQLite unique constraint violation: e.g. UNIQUE constraint failed: roles.name
    sqlite_match = re.search(r"UNIQUE constraint failed: \w+\.(\w+)", orig)
    if sqlite_match:
        field = sqlite_match.group(1)
        field_name = field.replace("_", " ").capitalize()
        msg = f"A record with this {field_name} already exists."
        return msg, [f"{field}: This value is already in use. Please enter a unique value."]

    # 3. Foreign key violation on delete (referenced by child records):
    if "is still referenced from table" in orig.lower() or "update or delete on table" in orig.lower():
        match_table = re.search(r'is still referenced from table "([^"]+)"', orig)
        ref_table = match_table.group(1).replace("_", " ") if match_table else "other records"
        return (
            f"Cannot delete record: it is still referenced by {ref_table}.",
            [f"Cannot delete this record because records in '{ref_table}' depend on it. Delete or reassign those records first."],
        )

    # 4. Foreign key violation on insert/update (parent not found):
    if "foreign key" in orig.lower() or "violates foreign key constraint" in orig.lower():
        return (
            "Referenced record does not exist. Please check related IDs.",
            ["One or more selected related IDs do not match any existing record."],
        )

    # 5. Fallback for unique constraint / duplicate record error:
    return (
        "A record with these details already exists.",
        ["A record with identical unique fields already exists in the database. Please check your input."],
    )
