"""Authenticated finance routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.db.models import FinanceAccount, FinanceCategory, FinanceTransaction
from app.db.session import get_db
from app.modules.finance.schemas import AccountCreate, AccountResponse, AccountUpdate, CsvImportRequest, CsvImportResponse, FinanceCategoryCreate, FinanceCategoryResponse, TransactionCreate, TransactionListResponse, TransactionResponse, TransactionSummary, TransactionUpdate
from app.modules.finance.service import create_account, create_category, create_transaction, delete_account, delete_category, delete_transaction, import_csv, list_accounts, list_categories, list_transactions, transaction_summary, update_account, update_transaction
from app.modules.identity.dependencies import AuthContext, get_auth_context, require_csrf, require_permission

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


def _account_response(account: FinanceAccount, balance_cents: int) -> AccountResponse:
    return AccountResponse(id=account.id, name=account.name, account_type=account.account_type, color=account.color, balance_cents=balance_cents, created_at=account.created_at, updated_at=account.updated_at)


def _category_response(item: FinanceCategory) -> FinanceCategoryResponse:
    return FinanceCategoryResponse(id=item.id, name=item.name, color=item.color)


def _transaction_response(item: FinanceTransaction) -> TransactionResponse:
    return TransactionResponse(id=item.id, account_id=item.account_id, amount_cents=item.amount_cents, description=item.description, note=item.note, category=_category_response(item.category) if item.category else None, occurred_at=item.occurred_at, created_at=item.created_at, updated_at=item.updated_at)


def _parse_datetime(value: str | None, name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{name} must be an ISO-8601 timestamp") from exc
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/accounts", response_model=list[AccountResponse])
def accounts(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[AccountResponse]:
    require_permission("finance.read", context)
    from app.modules.finance.service import _balance_cents

    return [_account_response(item, _balance_cents(db, context.user.id, item.id)) for item in list_accounts(db, context.user.id)]


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def account_create(payload: AccountCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> AccountResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        account = create_account(db, context.user.id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise _as_error(exc) from exc
    return _account_response(account, 0)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
def account_update(account_id: str, payload: AccountUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> AccountResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        account = update_account(db, context.user.id, account_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise _as_error(exc) from exc
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    from app.modules.finance.service import _balance_cents

    return _account_response(account, _balance_cents(db, context.user.id, account.id))


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def account_delete(account_id: str, request: Request, response: Response, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("finance.write", context)
    if delete_account(db, context.user.id, account_id, request.headers.get("Idempotency-Key")) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


@router.get("/categories", response_model=list[FinanceCategoryResponse])
def categories(db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> list[FinanceCategoryResponse]:
    require_permission("finance.read", context)
    return [_category_response(item) for item in list_categories(db, context.user.id)]


@router.post("/categories", response_model=FinanceCategoryResponse, status_code=status.HTTP_201_CREATED)
def category_create(payload: FinanceCategoryCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> FinanceCategoryResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        return _category_response(create_category(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise _as_error(exc) from exc


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def category_delete(category_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("finance.write", context)
    if not delete_category(db, context.user.id, category_id, request.headers.get("Idempotency-Key")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


@router.get("/transactions", response_model=TransactionListResponse)
def transactions(account_id: str | None = None, category: str | None = None, occurred_from: str | None = None, occurred_to: str | None = None, limit: int = 100, cursor: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TransactionListResponse:
    require_permission("finance.read", context)
    items = list_transactions(db, context.user.id, account_id=account_id, category=category, occurred_from=_parse_datetime(occurred_from, "occurred_from"), occurred_to=_parse_datetime(occurred_to, "occurred_to"), limit=limit, cursor=cursor)
    return TransactionListResponse(items=[_transaction_response(item) for item in items], next_cursor=items[-1].id if len(items) == min(max(limit, 1), 200) else None)


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def transaction_create(payload: TransactionCreate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TransactionResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        return _transaction_response(create_transaction(db, context.user.id, payload, request.headers.get("Idempotency-Key")))
    except ValueError as exc:
        raise _as_error(exc) from exc


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def transaction_update(transaction_id: str, payload: TransactionUpdate, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TransactionResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        transaction = update_transaction(db, context.user.id, transaction_id, payload, request.headers.get("Idempotency-Key"))
    except ValueError as exc:
        raise _as_error(exc) from exc
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return _transaction_response(transaction)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def transaction_delete(transaction_id: str, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> None:
    require_csrf(request, context)
    require_permission("finance.write", context)
    if delete_transaction(db, context.user.id, transaction_id, request.headers.get("Idempotency-Key")) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")


@router.get("/summary", response_model=TransactionSummary)
def summary(occurred_from: str | None = None, occurred_to: str | None = None, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> TransactionSummary:
    require_permission("finance.read", context)
    return TransactionSummary(**transaction_summary(db, context.user.id, occurred_from=_parse_datetime(occurred_from, "occurred_from"), occurred_to=_parse_datetime(occurred_to, "occurred_to")))


@router.post("/import/csv", response_model=CsvImportResponse)
def csv_import(payload: CsvImportRequest, request: Request, db: OrmSession = Depends(get_db), context: AuthContext = Depends(get_auth_context)) -> CsvImportResponse:
    require_csrf(request, context)
    require_permission("finance.write", context)
    try:
        result = import_csv(db, context.user.id, payload)
    except ValueError as exc:
        raise _as_error(exc) from exc
    return CsvImportResponse(**result)
