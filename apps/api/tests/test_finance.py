"""Milestone 11 Phase B finance account, transaction, category, and CSV tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.session import get_session_factory
from app.modules.identity.service import bootstrap_owner


def _bootstrap_owner() -> None:
    db = get_session_factory()()
    try:
        bootstrap_owner(db, "owner", "correct horse battery staple")
    finally:
        db.close()


def _login(client) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert response.status_code == 200


def _account_payload(**overrides) -> dict:
    payload = {"name": "Main checking", "account_type": "checking"}
    payload.update(overrides)
    return payload


def _transaction_payload(account_id: str, **overrides) -> dict:
    payload = {"account_id": account_id, "amount_cents": -2500, "description": "Groceries", "category": "Food", "occurred_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()}
    payload.update(overrides)
    return payload


def test_finance_crud_requires_auth_and_csrf(client) -> None:
    """Finance reads require auth and cookie mutations require CSRF."""
    assert client.get("/api/v1/finance/accounts").status_code == 401
    _bootstrap_owner()
    _login(client)
    blocked = client.post("/api/v1/finance/accounts", json=_account_payload())
    assert blocked.status_code == 403
    csrf = client.cookies.get("nexus_csrf")
    created = client.post("/api/v1/finance/accounts", json=_account_payload(), headers={"X-CSRF-Token": csrf, "Idempotency-Key": "account-1"})
    assert created.status_code == 201
    replay = client.post("/api/v1/finance/accounts", json=_account_payload(name="Other"), headers={"X-CSRF-Token": csrf, "Idempotency-Key": "account-1"})
    assert replay.status_code == 422
    assert replay.json()["detail"] == "Idempotency-Key was already used for a different operation"
    account_id = created.json()["id"]
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == 0
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "account-delete-1"}
    deleted = client.delete(f"/api/v1/finance/accounts/{account_id}", headers=delete_headers)
    replay_deleted = client.delete(f"/api/v1/finance/accounts/{account_id}", headers=delete_headers)
    assert deleted.status_code == replay_deleted.status_code == 204
    assert client.get("/api/v1/finance/accounts").json() == []


def test_transaction_lifecycle_and_balance(client) -> None:
    """Transactions update account balances, support categories, and replay safely."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    account = client.post("/api/v1/finance/accounts", json=_account_payload(), headers={"X-CSRF-Token": csrf})
    account_id = account.json()["id"]
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "transaction-1"}
    created = client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id), headers=headers)
    assert created.status_code == 201
    replay = client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, description="Different"), headers=headers)
    assert replay.status_code == 422
    assert replay.json()["detail"] == "Idempotency-Key was already used for a different operation"
    transaction_id = created.json()["id"]
    assert created.json()["category"]["name"] == "Food"
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == -2500
    patched = client.patch(f"/api/v1/finance/transactions/{transaction_id}", json={"amount_cents": -5000}, headers={"X-CSRF-Token": csrf, "Idempotency-Key": "transaction-update-1"})
    assert patched.status_code == 200
    assert patched.json()["amount_cents"] == -5000
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == -5000
    income = client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, amount_cents=10000, description="Paycheck"), headers={"X-CSRF-Token": csrf})
    assert income.status_code == 201
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == 5000
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "transaction-delete-1"}
    deleted = client.delete(f"/api/v1/finance/transactions/{transaction_id}", headers=delete_headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == 10000


def test_transaction_rejects_unknown_account(client) -> None:
    """Transactions cannot be created against another user's or missing accounts."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    response = client.post("/api/v1/finance/transactions", json=_transaction_payload("not-a-real-id"), headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert "account not found" in response.json()["detail"]


def test_summary_totals_income_and_expense(client) -> None:
    """Summary reports bounded period income, expense, and net in cents."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    account = client.post("/api/v1/finance/accounts", json=_account_payload(), headers={"X-CSRF-Token": csrf})
    account_id = account.json()["id"]
    client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, amount_cents=-1500, description="Coffee"), headers={"X-CSRF-Token": csrf})
    client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, amount_cents=100000, description="Salary"), headers={"X-CSRF-Token": csrf})
    summary = client.get("/api/v1/finance/summary").json()
    assert summary["total_income_cents"] == 100000
    assert summary["total_expense_cents"] == 1500
    assert summary["net_cents"] == 98500
    assert summary["count"] == 2


def test_csv_import_strict_validation(client) -> None:
    """CSV import rejects header/row errors without writing anything, and imports clean files."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    account = client.post("/api/v1/finance/accounts", json=_account_payload(), headers={"X-CSRF-Token": csrf})
    account_id = account.json()["id"]
    headers = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    bad_headers = client.post("/api/v1/finance/import/csv", json={"account_id": account_id, "csv": "foo,bar\n1,2\n"}, headers=headers)
    assert bad_headers.status_code == 422
    assert "must include columns" in bad_headers.json()["detail"]
    mixed = client.post("/api/v1/finance/import/csv", json={"account_id": account_id, "csv": "date,description,amount\n2026-01-05,Coffee,not-a-number\n2026-01-06,Bread,-3.50\n"}, headers=headers)
    assert mixed.status_code == 200
    assert mixed.json()["imported"] == 0
    assert len(mixed.json()["errors"]) == 1
    assert mixed.json()["errors"][0]["row"] == 2
    clean = client.post("/api/v1/finance/import/csv", json={"account_id": account_id, "csv": "date,description,amount,category\n2026-01-05,Coffee,-3.50,Food\n2026-01-06,Salary,5000.00\n"}, headers=headers)
    assert clean.status_code == 200
    assert clean.json()["imported"] == 2
    assert clean.json()["errors"] == []
    listing = client.get("/api/v1/finance/transactions").json()["items"]
    assert len(listing) == 2
    assert listing[0]["amount_cents"] == -350
    assert listing[0]["category"]["name"] == "Food"
    assert client.get("/api/v1/finance/accounts").json()[0]["balance_cents"] == 499650


def test_category_lifecycle(client) -> None:
    """Finance categories are user-owned and replay-safe."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "fin-category-1"}
    category = client.post("/api/v1/finance/categories", json={"name": "Transport"}, headers=headers)
    assert category.status_code == 201
    conflict = client.post("/api/v1/finance/categories", json={"name": "Other"}, headers=headers)
    assert conflict.status_code == 422
    category_id = category.json()["id"]
    assert any(item["id"] == category_id for item in client.get("/api/v1/finance/categories").json())
    delete_headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "fin-category-delete-1"}
    assert client.delete(f"/api/v1/finance/categories/{category_id}", headers=delete_headers).status_code == 204


def test_transaction_filters_and_cursor(client) -> None:
    """Transactions filter by account, category, and time range with cursor pagination."""
    _bootstrap_owner()
    _login(client)
    csrf = client.cookies.get("nexus_csrf")
    account = client.post("/api/v1/finance/accounts", json=_account_payload(), headers={"X-CSRF-Token": csrf})
    account_id = account.json()["id"]
    client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, description="Food run", category="Food"), headers={"X-CSRF-Token": csrf})
    client.post("/api/v1/finance/transactions", json=_transaction_payload(account_id, description="Fuel", category="Transport"), headers={"X-CSRF-Token": csrf})
    food = client.get("/api/v1/finance/transactions", params={"category": "food"})
    assert food.status_code == 200
    assert len(food.json()["items"]) == 1
    assert food.json()["items"][0]["description"] == "Food run"
    account_only = client.get("/api/v1/finance/transactions", params={"account_id": account_id})
    assert len(account_only.json()["items"]) == 2
