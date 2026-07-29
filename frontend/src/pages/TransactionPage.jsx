import TransactionTable from "../components/TransactionTable";

export default function TransactionsPage() {
  return (
    <main className="page-container">
      <div className="page-header">
        <h1>Transactions</h1>
        <p>Label, filter, and turn labels into rules.</p>
      </div>

      <div className="transaction-toolbar">
        <select aria-label="Transaction status">
          <option>All transactions</option>
          <option>Uncategorized only</option>
        </select>

        <input
          type="search"
          placeholder="Search merchant or note..."
          disabled
        />

        <button type="button" disabled>
          Search
        </button>
      </div>

      <TransactionTable />
    </main>
  );
}