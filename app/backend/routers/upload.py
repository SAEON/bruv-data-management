"""Single-record capture and validated CSV/Excel imports."""

import io
import json
import math
import csv
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import bcrypt
import pandas as pd
from pydantic import BaseModel
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Time,
    cast,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from db import database, models
from db.schemas.response import parse_integrity_error

router = APIRouter(prefix="/upload", tags=["data-entry"])
SUPPORTED_UPLOAD_EXTENSIONS = (".csv", ".xlsx", ".xls")
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000
SENSITIVE_FIELDS = {"password"}
AUTO_FIELDS = {"created_at", "assigned_at"}
LABELS = {"fieldtrips": "Field trips", "max_n": "MaxN", "cal_success": "Calibration success"}

FIELD_ALIASES: Dict[str, Dict[str, tuple[str, ...]]] = {
    "calibrations": {
        "cal_success": ("calibration_success", "cal_successful", "success", "cal_status"),
    }
}
# Preserve required business fields in addition to database constraints.
REQUIRED_FIELDS = {
    "roles": {"name"},
    "users": {"full_name"},
    "observations": {"deployment_id"},
    "measurements": {"deployment_id"},
    "analysis_periods": {"deployment_id"},
}

TABLE_LOOKUP_COLUMNS: Dict[str, List[str]] = {
    "deployments": ["opcode", "alt_opcode"],
    "projects": ["project_code", "project_name"],
    "fieldtrips": ["fieldtrip_code", "trip_code"],
    "roles": ["name"],
    "users": ["email", "username", "full_name"],
}

FOREIGN_KEY_ALIASES: Dict[str, tuple[str, ...]] = {
    "deployment_id": ("opcode", "deployment_opcode", "deployment"),
    "project_id": ("project_code", "project_name", "project"),
    "fieldtrip_id": ("fieldtrip_code", "trip_code", "fieldtrip", "trip"),
    "role_id": ("role_name", "role"),
    "user_id": ("email", "username", "user"),
}


def _label(name):
    return LABELS.get(name, name.replace("_", " ").capitalize())


def _build_schemas():
    schemas = {}
    for model_name in models.__all__:
        model = getattr(models, model_name)
        table = model.__table__
        if table.name == "upload_logs":
            continue
        fields = {}
        for column in table.columns:
            if column.primary_key or column.name in AUTO_FIELDS:
                continue
            kind = "str"
            for sql_type, field_type in (
                (Boolean, "bool"),
                (Integer, "int"),
                (Float, "float"),
                (DateTime, "datetime"),
                (Date, "date"),
                (Time, "time"),
            ):
                if isinstance(column.type, sql_type):
                    kind = field_type
                    break
            required = (
                not column.nullable
                and column.default is None
                and column.server_default is None
            ) or column.name in REQUIRED_FIELDS.get(table.name, set())
            spec = {"type": kind, "label": _label(column.name), "required": required}
            if kind == "bool":
                spec["description"] = "Use Yes or No (defaults to No)."
                spec["default"] = False
            if isinstance(column.type, Text):
                spec["multiline"] = True
            if getattr(column.type, "length", None):
                spec["max_length"] = column.type.length
            if column.foreign_keys:
                ref_target = next(iter(column.foreign_keys)).target_fullname
                spec["references"] = ref_target
                target_table = ref_target.split(".")[0]
                if target_table == "deployments":
                    spec["lookup_field"] = "opcode"
                elif target_table in TABLE_LOOKUP_COLUMNS:
                    spec["lookup_field"] = TABLE_LOOKUP_COLUMNS[target_table][0]
            fields[column.name] = spec
        schemas[table.name] = {
            "label": _label(table.name),
            "model": model,
            "fields": fields,
            "required_fields": [
                name for name, spec in fields.items() if spec["required"]
            ],
        }
    return schemas


ENTITY_SCHEMAS = _build_schemas()


def _get_unique_columns(model):
    table = model.__table__
    unique_cols = set()
    for col in table.columns:
        if col.unique:
            unique_cols.add(col.name)
    for const in table.constraints:
        if const.__class__.__name__ == "UniqueConstraint":
            for col in const.columns:
                unique_cols.add(col.name)
    for idx in table.indexes:
        if idx.unique:
            for col in idx.columns:
                unique_cols.add(col.name)
    return unique_cols


ALIASES = {
    "analysis_period": "analysis_periods",
    "observation": "observations",
    "measurement": "measurements",
    "deployment": "deployments",
    "fieldtrip": "fieldtrips",
    "project": "projects",
    "day_sheet": "day_sheets",
    "calibration": "calibrations",
    "role": "roles",
    "user": "users",
    "agent": "agents",
    "person": "people",
}


def _canonical_entity_type(entity_type: str) -> str:
    if entity_type in ENTITY_SCHEMAS:
        return entity_type
    lowered = (entity_type or "").lower().strip()
    if lowered in ENTITY_SCHEMAS:
        return lowered
    if lowered in ALIASES and ALIASES[lowered] in ENTITY_SCHEMAS:
        return ALIASES[lowered]
    if f"{lowered}s" in ENTITY_SCHEMAS:
        return f"{lowered}s"
    if lowered.endswith("s") and lowered[:-1] in ENTITY_SCHEMAS:
        return lowered[:-1]
    return entity_type


def _get_schema(entity_type):
    canonical = _canonical_entity_type(entity_type)
    if canonical not in ENTITY_SCHEMAS:
        raise HTTPException(status_code=400, detail="Unknown data entry table")
    return ENTITY_SCHEMAS[canonical]


