export default function TransactionRow({
  date,
  merchant,
  category,
  amount,
  account,
}) {
  const amountClass = amount < 0 ? "negative" : "positive";

  return (
    <div className="transaction-row">
      <div>{date}</div>
      <div className="merchant">{merchant}</div>
      <div>{category}</div>

      <div className={amountClass}>
        €{amount.toFixed(2)}
      </div>

      <div>{account}</div>
    </div>
  );
}