import TransactionRow from "./TransactionRow";

export default function TransactionTable({transactions, updateCategory, categories}) {
  const transactionElements = transactions.map((transaction) => (
    <TransactionRow
        key={transaction.id}
        {...transaction}
        updateCategory={updateCategory}
        categories={categories}
      />
  ))
  return (
    <section className="transaction-table">
      <div className="transaction-row transaction-header">
        <div>Date</div>
        <div>Merchant</div>
        <div>Category</div>
        <div>Amount</div>
        <div>Account</div>
      </div>
      {/* conditional rendering by getting the length of the transactions and printing
      no transactions found when the length is <= 0 */}
      {transactions.length > 0 ? (
      transactionElements
    ) : (
      <div className="empty-state">
        No transactions found.
      </div>
    )}

      
    </section>
  );
}