def _ensure_supported_file(filename: Optional[str]) -> str:
    extension = next(
        (
            ext
            for ext in SUPPORTED_UPLOAD_EXTENSIONS
            if (filename or "").lower().endswith(ext)
        ),
        "",
    )
    if not extension:
        raise HTTPException(
            status_code=400, detail="Upload a CSV or Excel file (.csv, .xlsx, .xls)."
        )
    return extension


async def _contents(file):
    _ensure_supported_file(file.filename)
    contents = await file.read(MAX_FILE_BYTES + 1)
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Files must be 10 MB or smaller.")
    if not contents:
        raise HTTPException(status_code=422, detail="The file is empty.")
    return contents


def _read_uploaded_table(contents, filename, sheet_name=None):
    extension = _ensure_supported_file(filename)
    try:
        buffer = io.BytesIO(contents)
        if extension == ".csv":
            headers = next(csv.reader(io.StringIO(contents.decode("utf-8-sig"))), [])
            # Keep identifiers and leading zeros intact; coerce values only after mapping.
            df = pd.read_csv(
                buffer,
                encoding="utf-8-sig",
                dtype=str,
                keep_default_na=False,
                nrows=MAX_ROWS + 1,
            )
        else:
            header_row = pd.read_excel(
                buffer,
                sheet_name=sheet_name or 0,
                header=None,
                nrows=1,
                keep_default_na=False,
            )
            headers = [] if header_row.empty else list(header_row.iloc[0])
            buffer.seek(0)
            df = pd.read_excel(
                buffer,
                sheet_name=sheet_name or 0,
                dtype=object,
                keep_default_na=False,
                nrows=MAX_ROWS + 1,
            )
        headers = [str(header).strip() for header in headers]
        if len(headers) != len(set(headers)) or any(not header for header in headers):
            raise HTTPException(
                status_code=422, detail="Every column needs a unique, non-empty header."
            )
        df.columns = [str(column).strip() for column in df.columns]
        if not df.columns.is_unique or any(
            not column or column.startswith("Unnamed:") for column in df.columns
        ):
            raise HTTPException(
                status_code=422, detail="Every column needs a unique, non-empty header."
            )
        if len(df) > MAX_ROWS:
            raise HTTPException(
                status_code=422, detail="Upload at most 10,000 rows at a time."
            )
        # Blank rows do not create empty records. Keep indexes for original spreadsheet row numbers.
        df = df.loc[
            ~df.apply(lambda row: all(_is_empty(value) for value in row), axis=1)
        ]
        if df.empty:
            raise HTTPException(
                status_code=422, detail="The selected sheet has no data rows."
            )
        return df
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Unable to read the file. Check its format, headers and selected sheet.",
        ) from exc


def _is_empty(value):
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or (not isinstance(value, (str, list, dict)) and bool(pd.isna(value)))
    )


def coerce_value(val: Any, target_type: str) -> tuple[Any, Optional[str]]:
    if isinstance(val, (dict, list, tuple)):
        return None, "Enter a single value."
    if _is_empty(val):
        if target_type == "bool":
            return False, None
        return None, None
    if target_type == "bool":
        if isinstance(val, bool):
            return val, None
        if isinstance(val, (int, float)):
            if val in (1, 1.0):
                return True, None
            if val in (0, 0.0, 2, 2.0):
                return False, None
            return None, "Use Yes or No."
        text = str(val).strip()
        cleaned = text.lower()
        if cleaned.endswith(".0"):
            cleaned = cleaned[:-2]
        if cleaned in ("true", "1", "yes", "y", "t"):
            return True, None
        if cleaned in ("false", "0", "2", "no", "n", "f"):
            return False, None
        return None, "Use Yes or No."
    text = str(val).strip()
    try:
        if target_type == "str":
            return text, None
        if target_type == "int":
            number = Decimal(text)
            if not number.is_finite() or number != number.to_integral_value():
                return None, "Enter a whole number."
            if not -(2**31) <= number < 2**31:
                return None, "Whole number is outside the supported range."
            return int(number), None
        if target_type == "float":
            number = float(text)
            if not math.isfinite(number):
                return None, "Enter a finite number."
            return number, None
        if target_type == "time":
            return val if isinstance(val, time) else time.fromisoformat(text), None
        if target_type in ("date", "datetime"):
            if isinstance(val, (int, float)):
                return None, "Use a date such as YYYY-MM-DD."
            parsed = pd.to_datetime(val, errors="raise")
            if pd.isna(parsed):
                return None, "Enter a valid date."
            result = (
                parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
            )
            return result.date() if target_type == "date" else result, None
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        return None, f"Enter a valid {target_type} value."
    return None, "Unsupported field type."


def _is_numeric_id(val: Any) -> tuple[bool, Optional[int]]:
    if isinstance(val, bool):
        return False, None
    if isinstance(val, int):
        if -(2**31) <= val < 2**31:
            return True, val
        return True, None
    if isinstance(val, float):
        if math.isfinite(val) and val.is_integer():
            int_val = int(val)
            if -(2**31) <= int_val < 2**31:
                return True, int_val
            return True, None
        return False, None
    raw_str = str(val).strip()
    try:
        num = Decimal(raw_str)
        if num.is_finite() and num == num.to_integral_value():
            int_val = int(num)
            if -(2**31) <= int_val < 2**31:
                return True, int_val
            return True, None
    except (InvalidOperation, ValueError, TypeError):
        pass
    return False, None


