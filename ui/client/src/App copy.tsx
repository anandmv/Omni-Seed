import './App.css'
import { useState, useEffect } from 'react';
import { fetchTransactions, type TransactionsPage } from './mocks/mockTransactions.ts';

function App() {
  // const [cursor, setCursor] = useState<string>('0');
  const [transactions, setTransactions] = useState<TransactionsPage | null>(null);
  //   const  fetchData = async () => {
  //   const data = await fetchTransactions(cursor);
  //     setTransactions((prev) => [...prev, data]);    }
  //   fetchData();
  // }, [fetchTransactions, setTransactions, cursor]);

  const loadMore = async () => {
    const controller = new AbortController();
    const lastPage = transactions?.nextCursor || '0';
    const newTransactions = await fetchTransactions(lastPage, controller.signal);
    setTransactions(newTransactions);
  };

useEffect(() => {
    loadMore();
    return () => {};
  }, [loadMore]);

  return (
    <>
      <section id="center">
        test
        {transactions && transactions.data.map((txn) => (
          <div key={txn.id}>
            <p>{txn.merchant}</p>
            <p>{txn.amount} {txn.currency}</p>
            <p>{txn.status}</p>
          </div>
        ))}
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
      <button onClick={loadMore}>Load More</button>
    </>
  )
}

export default App
