import { authenticatedFetch } from "./auth";

export type FinanceAccount = {
  id: string;
  name: string;
  account_type: string;
  color: string | null;
  balance_cents: number;
  created_at: string;
  updated_at: string;
};

export type FinanceCategory = {
  id: string;
  name: string;
  color: string | null;
};

export type FinanceTransaction = {
  id: string;
  account_id: string;
  amount_cents: number;
  description: string;
  note: string | null;
  category: FinanceCategory | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
};

export type TransactionInput = {
  account_id: string;
  amount_cents: number;
  description: string;
  note?: string | null;
  category?: string | null;
  occurred_at?: string;
};

export type CsvImportResult = {
  imported: number;
  errors: Array<{ row: number; error: string }>;
};

export type FinanceSummary = {
  total_income_cents: number;
  total_expense_cents: number;
  net_cents: number;
  count: number;
};

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Finance request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function idempotencyKey(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function cents(value: number): number {
  return Math.round(value * 100);
}

export function formatCents(value: number): string {
  const sign = value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  return `${sign}$${(absolute / 100).toLocaleString([], { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export async function listAccounts(): Promise<FinanceAccount[]> {
  const response = await authenticatedFetch("/api/v1/finance/accounts", { cache: "no-store" });
  return parse<FinanceAccount[]>(response);
}

export async function createAccount(input: { name: string; account_type: string; color?: string | null }): Promise<FinanceAccount> {
  return parse<FinanceAccount>(await authenticatedFetch("/api/v1/finance/accounts", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function deleteAccount(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/finance/accounts/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function listCategories(): Promise<FinanceCategory[]> {
  const response = await authenticatedFetch("/api/v1/finance/categories", { cache: "no-store" });
  return parse<FinanceCategory[]>(response);
}

export async function createCategory(name: string, color?: string): Promise<FinanceCategory> {
  return parse<FinanceCategory>(await authenticatedFetch("/api/v1/finance/categories", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify({ name, color: color || null }) }));
}

export async function deleteCategory(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/finance/categories/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function listTransactions(accountId?: string, category?: string): Promise<FinanceTransaction[]> {
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  if (category) params.set("category", category);
  const query = params.toString();
  const response = await authenticatedFetch(`/api/v1/finance/transactions${query ? `?${query}` : ""}`, { cache: "no-store" });
  const body = await parse<{ items: FinanceTransaction[] }>(response);
  return body.items;
}

export async function createTransaction(input: TransactionInput): Promise<FinanceTransaction> {
  return parse<FinanceTransaction>(await authenticatedFetch("/api/v1/finance/transactions", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(input) }));
}

export async function deleteTransaction(id: string): Promise<void> {
  await parse<void>(await authenticatedFetch(`/api/v1/finance/transactions/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "Idempotency-Key": idempotencyKey() } }));
}

export async function getSummary(): Promise<FinanceSummary> {
  const response = await authenticatedFetch("/api/v1/finance/summary", { cache: "no-store" });
  return parse<FinanceSummary>(response);
}

export async function importCsv(accountId: string, csv: string): Promise<CsvImportResult> {
  return parse<CsvImportResult>(await authenticatedFetch("/api/v1/finance/import/csv", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: accountId, csv }) }));
}

export { cents };