def _resolve_foreign_key(
    val: Any,
    spec: Dict[str, Any],
    field_name: str = "",
    db: Optional[Session] = None,
    fk_cache: Optional[Dict[str, tuple[Any, Optional[str]]]] = None,
) -> tuple[Optional[int], Optional[str]]:
    if isinstance(val, (dict, list, tuple)):
        return None, "Enter a single value."
    if _is_empty(val):
        return None, None
    raw_str = str(val).strip()
    if not raw_str:
        return None, None

    ref_target = spec.get("references")
    if not ref_target and field_name == "deployment_id":
        ref_target = "deployments.id"

    target_table_name = ""
    target_pk_name = "id"
    if ref_target:
        parts = ref_target.split(".")
        target_table_name = parts[0]
        if len(parts) > 1:
            target_pk_name = parts[1]
    elif field_name == "deployment_id":
        target_table_name = "deployments"

    cache_key = f"{target_table_name}:{raw_str}"
    if fk_cache is not None and cache_key in fk_cache:
        return fk_cache[cache_key]

    def _cache_and_return(result_id: Optional[int], err: Optional[str]):
        res = (result_id, err)
        if fk_cache is not None:
            fk_cache[cache_key] = res
        return res

    # 1. If the ID is a number, store it
    is_num, int_id = _is_numeric_id(val)
    if is_num:
        if int_id is None:
            return _cache_and_return(None, "Whole number is outside the supported range.")
        return _cache_and_return(int_id, None)

    # 2. If it's a text, lookup on the primary table and use that id
    target_schema = ENTITY_SCHEMAS.get(target_table_name)
    target_label = target_schema["label"] if target_schema else _label(target_table_name)
    singular_label = (
        target_label[:-1]
        if target_label.endswith("s") and not target_label.endswith("ss")
        else target_label
    )

    if db is None:
        if target_table_name == "deployments":
            return _cache_and_return(None, f"Database unavailable to resolve opcode '{raw_str}'.")
        return _cache_and_return(
            None, f"Database unavailable to resolve {singular_label.lower()} '{raw_str}'."
        )

    target_table = None
    if target_schema and target_schema.get("model") is not None:
        target_table = target_schema["model"].__table__
    elif hasattr(database, "Base") and target_table_name in database.Base.metadata.tables:
        target_table = database.Base.metadata.tables[target_table_name]

    if target_table is None:
        return _cache_and_return(None, f"Primary table '{target_table_name}' not found.")

    pk_col = getattr(target_table.c, target_pk_name, None)
    if pk_col is None:
        pk_col = next(iter(target_table.primary_key.columns))

    lookup_cols = []
    preferred = TABLE_LOOKUP_COLUMNS.get(target_table_name, [])
    for col_name in preferred:
        if col_name in target_table.c and col_name not in lookup_cols:
            lookup_cols.append(col_name)

    spec_lookup = spec.get("lookup_field")
    if spec_lookup and spec_lookup in target_table.c and spec_lookup not in lookup_cols:
        lookup_cols.insert(0, spec_lookup)

    if not lookup_cols:
        for col in target_table.columns:
            if isinstance(col.type, (String, Text)):
                lookup_cols.append(col.name)

    resolved_id = None
    # 2a. Exact match on primary table
    for col_name in lookup_cols:
        col = target_table.c[col_name]
        try:
            resolved_id = db.execute(
                select(pk_col).where(col == raw_str)
            ).scalar_one_or_none()
            if resolved_id is not None:
                break
        except Exception:
            resolved_id = None

    # 2b. Case-insensitive match on primary table
    if resolved_id is None:
        for col_name in lookup_cols:
            col = target_table.c[col_name]
            try:
                resolved_id = db.execute(
                    select(pk_col).where(
                        func.lower(cast(col, String)) == raw_str.lower()
                    )
                ).scalar_one_or_none()
                if resolved_id is not None:
                    break
            except Exception:
                resolved_id = None

    if resolved_id is None:
        if target_table_name == "deployments":
            err = f"Deployment with opcode or ID '{raw_str}' not found."
        else:
            err = f"{singular_label} with '{raw_str}' not found."
        return _cache_and_return(None, err)

    return _cache_and_return(resolved_id, None)


def _resolve_deployment_foreign_key(
    val: Any,
    db: Optional[Session] = None,
    fk_cache: Optional[Dict[str, tuple[Any, Optional[str]]]] = None,
) -> tuple[Optional[int], Optional[str]]:
    spec = {"references": "deployments.id", "lookup_field": "opcode"}
    return _resolve_foreign_key(
        val, spec=spec, field_name="deployment_id", db=db, fk_cache=fk_cache
    )


