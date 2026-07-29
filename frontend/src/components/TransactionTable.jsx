import TransactionRow from "./TransactionRow";

export default function TransactionTable() {
  return (
    <section className="transaction-table">
      <div className="transaction-row transaction-header">
        <div>Date</div>
        <div>Merchant</div>
        <div>Category</div>
        <div>Amount</div>
        <div>Account</div>
      </div>

      <TransactionRow
        date="2026-07-25"
        merchant="Orion Systems BV"
        category="Income"
        amount={2850}
        account="Demo Current Account"
      />

      <TransactionRow
        date="2026-07-23"
        merchant="Northstar Market"
        category="Groceries"
        amount={-72.78}
        account="Demo Current Account"
      />

      <TransactionRow
        date="2026-07-21"
        merchant="Metro OV Pass"
        category="Transport"
        amount={-18.3}
        account="Demo Current Account"
      />
    </section>
  );
}