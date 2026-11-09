"""Read-only table catalog and paginated records for the React browser."""

import io
from typing import List, Optional
import pandas as pd
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Boolean, MetaData, Table, String, Text, cast, func, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from db import database, models
from db.schemas.response import parse_integrity_error

router = APIRouter(prefix="/tables", tags=["table-browser"])

# Limit browsing to application tables, excluding internal database tables.
TABLES = {getattr(models, name).__table__.name for name in models.__all__}

# Canonical order matching data collection lifecycle and relational dependencies
TABLE_ORDER = [
    # 1. BRUV Survey Pipeline (Data collection order & foreign key dependencies)
    "projects",          # Level 1: High-level research project container
    "fieldtrips",        # Level 2: Field expedition under project (project_id)
    "day_sheets",        # Level 3: Daily field logs & sea conditions per trip (fieldtrip_id)
    "calibrations",      # Level 3: Stereo camera calibration per trip (fieldtrip_id)
    "deployments",       # Level 3: Rig drop operations per trip (fieldtrip_id), uses calibration
    "analysis_periods",  # Level 4: Video analysis timeframes per deployment (deployment_id)
    "observations",      # Level 4: Species biodiversity counts & MaxN per deployment (deployment_id)
    "measurements",      # Level 4: 3D stereo fish measurements per deployment (deployment_id)
    # 2. Access Control, System & Telemetry Tables
    "roles",
    "users",
    "user_roles",
    "agents",
    "people",
    "upload_logs",
]


def table_sort_key(name: str):
    """Sort key placing survey tables in collection/dependency order, followed by system tables."""
    try:
        return (TABLE_ORDER.index(name), name)
    except ValueError:
        return (len(TABLE_ORDER), name)


LABELS = {"fieldtrips": "Field trips"}
HIDDEN_COLUMNS = {"password", "password_hash", "hashed_password"}
TABLE_HIDDEN_COLUMNS = {"projects": {"name"}}


def label(name: str) -> str:
    return LABELS.get(name, name.replace("_", " ").capitalize())


def col_label(c_name: str, is_fk: bool) -> str:
    if is_fk and c_name.endswith("_id"):
        base = c_name[:-3]
        return LABELS.get(base, base.replace("_", " ").capitalize())
    if c_name == "id":
        return "ID"
    return label(c_name)


def format_entity_label(table_name: str, row: dict) -> str:
    """Produce a concise, human-readable identifier for a record."""
    if not row:
        return ""
    rec_id = row.get("id")

    # Projects
    p_code = row.get("project_code")
    p_name = row.get("project_name")
    if p_code or p_name:
        parts = [str(x).strip() for x in (p_code, p_name) if x]
        return " · ".join(parts)

    # Field trips
    t_code = row.get("fieldtrip_code") or row.get("trip_code")
    t_name = row.get("trip_name") or row.get("fieldtrip_lead") or row.get("location")
    if t_code or t_name:
        parts = [str(x).strip() for x in (t_code, t_name) if x]
        return " · ".join(parts)

    # Deployments
    opcode = row.get("opcode")
    site = row.get("site_name")
    if opcode or site:
        parts = [str(x).strip() for x in (opcode, site) if x]
        return " · ".join(parts)

    # Observations
    species = row.get("species_name")
    common = row.get("common_name")
    if species or common:
        if species and common:
            return f"{species} ({common})"
        return str(species or common)

    # Users
    full_name = row.get("full_name")
    email = row.get("email")
    username = row.get("username")
    if full_name:
        return f"{full_name} ({email})" if email else str(full_name)
    if username and email:
        return f"{username} ({email})"
    if email or username:
        return str(email or username)

    # People / Persons
    first = row.get("firstname") or row.get("first_name")
    last = row.get("lastname") or row.get("last_name")
    if first or last:
        name_parts = [str(x).strip() for x in (first, last) if x]
        return " ".join(name_parts)

    # Roles / generic name
    if row.get("name"):
        return str(row["name"]).strip()

    # Generic string scan (excluding password / timestamps)
    for k, v in row.items():
        if (
            k not in ("id", "created_at", "updated_at", "password", "hashed_password", "password_hash")
            and not k.endswith("_id")
            and isinstance(v, str)
            and v.strip()
        ):
            return v.strip()

    return f"#{rec_id}" if rec_id is not None else ""


