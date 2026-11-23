export default function TransactionRow({
  date,
  merchant,
  category,
  amount,
  account,
  updateCategory,
  categories,
}) {
  const amountClass = amount < 0 ? "negative" : "positive";

  return (
    <div className="transaction-row">
      <div>{date}</div>
      <div className="merchant">{merchant}</div>
      <select
        value={category}
        onChange={(event) =>
          updateCategory(id, event.target.value)
        }
      >
        {categories.map((categoryName) => (
          <option
            key={categoryName}
            value={categoryName}
          >
            {categoryName}
          </option>
        ))}
      </select>

      <div className={amountClass}>
        €{amount.toFixed(2)}
      </div>

      <div>{account}</div>
    </div>
  );
}