def _validate_record(raw, schema, db=None, fk_cache=None):
    # Support foreign key aliases
    for fk_field, aliases in FOREIGN_KEY_ALIASES.items():
        if fk_field in schema["fields"] and fk_field not in raw:
            for alias in aliases:
                if alias in raw:
                    raw = dict(raw)
                    raw[fk_field] = raw.pop(alias)
                    break

    # Support field aliases (e.g. calibration_success -> cal_success)
    table_name = schema.get("model").__table__.name if schema.get("model") else None
    if table_name and table_name in FIELD_ALIASES:
        for canon_field, aliases in FIELD_ALIASES[table_name].items():
            if canon_field in schema["fields"] and canon_field not in raw:
                for alias in aliases:
                    if alias in raw:
                        raw = dict(raw)
                        raw[canon_field] = raw.pop(alias)
                        break

    data, errors = {}, []
    unknown = set(raw) - set(schema["fields"])
    if unknown:
        errors.append("Unknown fields: " + ", ".join(sorted(unknown)))
    for name, spec in schema["fields"].items():
        if name not in raw:
            if spec.get("type") == "bool":
                data[name] = False
            continue
        if spec.get("references") or name == "deployment_id":
            value, error = _resolve_foreign_key(
                raw[name], spec=spec, field_name=name, db=db, fk_cache=fk_cache
            )
        else:
            value, error = coerce_value(raw[name], spec["type"])
        if error:
            errors.append(f"{spec['label']}: {error}")
        elif value is not None:
            if spec.get("max_length") and len(str(value)) > spec["max_length"]:
                errors.append(
                    f"{spec['label']}: Use at most {spec['max_length']} characters."
                )
            elif name == "password" and len(str(raw[name]).encode("utf-8")) > 72:
                errors.append("Password: Use at most 72 UTF-8 bytes.")
            else:
                data[name] = str(raw[name]) if name == "password" else value
    for name in schema["required_fields"]:
        if name not in data:
            errors.append(f"{schema['fields'][name]['label']}: This field is required.")
    if not data and not errors:
        errors.append("Enter at least one field.")
    return data, errors


class BulkEditRequest(BaseModel):
    ids: Optional[List[int]] = None
    updates: Optional[Dict[str, Any]] = None
    records: Optional[List[Dict[str, Any]]] = None


class BulkDeleteRequest(BaseModel):
    ids: List[int]


def _validate_update_record(raw, schema, db=None, fk_cache=None):
    for fk_field, aliases in FOREIGN_KEY_ALIASES.items():
        if fk_field in schema["fields"] and fk_field not in raw:
            for alias in aliases:
                if alias in raw:
                    raw = dict(raw)
                    raw[fk_field] = raw.pop(alias)
                    break

    table_name = schema.get("model").__table__.name if schema.get("model") else None
    if table_name and table_name in FIELD_ALIASES:
        for canon_field, aliases in FIELD_ALIASES[table_name].items():
            if canon_field in schema["fields"] and canon_field not in raw:
                for alias in aliases:
                    if alias in raw:
                        raw = dict(raw)
                        raw[canon_field] = raw.pop(alias)
                        break

    data, errors = {}, []
    for name in raw:
        if name not in schema["fields"]:
            continue
        spec = schema["fields"][name]
        if spec.get("references") or name == "deployment_id":
            value, error = _resolve_foreign_key(
                raw[name], spec=spec, field_name=name, db=db, fk_cache=fk_cache
            )
        else:
            value, error = coerce_value(raw[name], spec["type"])
        if error:
            errors.append(f"{spec['label']}: {error}")
        else:
            if (
                spec.get("max_length")
                and value is not None
                and len(str(value)) > spec["max_length"]
            ):
                errors.append(
                    f"{spec['label']}: Use at most {spec['max_length']} characters."
                )
            elif (
                name == "password"
                and value is not None
                and len(str(raw[name]).encode("utf-8")) > 72
            ):
                errors.append("Password: Use at most 72 UTF-8 bytes.")
            else:
                data[name] = str(raw[name]) if name == "password" else value
    for name in schema["required_fields"]:
        if name in raw and (data.get(name) is None or data.get(name) == ""):
            errors.append(f"{schema['fields'][name]['label']}: This field cannot be empty.")
    return data, errors


def _mapping(mapping_json, df, schema):
    try:
        mapping = json.loads(mapping_json)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid column mapping.")
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=400, detail="Column mapping must be an object.")
    targets = []
    normalized_mapping = {}
    for source, raw_target in mapping.items():
        if raw_target in ("", "__ignore__", None):
            continue
        target = raw_target
        for fk_field, aliases in FOREIGN_KEY_ALIASES.items():
            if (
                target in aliases
                and target not in schema["fields"]
                and fk_field in schema["fields"]
            ):
                target = fk_field
                break
        table_name = schema.get("model").__table__.name if schema.get("model") else None
        if table_name and table_name in FIELD_ALIASES:
            for canon_field, aliases in FIELD_ALIASES[table_name].items():
                if (
                    target in aliases
                    and target not in schema["fields"]
                    and canon_field in schema["fields"]
                ):
                    target = canon_field
                    break
        if (
            source not in df.columns
            or not isinstance(target, str)
            or target not in schema["fields"]
        ):
            raise HTTPException(
                status_code=400, detail="Mapping contains an unknown column or field."
            )
        targets.append(target)
        normalized_mapping[source] = target
    if len(set(targets)) != len(targets):
        raise HTTPException(status_code=400, detail="Map each target field only once.")
    if not targets:
        raise HTTPException(status_code=400, detail="Map at least one column.")
    missing = set(schema["required_fields"]) - set(targets)
    if missing:
        raise HTTPException(
            status_code=400, detail="Map required fields: " + ", ".join(sorted(missing))
        )
    return normalized_mapping