@router.get("/")
def list_tables(db: Session = Depends(database.get_db)):
    tables = []
    for name in sorted(TABLES, key=table_sort_key):
        try:
            # Use a Core table so unrelated ORM relationship errors cannot stop counts.
            table = database.Base.metadata.tables[name]
            count = db.execute(select(func.count()).select_from(table)).scalar_one()
            tables.append({"name": name, "label": label(name), "count": count})
        except SQLAlchemyError:
            db.rollback()
            tables.append({"name": name, "label": label(name), "count": None,
                           "error": "Unable to load record count"})
    return {"tables": tables}


def _build_table_schema_dict(db: Session, table_name: str, all_fks: dict = None) -> dict:
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    inspector = inspect(db.connection())
    hidden_columns = HIDDEN_COLUMNS | TABLE_HIDDEN_COLUMNS.get(table_name, set())
    raw_columns = inspector.get_columns(table_name)
    pk_constraint = inspector.get_pk_constraint(table_name)
    pk_cols = set(pk_constraint.get("constrained_columns") or [])

    fks = inspector.get_foreign_keys(table_name)
    fk_by_col = {}
    for fk in fks:
        if fk.get("constrained_columns") and fk.get("referred_table"):
            col_name = fk["constrained_columns"][0]
            fk_by_col[col_name] = {
                "target_table": fk["referred_table"],
                "target_label": label(fk["referred_table"]),
                "target_column": fk["referred_columns"][0] if fk.get("referred_columns") else "id",
                "constraint_name": fk.get("name"),
            }

    columns = []
    for col in raw_columns:
        c_name = col["name"]
        if c_name in hidden_columns:
            continue
        fk_info = fk_by_col.get(c_name)
        columns.append({
            "name": c_name,
            "label": col_label(c_name, bool(fk_info)),
            "type": str(col["type"]),
            "nullable": bool(col.get("nullable", True)),
            "default": str(col["default"]) if col.get("default") is not None else None,
            "is_primary_key": c_name in pk_cols,
            "is_foreign_key": bool(fk_info),
            "foreign_key": fk_info,
        })

    # Incoming relationships (tables referencing this table)
    incoming = []
    if all_fks is not None:
        for other_tbl, other_fk_list in all_fks.items():
            if other_tbl == table_name:
                continue
            for fk in other_fk_list:
                if fk.get("referred_table") == table_name:
                    src_col = fk["constrained_columns"][0] if fk.get("constrained_columns") else ""
                    tgt_col = fk["referred_columns"][0] if fk.get("referred_columns") else "id"
                    incoming.append({
                        "source_table": other_tbl,
                        "source_label": label(other_tbl),
                        "source_column": src_col,
                        "target_column": tgt_col,
                        "constraint_name": fk.get("name"),
                    })

    unique_constraints = inspector.get_unique_constraints(table_name)
    indexes = inspector.get_indexes(table_name)

    try:
        table_core = database.Base.metadata.tables.get(table_name)
        if table_core is None:
            table_core = Table(table_name, MetaData(), autoload_with=db.connection())
        row_count = db.execute(select(func.count()).select_from(table_core)).scalar_one()
    except Exception:
        row_count = None

    return {
        "name": table_name,
        "label": label(table_name),
        "row_count": row_count,
        "columns": columns,
        "primary_keys": list(pk_cols),
        "foreign_keys": list(fk_by_col.values()),
        "outgoing_relationships": [
            {
                "column": col["name"],
                "target_table": col["foreign_key"]["target_table"],
                "target_label": col["foreign_key"]["target_label"],
                "target_column": col["foreign_key"]["target_column"],
            }
            for col in columns
            if col["is_foreign_key"]
        ],
        "incoming_relationships": incoming,
        "unique_constraints": [
            {"name": uq.get("name"), "columns": uq.get("column_names", [])}
            for uq in unique_constraints
            if uq.get("column_names")
        ],
        "indexes": [
            {"name": idx.get("name"), "columns": idx.get("column_names", []), "unique": idx.get("unique", False)}
            for idx in indexes
            if idx.get("column_names")
        ],
    }


