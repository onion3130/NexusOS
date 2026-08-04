"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  cents,
  createAccount,
  createCategory,
  createTransaction,
  deleteAccount,
  deleteCategory,
  deleteTransaction,
  formatCents,
  getSummary,
  importCsv,
  listAccounts,
  listCategories,
  listTransactions,
  type FinanceAccount,
  type FinanceCategory,
  type FinanceTransaction,
} from "../lib/finance";

function TransactionRow({ transaction, onRemoved, onError }: { transaction: FinanceTransaction; onRemoved: (id: string) => void; onError: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  function remove() {
    if (!window.confirm(`Delete transaction “${transaction.description}”?`)) return;
    setBusy(true);
    void (async () => {
      try { await deleteTransaction(transaction.id); onRemoved(transaction.id); } catch (reason) { onError(reason instanceof Error ? reason.message : "Unable to delete transaction"); } finally { setBusy(false); }
    })();
  }
  const isIncome = transaction.amount_cents > 0;
  return <article className="finance-row">
    <span aria-hidden="true" className={`finance-amount ${isIncome ? "income" : "expense"}`}>{isIncome ? "+" : "−"}{formatCents(Math.abs(transaction.amount_cents))}</span>
    <div className="finance-row-copy">
      <strong>{transaction.description}</strong>
      <span>{new Date(transaction.occurred_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}{transaction.category ? ` · ${transaction.category.name}` : ""}</span>
    </div>
    <button aria-label={`Delete ${transaction.description}`} className="task-delete" disabled={busy} onClick={remove} type="button">⌫</button>
  </article>;
}

export function FinanceWorkspace() {
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [categories, setCategories] = useState<FinanceCategory[]>([]);
  const [transactions, setTransactions] = useState<FinanceTransaction[]>([]);
  const [summary, setSummary] = useState<{ total_income_cents: number; total_expense_cents: number; net_cents: number } | null>(null);
  const [selectedAccount, setSelectedAccount] = useState("");
  const [accountDraft, setAccountDraft] = useState("");
  const [accountType, setAccountType] = useState("checking");
  const [categoryDraft, setCategoryDraft] = useState("");
  const [categoryColorDraft, setCategoryColorDraft] = useState("#7b6cff");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [txCategory, setTxCategory] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [csvText, setCsvText] = useState("");
  const [csvResult, setCsvResult] = useState<{ imported: number; errors: Array<{ row: number; error: string }> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [accountItems, categoryItems, txItems, summaryData] = await Promise.all([listAccounts(), listCategories(), listTransactions(), getSummary()]);
      setAccounts(accountItems);
      setCategories(categoryItems);
      setTransactions(txItems);
      setSummary(summaryData);
      setSelectedAccount((current) => current || (accountItems[0]?.id ?? ""));
      setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Finance data unavailable"); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const visibleTransactions = useMemo(() => selectedAccount ? transactions.filter((transaction) => transaction.account_id === selectedAccount) : transactions, [selectedAccount, transactions]);
  const activeAccount = useMemo(() => accounts.find((account) => account.id === selectedAccount) ?? null, [accounts, selectedAccount]);

  async function addAccount() {
    if (!accountDraft.trim() || saving) return;
    setSaving(true); setError(null);
    try {
      const created = await createAccount({ name: accountDraft.trim(), account_type: accountType });
      setAccounts((items) => [...items, created]);
      setAccountDraft("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create account"); } finally { setSaving(false); }
  }
  function removeAccount(id: string) {
    if (!window.confirm("Delete this account and all of its transactions?")) return;
    void (async () => {
      try {
        await deleteAccount(id);
        setAccounts((items) => items.filter((item) => item.id !== id));
        setTransactions((items) => items.filter((item) => item.account_id !== id));
        setSelectedAccount("");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete account"); }
    })();
  }
  async function addTransaction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!description.trim() || !amount || !selectedAccount || saving) return;
    setSaving(true); setError(null);
    try {
      const signed = kind === "income" ? Math.abs(cents(Number(amount))) : -Math.abs(cents(Number(amount)));
      const created = await createTransaction({ account_id: selectedAccount, amount_cents: signed, description: description.trim(), category: txCategory.trim() || null, occurred_at: occurredAt ? new Date(occurredAt).toISOString() : new Date().toISOString() });
      setTransactions((items) => [created, ...items]);
      setDescription(""); setAmount(""); setTxCategory(""); setOccurredAt("");
      void refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create transaction"); } finally { setSaving(false); }
  }
  function addCategory() {
    if (!categoryDraft.trim()) return;
    void (async () => {
      try {
        const created = await createCategory(categoryDraft.trim(), categoryColorDraft);
        setCategories((items) => [...items, created]);
        setCategoryDraft(""); setCategoryColorDraft("#7b6cff");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create category"); }
    })();
  }
  function removeCategory(id: string) {
    if (!window.confirm("Delete this category? Transactions keep their amounts.")) return;
    void (async () => {
      try { await deleteCategory(id); setCategories((items) => items.filter((item) => item.id !== id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete category"); }
    })();
  }
  async function runImport() {
    if (!csvText.trim() || !selectedAccount) return;
    setSaving(true); setError(null); setCsvResult(null);
    try {
      const result = await importCsv(selectedAccount, csvText);
      setCsvResult(result);
      if (result.imported > 0) { setCsvText(""); void refresh(); }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to import CSV"); } finally { setSaving(false); }
  }

  return <section aria-labelledby="finance-heading" className="finance-workspace section-block">
    <div className="section-heading"><div><p className="eyebrow">Money, tracked in cents</p><h2 id="finance-heading">Finance</h2></div><button className="refresh-button" disabled={loading} onClick={() => void refresh()} type="button">{loading ? "Loading…" : "Refresh"}</button></div>

    <div className="finance-summary">
      <article className="metric-card"><div className="metric-indicator green" /><p>Net balance</p><strong>{summary ? formatCents(summary.net_cents) : "—"}</strong><span>Across all accounts</span></article>
      <article className="metric-card"><div className="metric-indicator blue" /><p>Income</p><strong>{summary ? formatCents(summary.total_income_cents) : "—"}</strong><span>All time</span></article>
      <article className="metric-card"><div className="metric-indicator" /><p>Expenses</p><strong>{summary ? formatCents(summary.total_expense_cents) : "—"}</strong><span>All time</span></article>
    </div>

    <div className="finance-accounts"><strong>Accounts</strong><div className="event-category-fields"><input aria-label="Account name" maxLength={64} onChange={(event) => setAccountDraft(event.target.value)} placeholder="New account" value={accountDraft} /><select aria-label="Account type" onChange={(event) => setAccountType(event.target.value)} value={accountType}><option value="checking">Checking</option><option value="savings">Savings</option><option value="cash">Cash</option><option value="credit">Credit</option><option value="investment">Investment</option></select><button className="text-button" disabled={!accountDraft.trim()} onClick={addAccount} type="button">Add account</button></div><div className="finance-account-list">{accounts.map((account) => <span className={`finance-account-chip${selectedAccount === account.id ? " selected" : ""}`} key={account.id}><button className="finance-account-select" onClick={() => setSelectedAccount(account.id)} type="button"><span style={{ background: account.color ?? "var(--accent)" }} />{account.name}<em>{formatCents(account.balance_cents)}</em></button><button aria-label={`Delete account ${account.name}`} className="category-delete" onClick={() => removeAccount(account.id)} type="button">×</button></span>)}</div></div>

    <form className="task-create-form" onSubmit={addTransaction}><label htmlFor="tx-description">New transaction{activeAccount ? ` · ${activeAccount.name}` : ""}</label><div className="task-create-main"><input id="tx-description" maxLength={255} onChange={(event) => setDescription(event.target.value)} placeholder="What was it for?" value={description} /><button className="primary-button" disabled={!description.trim() || !amount || !selectedAccount || saving} type="submit">{saving ? "Adding…" : "Add transaction"}</button></div><div className="task-create-options"><label className="checkbox-label finance-kind"><button aria-pressed={kind === "expense"} className={kind === "expense" ? "kind-active kind-expense" : ""} onClick={() => setKind("expense")} type="button">Expense</button><button aria-pressed={kind === "income"} className={kind === "income" ? "kind-active kind-income" : ""} onClick={() => setKind("income")} type="button">Income</button></label><input aria-label="Amount" inputMode="decimal" min="0" onChange={(event) => setAmount(event.target.value)} placeholder="Amount" step="0.01" type="number" value={amount} /><input aria-label="Category" list="finance-categories" maxLength={64} onChange={(event) => setTxCategory(event.target.value)} placeholder="Category" value={txCategory} /><datalist id="finance-categories">{categories.map((item) => <option key={item.id} value={item.name} />)}</datalist><input aria-label="Occurred at" onChange={(event) => setOccurredAt(event.target.value)} type="datetime-local" value={occurredAt} /></div></form>

    <div className="finance-category-manager"><strong>Categories</strong><div className="event-category-fields"><input aria-label="Category name" maxLength={64} onChange={(event) => setCategoryDraft(event.target.value)} placeholder="New category" value={categoryDraft} /><input aria-label="Category color" onChange={(event) => setCategoryColorDraft(event.target.value)} type="color" value={categoryColorDraft} /><button className="text-button" disabled={!categoryDraft.trim()} onClick={addCategory} type="button">Add category</button></div>{categories.map((item) => <span className="event-category event-category-managed" key={item.id} style={{ borderColor: item.color ?? "var(--line-strong)", color: item.color ?? "var(--muted-strong)" }}>{item.name}<button aria-label={`Delete category ${item.name}`} className="category-delete" onClick={() => removeCategory(item.id)} type="button">×</button></span>)}</div>

    <details className="finance-import"><summary>Import transactions from CSV</summary><p className="import-hint">Columns: <code>date, description, amount, category</code> (date ISO-8601 or YYYY-MM-DD; amount in decimal currency). Every row is validated before anything is written.</p><textarea aria-label="CSV content" onChange={(event) => setCsvText(event.target.value)} placeholder={"date,description,amount,category\n2026-01-05,Coffee,-3.50,Food"} rows={5} value={csvText} /><button className="text-button" disabled={!csvText.trim() || !selectedAccount || saving} onClick={runImport} type="button">Import CSV</button>{csvResult && <div className={`inline-state ${csvResult.errors.length ? "error-state" : ""}`}><strong>{csvResult.imported > 0 ? `${csvResult.imported} transaction${csvResult.imported === 1 ? "" : "s"} imported.` : "Nothing imported."}</strong>{csvResult.errors.length > 0 && <span>{csvResult.errors.map((item) => `Row ${item.row}: ${item.error}`).join(" · ")}</span>}</div>}</details>

    {error && <div className="inline-state error-state" role="alert"><strong>Finance unavailable.</strong><span>{error}</span><button className="text-button" onClick={() => void refresh()} type="button">Retry</button></div>}
    {loading ? <div className="task-list-placeholder" role="status">Loading your ledger…</div> : visibleTransactions.length === 0 ? <div className="empty-state task-empty"><span className="empty-icon">₿</span><strong>No transactions yet</strong><span>Add a transaction or import a CSV to start tracking.</span></div> : <div className="finance-list">{visibleTransactions.map((transaction) => <TransactionRow key={transaction.id} onError={setError} onRemoved={(id) => setTransactions((items) => items.filter((item) => item.id !== id))} transaction={transaction} />)}</div>}
  </section>;
}