def _validated_rows(df, mapping, schema, db=None):
    rows = []
    model = schema.get("model")
    unique_cols = _get_unique_columns(model) if model else set()
    table = model.__table__ if model else None

    # Cache foreign key lookups across rows for batch performance
    fk_cache = {}

    # Track seen values within the spreadsheet to prevent case-insensitive duplicates
    seen_in_batch = {col: {} for col in unique_cols}

    for index, row in df.iterrows():
        raw = {target: row[source] for source, target in mapping.items()}
        data, errors = _validate_record(raw, schema, db=db, fk_cache=fk_cache)
        row_num = int(index) + 2

        if not errors:
            for col_name in unique_cols:
                val = data.get(col_name)
                if val is not None:
                    str_val = str(val).strip()
                    val_key = str_val.lower() if isinstance(val, str) else str_val
                    col_label = schema["fields"][col_name]["label"]

                    # 1. Check duplicate within the uploaded sheet
                    if val_key in seen_in_batch[col_name]:
                        first_row = seen_in_batch[col_name][val_key]
                        errors.append(
                            f"{col_label}: Duplicate value '{str_val}' in file (matches row {first_row} case-insensitively)."
                        )
                    else:
                        seen_in_batch[col_name][val_key] = row_num

                    # 2. Check duplicate against existing database records
                    if db is not None and table is not None and not errors:
                        col = table.c[col_name]
                        condition = (
                            func.lower(cast(col, String)) == func.lower(str_val)
                            if isinstance(val, str)
                            else col == val
                        )
                        existing = db.execute(select(col).where(condition)).scalar_one_or_none()
                        if existing is not None:
                            errors.append(
                                f"{col_label}: Value '{str_val}' already exists in database (matches existing '{existing}')."
                            )

        rows.append({"row_number": row_num, "data": data, "errors": errors})
    return rows


def _public_data(data):
    return {
        key: (
            "••••••••"
            if key in SENSITIVE_FIELDS
            else (
                value.isoformat()
                if isinstance(value, (date, datetime, time))
                else value
            )
        )
        for key, value in data.items()
    }


def _insert(db, schema, data):
    values = dict(data)
    if "password" in values:
        values["password"] = bcrypt.hashpw(
            values["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
    return db.execute(
        schema["model"].__table__.insert().values(**values)
    ).inserted_primary_key[0]


@router.get("/schemas")
async def get_schemas():
    return {
        name: {key: value for key, value in schema.items() if key != "model"}
        for name, schema in ENTITY_SCHEMAS.items()
    }


@router.post("/record/{entity_type}", status_code=201)
def capture_record(
    entity_type: str, record: dict = Body(...), db: Session = Depends(database.get_db)
):
    schema = _get_schema(entity_type)
    data, errors = _validate_record(record, schema, db=db)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Check the record fields.", "errors": errors},
        )

    # Case-insensitive duplicate check on unique columns
    model = schema["model"]
    unique_cols = _get_unique_columns(model)
    table = model.__table__
    for col_name in unique_cols:
        val = data.get(col_name)
        if val is not None:
            col = table.c[col_name]
            str_val = str(val).strip()
            condition = (
                func.lower(cast(col, String)) == func.lower(str_val)
                if isinstance(val, str)
                else col == val
            )
            existing = db.execute(select(col).where(condition)).scalar_one_or_none()
            if existing is not None:
                field_label = schema["fields"][col_name]["label"]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"A record with {field_label} '{val}' already exists (matches existing '{existing}').",
                        "errors": [
                            f"{col_name}: Value '{val}' already exists (case-insensitive duplicate of '{existing}'). Please use a unique value."
                        ],
                    },
                )

    try:
        record_id = _insert(db, schema, data)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message, errors = parse_integrity_error(exc)
        raise HTTPException(
            status_code=409,
            detail={"message": message, "errors": errors},
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to save the record. Check the database connection and migrations.",
        )
    return {
        "success": True,
        "id": record_id,
        "data": {"id": record_id},
        "entity_type": entity_type,
        "message": "Record saved successfully.",
    }


