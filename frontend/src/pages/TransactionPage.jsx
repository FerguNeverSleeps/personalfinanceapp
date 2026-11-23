import { useState } from "react"
import transactions from "../data/transactions"
import TransactionTable from "../components/TransactionTable"

export default function TransactionsPage() {
  const [search, setSearch] = useState("")
  const [view, setView] = useState("all")
  const [category, setCategory] = useState("all")
  const [account, setAccount] = useState("all")
  //convert categories into a set to remove duplicates and 
  // convert the set back into an array with [...new Set(...)]
  const categories = [
    ...new Set(
        transactions.map((transaction) => transaction.category)
    )
  ]

  const accounts = [
    ...new Set(
      transactions.map((transaction) => transaction.account)
    )
  ]
  const filteredTransactions = transactions.filter((transaction) =>{
  const matchesSearch = transaction.merchant
      .toLowerCase()
      .includes(search.toLowerCase())

  const matchesView =
      view === "all" ||
      transaction.category === "Uncategorized"

  const matchesCategory =
  category === "all" ||
  transaction.category === category

  const matchesAccount =
    account === "all" ||
    transaction.account === account

  

  return matchesSearch && matchesView && matchesCategory && matchesAccount
  })

  

  return (
    <main className="page-container">
      <div className="page-header">
        <h1>Transactions</h1>
        <p>Label, filter, and turn labels into rules.</p>
      </div>

      <div className="transaction-toolbar">
        <select
          value={view}
          onChange={(event) => setView(event.target.value)}
        >
          <option value="all">All transactions</option>
          <option value="uncategorized">Uncategorized only</option>
        </select>

        <input
        type="search"
        placeholder="Search merchant, note..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        />
        
        {/* <button type="button" disabled>
          Search
        </button> */}
      </div>

      <select
        value={category}
        onChange={(event) => setCategory(event.target.value)}
      >
        <option value="all">All categories</option>

        {categories.map((categoryName) => (
          <option
          key={categoryName}
          value={categoryName}
          >
          {categoryName}
          </option>
        ))}
      </select>

      <select
        value={account}
        onChange={(event)=> setAccount(event.target.value)}
      >
        <option value="all">All Accounts</option> 
        {accounts.map(currentAccount => (
          <option
          key={currentAccount}
          value={currentAccount}
          >{currentAccount}</option>
        ))}
      </select>

      <TransactionTable transactions={filteredTransactions} />
    </main>
  );
}