@router.get("/schema")
def get_database_schema(db: Session = Depends(database.get_db)):
    """Return the complete database schema with tables, columns, constraints, and relationship graph."""
    inspector = inspect(db.connection())
    all_fks = {}
    for tbl in TABLES:
        try:
            all_fks[tbl] = inspector.get_foreign_keys(tbl)
        except Exception:
            all_fks[tbl] = []

    tables_schema = []
    edges = []
    total_columns = 0
    total_records = 0

    for tbl in sorted(TABLES, key=table_sort_key):
        try:
            tbl_info = _build_table_schema_dict(db, tbl, all_fks=all_fks)
            tables_schema.append(tbl_info)
            total_columns += len(tbl_info["columns"])
            if tbl_info["row_count"] is not None:
                total_records += tbl_info["row_count"]

            for rel in tbl_info["outgoing_relationships"]:
                edges.append({
                    "id": f"{tbl}.{rel['column']}->{rel['target_table']}.{rel['target_column']}",
                    "source": tbl,
                    "source_label": tbl_info["label"],
                    "source_column": rel["column"],
                    "target": rel["target_table"],
                    "target_label": rel["target_label"],
                    "target_column": rel["target_column"],
                })
        except Exception:
            db.rollback()

    return {
        "tables": tables_schema,
        "edges": edges,
        "summary": {
            "total_tables": len(tables_schema),
            "total_columns": total_columns,
            "total_relationships": len(edges),
            "total_records": total_records,
        },
    }