@router.put("/record/{entity_type}/{record_id}")
def update_record(
    entity_type: str,
    record_id: int,
    record: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    model = schema["model"]
    table = model.__table__
    pk_col = next(iter(table.primary_key.columns))

    existing_record = db.execute(
        select(table).where(pk_col == record_id)
    ).mappings().first()
    if not existing_record:
        raise HTTPException(
            status_code=404,
            detail=f"{schema['label']} record with ID {record_id} not found.",
        )

    data, errors = _validate_update_record(record, schema, db=db)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Check the record fields.", "errors": errors},
        )
    if not data:
        raise HTTPException(
            status_code=400,
            detail="No valid fields provided to update.",
        )

    unique_cols = _get_unique_columns(model)
    for col_name in unique_cols:
        val = data.get(col_name)
        if val is not None:
            col = table.c[col_name]
            str_val = str(val).strip()
            condition = (
                func.lower(cast(col, String)) == func.lower(str_val)
                if isinstance(val, str)
                else col == val
            )
            existing_dup = db.execute(
                select(col).where(condition, pk_col != record_id)
            ).scalar_one_or_none()
            if existing_dup is not None:
                field_label = schema["fields"][col_name]["label"]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"A record with {field_label} '{val}' already exists (matches existing '{existing_dup}').",
                        "errors": [
                            f"{col_name}: Value '{val}' already exists (case-insensitive duplicate of '{existing_dup}'). Please use a unique value."
                        ],
                    },
                )

    values = dict(data)
    if "password" in values:
        if values["password"]:
            values["password"] = bcrypt.hashpw(
                values["password"].encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
        else:
            values.pop("password", None)

    try:
        db.execute(
            table.update().where(pk_col == record_id).values(**values)
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message, errors = parse_integrity_error(exc)
        raise HTTPException(
            status_code=409,
            detail={"message": message, "errors": errors},
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to update the record. Check the database connection and migrations.",
        )

    updated_row = db.execute(
        select(table).where(pk_col == record_id)
    ).mappings().first()

    return {
        "success": True,
        "id": record_id,
        "entity_type": entity_type,
        "message": f"{schema['label']} record #{record_id} updated successfully.",
        "data": _public_data(dict(updated_row)) if updated_row else None,
    }


@router.delete("/record/{entity_type}/{record_id}")
@router.post("/record/{entity_type}/{record_id}/delete")
def delete_record(
    entity_type: str,
    record_id: int,
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    model = schema["model"]
    table = model.__table__
    pk_col = next(iter(table.primary_key.columns))

    existing_record = db.execute(
        select(table).where(pk_col == record_id)
    ).mappings().first()
    if not existing_record:
        raise HTTPException(
            status_code=404,
            detail=f"{schema['label']} record with ID {record_id} not found.",
        )

    try:
        db.execute(table.delete().where(pk_col == record_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message, errors = parse_integrity_error(exc)
        raise HTTPException(
            status_code=409,
            detail={"message": message, "errors": errors},
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to delete the record. Check the database connection and migrations.",
        )

    return {
        "success": True,
        "id": record_id,
        "entity_type": entity_type,
        "message": f"{schema['label']} record #{record_id} deleted successfully.",
    }


@router.delete("/records/{entity_type}/bulk")
@router.post("/records/{entity_type}/delete-bulk")
def bulk_delete_records(
    entity_type: str,
    payload: BulkDeleteRequest,
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    model = schema["model"]
    table = model.__table__
    pk_col = next(iter(table.primary_key.columns))

    if not payload.ids:
        raise HTTPException(status_code=400, detail="No record IDs selected for deletion.")

    ids = list(dict.fromkeys(payload.ids))
    try:
        res = db.execute(table.delete().where(pk_col.in_(ids)))
        db.commit()
        deleted_count = res.rowcount
    except IntegrityError as exc:
        db.rollback()
        message, errors = parse_integrity_error(exc)
        raise HTTPException(
            status_code=409,
            detail={"message": message, "errors": errors},
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Failed to delete records. Database error.",
        )

    return {
        "success": True,
        "entity_type": entity_type,
        "deleted_count": deleted_count,
        "data": {"deleted_count": deleted_count, "ids": ids},
        "message": f"Successfully deleted {deleted_count} {schema['label'].lower()} record(s).",
    }


@router.patch("/records/{entity_type}/bulk")
def bulk_edit_records(
    entity_type: str,
    payload: BulkEditRequest,
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    model = schema["model"]
    table = model.__table__
    pk_col = next(iter(table.primary_key.columns))
    unique_cols = _get_unique_columns(model)
    disallowed = {pk_col.name} | AUTO_FIELDS

    # Multi-record batch update mode (e.g. from bulk records grid editor)
    if payload.records is not None:
        if not payload.records:
            raise HTTPException(status_code=400, detail="No records provided for bulk update.")

        record_updates = []
        for index, item in enumerate(payload.records):
            if not isinstance(item, dict):
                raise HTTPException(status_code=400, detail=f"Record at index {index} must be an object.")
            rec_id = item.get("id") or item.get(pk_col.name)
            if rec_id is None:
                raise HTTPException(status_code=400, detail=f"Record at index {index} is missing an 'id'.")
            try:
                rec_id = int(rec_id)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail=f"Record ID at index {index} is invalid: '{rec_id}'.")

            raw_updates = {
                k: v for k, v in item.items()
                if k not in disallowed and k in schema["fields"]
            }
            if not raw_updates:
                continue

            coerced_vals, field_errors = _validate_update_record(raw_updates, schema, db=db)
            if field_errors:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": f"Validation failed for record #{rec_id}.",
                        "errors": [f"Record #{rec_id} - {err}" for err in field_errors],
                    },
                )
            record_updates.append((rec_id, coerced_vals))

        if not record_updates:
            return {
                "success": True,
                "entity_type": entity_type,
                "updated_count": 0,
                "total_requested": len(payload.records),
                "data": {"updated_count": 0, "total_requested": len(payload.records)},
                "message": "No changes to update.",
            }

        # Check for case-insensitive duplicate collisions within the batch
        batch_seen = {col_name: {} for col_name in unique_cols}
        for rec_id, vals in record_updates:
            for col_name in unique_cols:
                val = vals.get(col_name)
                if val is not None:
                    val_lower = str(val).strip().lower()
                    if val_lower in batch_seen[col_name]:
                        prev_id = batch_seen[col_name][val_lower]
                        field_label = schema["fields"][col_name]["label"]
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "message": f"Duplicate value '{val}' specified for {field_label} on records #{prev_id} and #{rec_id}.",
                                "errors": [
                                    f"{col_name}: Cannot assign the same value '{val}' to multiple records in the same bulk update."
                                ],
                            },
                        )
                    batch_seen[col_name][val_lower] = rec_id

        # Check for case-insensitive duplicate collisions against existing DB records
        for rec_id, vals in record_updates:
            for col_name in unique_cols:
                val = vals.get(col_name)
                if val is not None:
                    col = table.c[col_name]
                    str_val = str(val).strip()
                    condition = (
                        func.lower(cast(col, String)) == func.lower(str_val)
                        if isinstance(val, str)
                        else col == val
                    )
                    existing_dup = db.execute(
                        select(col).where(condition, pk_col != rec_id)
                    ).scalar_one_or_none()
                    if existing_dup is not None:
                        field_label = schema["fields"][col_name]["label"]
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "message": f"Record #{rec_id}: A record with {field_label} '{val}' already exists (matches existing '{existing_dup}').",
                                "errors": [
                                    f"{col_name}: Value '{val}' on record #{rec_id} already exists in another record."
                                ],
                            },
                        )

        # Apply updates atomically
        try:
            updated_count = 0
            for rec_id, vals in record_updates:
                row_vals = dict(vals)
                if "password" in row_vals:
                    if row_vals["password"]:
                        row_vals["password"] = bcrypt.hashpw(
                            row_vals["password"].encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")
                    else:
                        row_vals.pop("password", None)
                if row_vals:
                    db.execute(table.update().where(pk_col == rec_id).values(**row_vals))
                    updated_count += 1
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            message, errs = parse_integrity_error(exc)
            raise HTTPException(
                status_code=409,
                detail={"message": message, "errors": errs},
            )
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="Failed to apply bulk updates. Database error.",
            )

        return {
            "success": True,
            "entity_type": entity_type,
            "updated_count": updated_count,
            "total_requested": len(payload.records),
            "data": {
                "updated_count": updated_count,
                "total_requested": len(payload.records),
            },
            "message": f"Successfully updated {updated_count} {schema['label'].lower()} record(s).",
        }

    # Uniform update mode across multiple IDs
    if not payload.ids:
        raise HTTPException(status_code=400, detail="No record IDs selected for bulk update.")

    ids = list(dict.fromkeys(payload.ids))
    updates_raw = payload.updates
    if not updates_raw:
        raise HTTPException(status_code=400, detail="No field updates provided.")

    for field in updates_raw:
        if field in disallowed:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{field}' cannot be updated in bulk.",
            )
        if field not in schema["fields"]:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{field}' is not a valid field for {schema['label']}.",
            )

    for field in updates_raw:
        if field in unique_cols and len(ids) > 1 and updates_raw[field] is not None:
            field_label = schema["fields"][field]["label"]
            raise HTTPException(
                status_code=400,
                detail=f"Cannot bulk update unique field '{field_label}' with the same value across {len(ids)} records.",
            )

    coerced_updates = {}
    errors = []
    for field, raw_val in updates_raw.items():
        spec = schema["fields"][field]
        if spec.get("references") or field == "deployment_id":
            val, err = _resolve_foreign_key(raw_val, spec=spec, field_name=field, db=db)
        else:
            val, err = coerce_value(raw_val, spec["type"])
        if err:
            errors.append(f"{spec['label']}: {err}")
        else:
            coerced_updates[field] = val

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Invalid values for bulk update.", "errors": errors},
        )

    if len(ids) == 1:
        rec_id = ids[0]
        for col_name in unique_cols:
            val = coerced_updates.get(col_name)
            if val is not None:
                col = table.c[col_name]
                str_val = str(val).strip()
                condition = (
                    func.lower(cast(col, String)) == func.lower(str_val)
                    if isinstance(val, str)
                    else col == val
                )
                existing_dup = db.execute(
                    select(col).where(condition, pk_col != rec_id)
                ).scalar_one_or_none()
                if existing_dup is not None:
                    field_label = schema["fields"][col_name]["label"]
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": f"A record with {field_label} '{val}' already exists (matches existing '{existing_dup}').",
                            "errors": [
                                f"{col_name}: Value '{val}' already exists (case-insensitive duplicate of '{existing_dup}'). Please use a unique value."
                            ],
                        },
                    )

    if "password" in coerced_updates:
        if coerced_updates["password"]:
            coerced_updates["password"] = bcrypt.hashpw(
                coerced_updates["password"].encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
        else:
            coerced_updates.pop("password", None)

    try:
        stmt = table.update().where(pk_col.in_(ids)).values(**coerced_updates)
        res = db.execute(stmt)
        db.commit()
        affected = res.rowcount
    except IntegrityError as exc:
        db.rollback()
        message, errs = parse_integrity_error(exc)
        raise HTTPException(
            status_code=409,
            detail={"message": message, "errors": errs},
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Failed to apply bulk updates. Database error.",
        )

    return {
        "success": True,
        "entity_type": entity_type,
        "updated_count": affected,
        "total_requested": len(ids),
        "data": {
            "updated_count": affected,
            "total_requested": len(ids),
        },
        "message": f"Successfully updated {affected} {schema['label'].lower()} record(s).",
    }


@router.post("/inspect")
async def inspect_excel(file: UploadFile = File(...)):
    contents = await _contents(file)
    extension = _ensure_supported_file(file.filename)
    try:
        sheet_names = (
            ["CSV"]
            if extension == ".csv"
            else pd.ExcelFile(io.BytesIO(contents)).sheet_names
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="Unable to open this Excel workbook."
        ) from exc
    sheets = []
    # Header-only/empty sheets can still be listed, allowing selection of another sheet.
    for name in sheet_names:
        try:
            df = _read_uploaded_table(
                contents, file.filename, None if extension == ".csv" else name
            )
            columns = list(df.columns)
            sensitive_columns = {
                column
                for column in columns
                if column.lower().replace(" ", "_") in SENSITIVE_FIELDS
            }
            preview = [
                {
                    column: (
                        "••••••••"
                        if column in sensitive_columns
                        else "" if _is_empty(value) else str(value)
                    )
                    for column, value in row.items()
                }
                for row in df.head(5).to_dict("records")
            ]
            sheets.append(
                {
                    "sheet_name": name,
                    "row_count": len(df),
                    "columns": columns,
                    "preview": preview,
                }
            )
        except HTTPException as exc:
            if extension == ".csv":
                raise
            sheets.append(
                {
                    "sheet_name": name,
                    "row_count": 0,
                    "columns": [],
                    "preview": [],
                    "error": exc.detail,
                }
            )
    columns = {
        column.lower().replace(" ", "_")
        for column in (sheets[0]["columns"] if sheets else [])
    }
    def _score_schema(fields, table_name=None):
        score = len(columns & set(fields))
        for fk_field, aliases in FOREIGN_KEY_ALIASES.items():
            if fk_field in fields and any(c in columns for c in aliases):
                score += 1
        if table_name and table_name in FIELD_ALIASES:
            for canon_field, aliases in FIELD_ALIASES[table_name].items():
                if canon_field in fields and any(c in columns for c in aliases):
                    score += 1
        return score

    recommended = max(
        ENTITY_SCHEMAS,
        key=lambda name: _score_schema(ENTITY_SCHEMAS[name]["fields"], name),
    )
    return {
        "filename": file.filename,
        "sheets": sheets,
        "recommended_entity": recommended,
    }


@router.post("/validate")
async def validate_excel(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    entity_type: str = Form(...),
    mapping_json: str = Form(...),
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    df = _read_uploaded_table(await _contents(file), file.filename, sheet_name)
    mapping = _mapping(mapping_json, df, schema)
    rows = _validated_rows(df, mapping, schema, db=db)
    errors = sum(bool(row["errors"]) for row in rows)
    return {
        "entity_type": entity_type,
        "total_rows": len(rows),
        "valid_count": len(rows) - errors,
        "error_count": errors,
        "rows": [
            {
                "row_number": row["row_number"],
                "mapped_data": _public_data(row["data"]),
                "status": "error" if row["errors"] else "valid",
                "errors": row["errors"],
                "warnings": [],
            }
            for row in rows
        ],
    }


@router.post("/commit")
async def commit_excel_upload(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    entity_type: str = Form(...),
    mapping_json: str = Form(...),
    import_mode: str = Form("all_valid"),
    db: Session = Depends(database.get_db),
):
    schema = _get_schema(entity_type)
    if import_mode not in ("strict", "all_valid"):
        raise HTTPException(
            status_code=400, detail="Choose strict or all_valid import mode."
        )
    df = _read_uploaded_table(await _contents(file), file.filename, sheet_name)
    rows = _validated_rows(df, _mapping(mapping_json, df, schema), schema, db=db)
    if import_mode == "strict" and any(row["errors"] for row in rows):
        raise HTTPException(
            status_code=422,
            detail="No records imported. Fix validation errors before a strict import.",
        )
    inserted = 0
    failures = []
    try:
        # Starting with a write also establishes the outer transaction on SQLite,
        # where releasing a first savepoint could otherwise persist rows early.
        log = db.execute(
            models.UploadLog.__table__.insert().values(
                filename=file.filename,
                sheet_name=sheet_name,
                entity_type=entity_type,
                total_rows=len(rows),
                inserted_rows=0,
                failed_rows=0,
                status="IN_PROGRESS",
            )
        )
        log_id = log.inserted_primary_key[0]
        for row in rows:
            errors = row["errors"]
            if not errors:
                try:
                    # Savepoints let all_valid skip constraint failures without losing other rows.
                    with db.begin_nested():
                        _insert(db, schema, row["data"])
                    inserted += 1
                except IntegrityError as exc:
                    message, _ = parse_integrity_error(exc)
                    errors = [message]
            if errors:
                failures.append({"row": row["row_number"], "errors": errors})
                if import_mode == "strict":
                    db.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail=f"No records imported. Row {row['row_number']}: {' '.join(errors)}",
                    )
        result_status = (
            "SUCCESS" if not failures else "PARTIAL_SUCCESS" if inserted else "FAILED"
        )
        db.execute(
            models.UploadLog.__table__.update()
            .where(models.UploadLog.__table__.c.id == log_id)
            .values(
                inserted_rows=inserted,
                failed_rows=len(failures),
                status=result_status,
                error_details=failures or None,
            )
        )
        # Import and audit log succeed or roll back together.
        db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="No records imported. Check the database connection and migrations.",
        )
    return {
        "success": inserted > 0,
        "log_id": log_id,
        "entity_type": entity_type,
        "total_rows": len(rows),
        "inserted_rows": inserted,
        "failed_rows": len(failures),
        "status": result_status,
        "message": f"Imported {inserted} records; skipped {len(failures)} rows.",
        "error_details": failures,
    }


@router.get("/template/{entity_type}")
async def download_template(
    entity_type: str, format: str = Query("xlsx", pattern="^(csv|xlsx)$")
):
    schema = _get_schema(entity_type)
    canonical = schema["model"].__table__.name
    columns = [
        "opcode"
        if (
            col == "deployment_id"
            or schema["fields"].get(col, {}).get("references") == "deployments.id"
            or schema["fields"].get(col, {}).get("lookup_field") == "opcode"
        )
        else col
        for col in schema["fields"]
    ]
    df = pd.DataFrame(columns=columns)
    output = io.BytesIO()
    if format == "csv":
        output.write(df.to_csv(index=False).encode("utf-8-sig"))
        media_type = "text/csv; charset=utf-8"
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=schema["label"][:31], index=False)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    output.seek(0)
    return StreamingResponse(
        output,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{canonical}_bulk_template.{format}"'
        },
    )


@router.get("/history")
def get_upload_history(db: Session = Depends(database.get_db)):
    table = models.UploadLog.__table__
    return [
        dict(row)
        for row in db.execute(
            select(table)
            .order_by(table.c.created_at.desc(), table.c.id.desc())
            .limit(50)
        ).mappings()
    ]
