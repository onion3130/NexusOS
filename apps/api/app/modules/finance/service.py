"""Finance-domain services with ownership, idempotency, and audit boundaries."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession, selectinload

from app.db.base import utc_now
from app.db.models import FinanceAccount, FinanceCategory, FinanceTransaction, Job
from app.modules.finance.schemas import AccountCreate, AccountUpdate, CsvImportRequest, CsvImportRowError, FinanceCategoryCreate, TransactionCreate, TransactionUpdate
from app.modules.identity.service import add_audit_event

REQUIRED_CSV_HEADERS = ("date", "description", "amount")


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _mutation_key(user_id: str, operation: str, key: str) -> str:
    return hashlib.sha256(f"{user_id}:{operation}:{key}".encode("utf-8")).hexdigest()


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _prior_mutation(db: OrmSession, user_id: str, operation: str, key: str | None, payload: object | None = None) -> tuple[str, str] | None:
    if not key:
        return None
    job = db.scalar(select(Job).where(Job.idempotency_key == _mutation_key(user_id, operation, key)))
    if not job or not job.payload_json:
        return None
    stored = json.loads(job.payload_json)
    stored_fingerprint = str(stored.get("fingerprint", ""))
    if payload is not None and stored_fingerprint and stored_fingerprint != _fingerprint(payload):
        raise ValueError("Idempotency-Key was already used for a different operation")
    return str(stored.get("resource_id")), stored_fingerprint


def _record_mutation(db: OrmSession, user_id: str, operation: str, key: str | None, resource_id: str, payload: object | None = None) -> None:
    if key:
        db.add(Job(job_type="mutation", status="completed", available_at=utc_now(), idempotency_key=_mutation_key(user_id, operation, key), payload_json=json.dumps({"resource_id": resource_id, "fingerprint": _fingerprint(payload) if payload is not None else ""}, separators=(",", ":")), completed_at=utc_now()))


def _category(db: OrmSession, user_id: str, name: str | None, color: str | None = None) -> FinanceCategory | None:
    if not name:
        return None
    normalized = name.casefold()
    category = db.scalar(select(FinanceCategory).where(FinanceCategory.user_id == user_id, FinanceCategory.normalized_name == normalized))
    if category is None:
        category = FinanceCategory(user_id=user_id, name=name, normalized_name=normalized, color=color)
        db.add(category)
        db.flush()
    return category


def _account(db: OrmSession, user_id: str, account_id: str) -> FinanceAccount | None:
    return db.scalar(select(FinanceAccount).where(FinanceAccount.id == account_id, FinanceAccount.user_id == user_id, FinanceAccount.deleted_at.is_(None)))


def _transaction(db: OrmSession, user_id: str, transaction_id: str) -> FinanceTransaction | None:
    return db.scalar(
        select(FinanceTransaction)
        .where(FinanceTransaction.id == transaction_id, FinanceTransaction.user_id == user_id, FinanceTransaction.deleted_at.is_(None))
        .options(selectinload(FinanceTransaction.category))
    )


def _balance_cents(db: OrmSession, user_id: str, account_id: str) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(FinanceTransaction.amount_cents), 0)).where(
            FinanceTransaction.user_id == user_id, FinanceTransaction.account_id == account_id, FinanceTransaction.deleted_at.is_(None)
        )
    )
    return int(total or 0)


def list_accounts(db: OrmSession, user_id: str) -> list[FinanceAccount]:
    return list(db.scalars(select(FinanceAccount).where(FinanceAccount.user_id == user_id, FinanceAccount.deleted_at.is_(None)).order_by(FinanceAccount.name)))


def create_account(db: OrmSession, user_id: str, payload: AccountCreate, idempotency_key: str | None = None) -> FinanceAccount:
    prior = _prior_mutation(db, user_id, "account-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = _account(db, user_id, prior[0])
        if existing:
            return existing
    account = FinanceAccount(user_id=user_id, name=payload.name, account_type=payload.account_type, color=payload.color)
    db.add(account)
    db.flush()
    _record_mutation(db, user_id, "account-create", idempotency_key, account.id, payload.model_dump(mode="json"))
    add_audit_event(db, action="finance.account_create", result="success", actor_user_id=user_id, target=account.id, metadata={"name": account.name})
    db.commit()
    return account


def update_account(db: OrmSession, user_id: str, account_id: str, payload: AccountUpdate, idempotency_key: str | None = None) -> FinanceAccount | None:
    mutation_payload = {"account_id": account_id, "changes": payload.model_dump(mode="json", exclude_unset=True)}
    prior = _prior_mutation(db, user_id, "account-update", idempotency_key, mutation_payload)
    if prior:
        return _account(db, user_id, prior[0])
    account = _account(db, user_id, account_id)
    if account is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(account, key, value)
    _record_mutation(db, user_id, "account-update", idempotency_key, account.id, mutation_payload)
    add_audit_event(db, action="finance.account_update", result="success", actor_user_id=user_id, target=account.id, metadata={"fields": sorted(values)})
    db.commit()
    return account


def delete_account(db: OrmSession, user_id: str, account_id: str, idempotency_key: str | None = None) -> FinanceAccount | None:
    prior = _prior_mutation(db, user_id, "account-delete", idempotency_key, {"account_id": account_id})
    if prior:
        return db.scalar(select(FinanceAccount).where(FinanceAccount.id == prior[0], FinanceAccount.user_id == user_id))
    account = _account(db, user_id, account_id)
    if account is None:
        return None
    account.deleted_at = utc_now()
    _record_mutation(db, user_id, "account-delete", idempotency_key, account.id, {"account_id": account_id})
    add_audit_event(db, action="finance.account_delete", result="success", actor_user_id=user_id, target=account.id)
    db.commit()
    return account


def list_categories(db: OrmSession, user_id: str) -> list[FinanceCategory]:
    return list(db.scalars(select(FinanceCategory).where(FinanceCategory.user_id == user_id).order_by(FinanceCategory.name)))


def create_category(db: OrmSession, user_id: str, payload: FinanceCategoryCreate, idempotency_key: str | None = None) -> FinanceCategory:
    prior = _prior_mutation(db, user_id, "finance-category-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = db.get(FinanceCategory, prior[0])
        if existing is not None:
            return existing
    category = _category(db, user_id, payload.name, payload.color)
    if category is None:
        raise ValueError("category name is required")
    _record_mutation(db, user_id, "finance-category-create", idempotency_key, category.id, payload.model_dump(mode="json"))
    db.commit()
    return category


def delete_category(db: OrmSession, user_id: str, category_id: str, idempotency_key: str | None = None) -> bool:
    prior = _prior_mutation(db, user_id, "finance-category-delete", idempotency_key, {"category_id": category_id})
    if prior:
        return True
    category = db.scalar(select(FinanceCategory).where(FinanceCategory.id == category_id, FinanceCategory.user_id == user_id))
    if category is None:
        return False
    db.delete(category)
    _record_mutation(db, user_id, "finance-category-delete", idempotency_key, category_id, {"category_id": category_id})
    add_audit_event(db, action="finance.category_delete", result="success", actor_user_id=user_id, target=category_id)
    db.commit()
    return True


def list_transactions(db: OrmSession, user_id: str, *, account_id: str | None = None, category: str | None = None, occurred_from: datetime | None = None, occurred_to: datetime | None = None, limit: int = 100, cursor: str | None = None) -> list[FinanceTransaction]:
    statement = select(FinanceTransaction).where(FinanceTransaction.user_id == user_id, FinanceTransaction.deleted_at.is_(None)).options(selectinload(FinanceTransaction.category))
    if account_id:
        statement = statement.where(FinanceTransaction.account_id == account_id)
    if category:
        statement = statement.join(FinanceCategory).where(FinanceCategory.user_id == user_id, FinanceCategory.normalized_name == category.casefold())
    if occurred_from is not None:
        statement = statement.where(FinanceTransaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        statement = statement.where(FinanceTransaction.occurred_at <= occurred_to)
    if cursor:
        statement = statement.where(FinanceTransaction.id < cursor)
    return list(db.scalars(statement.order_by(FinanceTransaction.occurred_at, FinanceTransaction.id).limit(max(1, min(limit, 200)))))


def create_transaction(db: OrmSession, user_id: str, payload: TransactionCreate, idempotency_key: str | None = None) -> FinanceTransaction:
    prior = _prior_mutation(db, user_id, "transaction-create", idempotency_key, payload.model_dump(mode="json"))
    if prior:
        existing = _transaction(db, user_id, prior[0])
        if existing:
            return existing
    account = _account(db, user_id, payload.account_id)
    if account is None:
        raise ValueError("account not found")
    category = _category(db, user_id, payload.category)
    transaction = FinanceTransaction(
        user_id=user_id,
        account_id=account.id,
        category_id=category.id if category else None,
        amount_cents=payload.amount_cents,
        description=payload.description,
        note=payload.note,
        occurred_at=_aware(payload.occurred_at or utc_now()),
    )
    db.add(transaction)
    db.flush()
    _record_mutation(db, user_id, "transaction-create", idempotency_key, transaction.id, payload.model_dump(mode="json"))
    add_audit_event(db, action="finance.transaction_create", result="success", actor_user_id=user_id, target=transaction.id, metadata={"amount_cents": transaction.amount_cents, "account_id": account.id})
    db.commit()
    return _transaction(db, user_id, transaction.id)  # type: ignore[return-value]


def update_transaction(db: OrmSession, user_id: str, transaction_id: str, payload: TransactionUpdate, idempotency_key: str | None = None) -> FinanceTransaction | None:
    mutation_payload = {"transaction_id": transaction_id, "changes": payload.model_dump(mode="json", exclude_unset=True)}
    prior = _prior_mutation(db, user_id, "transaction-update", idempotency_key, mutation_payload)
    if prior:
        return _transaction(db, user_id, prior[0])
    transaction = _transaction(db, user_id, transaction_id)
    if transaction is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    category_name = values.pop("category", None)
    if "account_id" in values:
        account = _account(db, user_id, str(values["account_id"]))
        if account is None:
            raise ValueError("account not found")
    for key, value in values.items():
        if key == "occurred_at" and value is not None:
            value = _aware(value)
        setattr(transaction, key, value)
    if category_name is not None:
        category = _category(db, user_id, category_name)
        transaction.category_id = category.id if category else None
    _record_mutation(db, user_id, "transaction-update", idempotency_key, transaction.id, mutation_payload)
    add_audit_event(db, action="finance.transaction_update", result="success", actor_user_id=user_id, target=transaction.id, metadata={"fields": sorted(values)})
    db.commit()
    return _transaction(db, user_id, transaction.id)


def delete_transaction(db: OrmSession, user_id: str, transaction_id: str, idempotency_key: str | None = None) -> FinanceTransaction | None:
    prior = _prior_mutation(db, user_id, "transaction-delete", idempotency_key, {"transaction_id": transaction_id})
    if prior:
        return db.scalar(select(FinanceTransaction).where(FinanceTransaction.id == prior[0], FinanceTransaction.user_id == user_id))
    transaction = _transaction(db, user_id, transaction_id)
    if transaction is None:
        return None
    transaction.deleted_at = utc_now()
    _record_mutation(db, user_id, "transaction-delete", idempotency_key, transaction.id, {"transaction_id": transaction_id})
    add_audit_event(db, action="finance.transaction_delete", result="success", actor_user_id=user_id, target=transaction.id)
    db.commit()
    return transaction


def transaction_summary(db: OrmSession, user_id: str, *, occurred_from: datetime | None = None, occurred_to: datetime | None = None) -> dict[str, int]:
    """Bounded period totals: income (positive) and expense (negative) sums in cents."""
    statement = select(FinanceTransaction).where(FinanceTransaction.user_id == user_id, FinanceTransaction.deleted_at.is_(None))
    if occurred_from is not None:
        statement = statement.where(FinanceTransaction.occurred_at >= occurred_from)
    if occurred_to is not None:
        statement = statement.where(FinanceTransaction.occurred_at <= occurred_to)
    transactions = list(db.scalars(statement))
    income = sum(item.amount_cents for item in transactions if item.amount_cents > 0)
    expense = sum(item.amount_cents for item in transactions if item.amount_cents < 0)
    return {
        "total_income_cents": income,
        "total_expense_cents": abs(expense),
        "net_cents": income + expense,
        "count": len(transactions),
    }


def import_csv(db: OrmSession, user_id: str, payload: CsvImportRequest) -> dict[str, object]:
    """Strict all-or-nothing CSV import: validate every row before writing any."""
    account = _account(db, user_id, payload.account_id)
    if account is None:
        raise ValueError("account not found")
    reader = csv.reader(io.StringIO(payload.csv))
    try:
        headers = [header.strip().casefold() for header in next(reader)]
    except StopIteration as exc:
        raise ValueError("CSV is empty") from exc
    if not all(required in headers for required in REQUIRED_CSV_HEADERS):
        raise ValueError(f"CSV must include columns: {', '.join(REQUIRED_CSV_HEADERS)}")
    index = {header: position for position, header in enumerate(headers)}
    rows: list[dict[str, object]] = []
    errors: list[CsvImportRowError] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue
        try:
            if len(raw_row) < len(REQUIRED_CSV_HEADERS):
                raise ValueError("too few columns")
            date_value = raw_row[index["date"]].strip()
            occurred_at = _parse_date(date_value)
            amount = _parse_amount(raw_row[index["amount"]].strip())
            description = raw_row[index["description"]].strip()
            if not description:
                raise ValueError("description is required")
            category = raw_row[index["category"]].strip() if "category" in index and len(raw_row) > index["category"] else ""
            rows.append({"occurred_at": occurred_at, "amount_cents": amount, "description": description[:255], "category": category[:64] or None})
        except ValueError as exc:
            errors.append(CsvImportRowError(row=row_number, error=str(exc)))
    if errors:
        return {"imported": 0, "errors": errors}
    for row in rows:
        category = _category(db, user_id, str(row["category"])) if row.get("category") else None
        db.add(
            FinanceTransaction(
                user_id=user_id,
                account_id=account.id,
                category_id=category.id if category else None,
                amount_cents=int(row["amount_cents"]),
                description=str(row["description"]),
                occurred_at=row["occurred_at"],  # type: ignore[arg-type]
            )
        )
    add_audit_event(db, action="finance.csv_import", result="success", actor_user_id=user_id, target=account.id, metadata={"rows": len(rows)})
    db.commit()
    return {"imported": len(rows), "errors": []}


def _parse_date(value: str) -> datetime:
    """Accept ISO-8601 or YYYY-MM-DD, refusing naive ambiguity by assuming UTC."""
    value = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}") from exc
    return _aware(parsed)


def _parse_amount(value: str) -> int:
    """Parse decimal money into integer cents, bounding precision to 2 decimals."""
    cleaned = value.replace(",", "").replace("$", "").strip()
    if not cleaned:
        raise ValueError("amount is required")
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"invalid amount {value!r}") from exc
    cents = round(parsed * 100)
    if abs(cents) > 9_999_999_999:
        raise ValueError("amount out of bounds")
    return int(cents)