@router.get("/{table_name}/schema")
def get_single_table_schema(table_name: str, db: Session = Depends(database.get_db)):
    """Return the schema metadata for a single database table."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    inspector = inspect(db.connection())
    all_fks = {}
    for tbl in TABLES:
        try:
            all_fks[tbl] = inspector.get_foreign_keys(tbl)
        except Exception:
            all_fks[tbl] = []
    return _build_table_schema_dict(db, table_name, all_fks=all_fks)


@router.get("/{table_name}")
def get_records(
    table_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=200),
    db: Session = Depends(database.get_db),
):
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    try:
        # Reflect the actual columns to support databases with older migrations.
        table = Table(table_name, MetaData(), autoload_with=db.connection())
        hidden_columns = HIDDEN_COLUMNS | TABLE_HIDDEN_COLUMNS.get(table_name, set())
        columns = [column for column in table.columns if column.name not in hidden_columns]

        # Identify foreign keys
        fk_map = {}  # col_name -> (target_table_name, target_pk_name)
        for column in columns:
            if column.foreign_keys:
                fk = next(iter(column.foreign_keys))
                fk_map[column.name] = (fk.column.table.name, fk.column.name)

        statement = select(*columns)
        count_statement = select(func.count()).select_from(table)
        if search.strip():
            term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term_lower = search.strip().lower()
            text_columns = [
                column for column in columns
                if isinstance(column.type, (String, Text)) or column.primary_key
            ]
            conditions = [cast(column, String).ilike(f"%{term}%", escape="\\")
                          for column in text_columns]
            bool_columns = [column for column in columns if isinstance(column.type, Boolean)]
            if term_lower in ("yes", "y", "true", "t", "1"):
                conditions.extend([col == True for col in bool_columns])
            elif term_lower in ("no", "n", "false", "f", "0", "2"):
                conditions.extend([col == False for col in bool_columns])
            if conditions:
                condition = or_(*conditions)
                statement = statement.where(condition)
                count_statement = count_statement.where(condition)
        order = list(table.primary_key.columns) or columns
        total = db.execute(count_statement).scalar_one()
        rows = db.execute(statement.order_by(*order).offset(skip).limit(limit)).mappings().all()

        # Batch resolve display names for foreign keys present in these rows
        resolved_fk_labels = {col_name: {} for col_name in fk_map}
        for col_name, (target_tbl, target_pk) in fk_map.items():
            needed_ids = {r[col_name] for r in rows if r.get(col_name) is not None}
            if needed_ids:
                target_meta_table = database.Base.metadata.tables.get(target_tbl)
                if target_meta_table is None:
                    try:
                        target_meta_table = Table(target_tbl, MetaData(), autoload_with=db.connection())
                    except Exception:
                        target_meta_table = None
                if target_meta_table is not None:
                    target_rows = db.execute(
                        select(target_meta_table).where(target_meta_table.c[target_pk].in_(needed_ids))
                    ).mappings().all()
                    for tr in target_rows:
                        resolved_fk_labels[col_name][tr[target_pk]] = format_entity_label(target_tbl, dict(tr))

        items = []
        for r in rows:
            row_dict = dict(r)
            display_names = {}
            for col_name in fk_map:
                val = row_dict.get(col_name)
                if val is not None and val in resolved_fk_labels[col_name]:
                    display_names[col_name] = resolved_fk_labels[col_name][val]
            row_dict["_display_names"] = display_names
            row_dict["_record_label"] = format_entity_label(table_name, row_dict)
            items.append(row_dict)

        return {
            "name": table_name,
            "label": label(table_name),
            "total": total,
            "columns": [
                {
                    "name": column.name,
                    "label": col_label(column.name, column.name in fk_map),
                    "is_foreign_key": column.name in fk_map,
                    "is_primary_key": column.primary_key,
                    "target_table": fk_map[column.name][0] if column.name in fk_map else None,
                }
                for column in columns
            ],
            "items": items,
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to read this table. Check the database connection and migrations.")


class TableDownloadRequest(BaseModel):
    ids: Optional[List[int]] = None
    format: str = "csv"
    search: Optional[str] = ""


def _generate_table_download(
    table_name: str,
    format: str,
    search: str,
    selected_ids: Optional[List[int]],
    db: Session,
):
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    format_clean = (format or "csv").lower().strip()
    if format_clean not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats are 'csv' and 'xlsx'.")

    try:
        try:
            table = Table(table_name, MetaData(), autoload_with=db.connection())
        except Exception:
            table = database.Base.metadata.tables.get(table_name)
        if table is None:
            raise HTTPException(status_code=404, detail="Table metadata not found")

        hidden_columns = HIDDEN_COLUMNS | TABLE_HIDDEN_COLUMNS.get(table_name, set())
        columns = [column for column in table.columns if column.name not in hidden_columns]

        statement = select(*columns)

        if selected_ids is not None:
            pk_cols = list(table.primary_key.columns)
            if pk_cols:
                pk_col = pk_cols[0]
                statement = statement.where(pk_col.in_(selected_ids))
            elif "id" in table.columns:
                statement = statement.where(table.columns["id"].in_(selected_ids))

        if search and search.strip():
            term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term_lower = search.strip().lower()
            text_columns = [
                column for column in columns
                if isinstance(column.type, (String, Text)) or column.primary_key
            ]
            conditions = [cast(column, String).ilike(f"%{term}%", escape="\\")
                          for column in text_columns]
            bool_columns = [column for column in columns if isinstance(column.type, Boolean)]
            if term_lower in ("yes", "y", "true", "t", "1"):
                conditions.extend([col == True for col in bool_columns])
            elif term_lower in ("no", "n", "false", "f", "0", "2"):
                conditions.extend([col == False for col in bool_columns])
            if conditions:
                statement = statement.where(or_(*conditions))

        order = list(table.primary_key.columns) or columns
        rows = [dict(r) for r in db.execute(statement.order_by(*order)).mappings().all()]

        df = pd.DataFrame(rows, columns=[c.name for c in columns])

        output = io.BytesIO()
        if format_clean == "csv":
            output.write(df.to_csv(index=False).encode("utf-8-sig"))
            media_type = "text/csv; charset=utf-8"
        else:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=label(table_name)[:31], index=False)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        output.seek(0)

        filename_prefix = f"{table_name}_selected" if (selected_ids is not None and len(selected_ids) > 0) else f"{table_name}"
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename_prefix}_records.{format_clean}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to read this table. Check the database connection and migrations.")


@router.get("/{table_name}/download")
@router.get("/{table_name}/export")
def download_table_records(
    table_name: str,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    search: str = Query("", max_length=200),
    ids: Optional[List[str]] = Query(None),
    db: Session = Depends(database.get_db),
):
    selected_ids = None
    if ids is not None:
        selected_ids = []
        for item in ids:
            for part in str(item).split(","):
                part_clean = part.strip()
                if part_clean:
                    try:
                        selected_ids.append(int(part_clean))
                    except ValueError:
                        raise HTTPException(status_code=400, detail=f"Invalid record ID '{part_clean}'. IDs must be integers.")
        selected_ids = list(dict.fromkeys(selected_ids))

    return _generate_table_download(
        table_name=table_name,
        format=format,
        search=search,
        selected_ids=selected_ids,
        db=db,
    )


@router.post("/{table_name}/download")
@router.post("/{table_name}/export")
def download_table_records_post(
    table_name: str,
    payload: TableDownloadRequest,
    db: Session = Depends(database.get_db),
):
    selected_ids = None
    if payload.ids is not None:
        selected_ids = list(dict.fromkeys(payload.ids))
    return _generate_table_download(
        table_name=table_name,
        format=payload.format,
        search=payload.search or "",
        selected_ids=selected_ids,
        db=db,
    )


class TableBulkDeleteRequest(BaseModel):
    ids: List[int]


@router.delete("/{table_name}/{record_id}")
@router.post("/{table_name}/{record_id}/delete")
def delete_table_record(
    table_name: str,
    record_id: int,
    db: Session = Depends(database.get_db),
):
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    table = database.Base.metadata.tables.get(table_name)
    if table is None:
        try:
            table = Table(table_name, MetaData(), autoload_with=db.connection())
        except Exception:
            raise HTTPException(status_code=404, detail="Table metadata not found")

    pk_cols = list(table.primary_key.columns)
    if not pk_cols:
        raise HTTPException(status_code=400, detail="Table does not have a primary key")
    pk_col = pk_cols[0]

    existing = db.execute(select(table).where(pk_col == record_id)).mappings().first()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"{label(table_name)} record with ID {record_id} not found.",
        )

    try:
        db.execute(table.delete().where(pk_col == record_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message, errors = parse_integrity_error(exc)
        raise HTTPException(status_code=409, detail={"message": message, "errors": errors})
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to delete record from table.")

    return {
        "success": True,
        "id": record_id,
        "table_name": table_name,
        "message": f"{label(table_name)} record #{record_id} deleted successfully.",
    }


@router.delete("/{table_name}/bulk")
@router.post("/{table_name}/delete-bulk")
def delete_table_records_bulk(
    table_name: str,
    payload: TableBulkDeleteRequest,
    db: Session = Depends(database.get_db),
):
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail="Unknown application table")
    table = database.Base.metadata.tables.get(table_name)
    if table is None:
        try:
            table = Table(table_name, MetaData(), autoload_with=db.connection())
        except Exception:
            raise HTTPException(status_code=404, detail="Table metadata not found")

    pk_cols = list(table.primary_key.columns)
    if not pk_cols:
        raise HTTPException(status_code=400, detail="Table does not have a primary key")
    pk_col = pk_cols[0]

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
        raise HTTPException(status_code=409, detail={"message": message, "errors": errors})
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to delete records from table.")

    return {
        "success": True,
        "table_name": table_name,
        "deleted_count": deleted_count,
        "data": {"deleted_count": deleted_count, "ids": ids},
        "message": f"Successfully deleted {deleted_count} {label(table_name).lower()} record(s).",
    }
