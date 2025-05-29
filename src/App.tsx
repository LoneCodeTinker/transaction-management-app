import React, { useState, useEffect } from 'react';
import './App.css';

const TABS = [
  { key: 'sales', label: 'Sales', entity: 'Customer' },
  { key: 'received', label: 'Received Amount', entity: 'Customer' },
  { key: 'purchases', label: 'Purchases', entity: 'Vendor' },
  { key: 'expenses', label: 'Expenses', entity: 'Vendor' },
];

const ACTIONS = [
  'Scanned the bill',
  'Registered in the system',
  'Paid?',
  'Registered the payment in the system',
];

function App() {
  const [activeTab, setActiveTab] = useState('sales');
  const [form, setForm] = useState({
    name: '',
    date: '',
    description: '',
    reference: '',
    amount: '',
    vat: '',
    total: '',
  });
  const [actions, setActions] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [editActions, setEditActions] = useState<string[]>([]);
  const [editDone, setEditDone] = useState(false);
  const [showDone, setShowDone] = useState(false);

  useEffect(() => {
    const fetchTransactions = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/transactions/${activeTab}`); // Use relative path for proxy
        if (res.ok) {
          const data = await res.json();
          setTransactions(data);
        } else {
          setTransactions([]);
        }
      } catch {
        setTransactions([]);
      }
      setLoading(false);
    };
    fetchTransactions();
  }, [activeTab, message]); // refetch on tab or after save

  useEffect(() => {
    setSelectedIdx(null);
    setEditActions([]);
    setEditDone(false);
  }, [activeTab, showDone]); // add showDone to dependencies

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleActionChange = (action: string) => {
    setActions(prev =>
      prev.includes(action) ? prev.filter(a => a !== action) : [...prev, action]
    );
  };

  const handleEditActionChange = (action: string) => {
    setEditActions(prev =>
      prev.includes(action) ? prev.filter(a => a !== action) : [...prev, action]
    );
  };

  const handleEditDoneChange = () => {
    setEditDone(d => !d);
  };

  const filteredTxs = showDone ? transactions : transactions.filter(tx => !tx.Done);

  // Map filtered index to real index in transactions
  const getRealIdx = (filteredIdx: number) => {
    if (showDone) return filteredIdx;
    // Find the index in the full transactions array
    const tx = filteredTxs[filteredIdx];
    return transactions.findIndex(t => t === tx);
  };

  const handleRowClick = (idx: number) => {
    const realIdx = getRealIdx(idx);
    setSelectedIdx(realIdx);
    setEditActions(Array.isArray(transactions[realIdx].Actions) ? transactions[realIdx].Actions : []);
    setEditDone(!!transactions[realIdx].Done);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    // Calculate total if not provided
    const total = form.total || (parseFloat(form.amount) + parseFloat(form.vat)).toString();
    const payload = {
      type: activeTab,
      name: form.name,
      date: form.date,
      description: form.description,
      reference: form.reference,
      amount: parseFloat(form.amount),
      vat: parseFloat(form.vat),
      total: parseFloat(total),
      actions,
      done: false,
    };
    try {
      const res = await fetch('/transaction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setMessage('Transaction saved!');
        setForm({ name: '', date: '', description: '', reference: '', amount: '', vat: '', total: '' });
        setActions([]);
      } else {
        const data = await res.json();
        setMessage(data.detail || 'Error saving transaction');
      }
    } catch (err) {
      setMessage('Network error');
    }
  };

  const handleUpdate = async () => {
    if (selectedIdx === null) return;
    setMessage('');
    try {
      const res = await fetch(`/transactions/${activeTab}/${selectedIdx}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Actions: editActions, Done: editDone }),
      });
      if (res.ok) {
        setMessage('Transaction updated!');
        setSelectedIdx(null);
      } else {
        const data = await res.json();
        setMessage(data.detail || 'Error updating transaction');
      }
    } catch {
      setMessage('Network error');
    }
  };

  return (
    <div className="container">
      <h1>Transaction Management</h1>
      <div className="tabs">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? 'active' : ''}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="tab-content">
        <section className="form-section">
          <h2>Add {TABS.find(t => t.key === activeTab)?.label} Transaction</h2>
          <form onSubmit={handleSubmit}>
            <div>
              <label>{TABS.find(t => t.key === activeTab)?.entity} Name:</label>
              <input name="name" value={form.name} onChange={handleFormChange} required />
            </div>
            <div>
              <label>Date:</label>
              <input name="date" type="date" value={form.date} onChange={handleFormChange} required />
            </div>
            <div>
              <label>Description:</label>
              <textarea name="description" value={form.description} onChange={handleFormChange} />
            </div>
            <div>
              <label>Reference #:</label>
              <input name="reference" value={form.reference} onChange={handleFormChange} />
            </div>
            <div>
              <label>Amount:</label>
              <input name="amount" type="number" step="0.01" value={form.amount} onChange={handleFormChange} required />
            </div>
            <div>
              <label>VAT:</label>
              <input name="vat" type="number" step="0.01" value={form.vat} onChange={handleFormChange} required />
            </div>
            <div>
              <label>Total (with VAT):</label>
              <input name="total" type="number" step="0.01" value={form.total} onChange={handleFormChange} placeholder="Auto-calculated if empty" />
            </div>
            <button type="submit">Save</button>
          </form>
          {message && <div className="message">{message}</div>}
        </section>
        <section className="actions-section">
          <h3>Actions</h3>
          <ul>
            {ACTIONS.map(action => (
              <li key={action}>
                <input
                  type="checkbox"
                  id={action}
                  checked={actions.includes(action)}
                  onChange={() => handleActionChange(action)}
                />
                <label htmlFor={action}>{action}</label>
              </li>
            ))}
          </ul>
        </section>
        <section className="list-section">
          <h3>Transactions List</h3>
          <label style={{marginBottom:8,display:'block'}}>
            <input type="checkbox" checked={showDone} onChange={e => setShowDone(e.target.checked)} /> Show Done Transactions
          </label>
          {loading ? (
            <div>Loading...</div>
          ) : filteredTxs.length === 0 ? (
            <div>No transactions found.</div>
          ) : (
            <table className="tx-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Reference</th>
                  <th>Amount</th>
                  <th>VAT</th>
                  <th>Total</th>
                  <th>Actions</th>
                  <th>Done</th>
                </tr>
              </thead>
              <tbody>
                {filteredTxs.map((tx, idx) => (
                  <tr key={idx} className={selectedIdx === getRealIdx(idx) ? 'selected' : ''} onClick={() => handleRowClick(idx)} style={{cursor:'pointer'}}>
                    <td>{tx.Name}</td>
                    <td>{tx.Date}</td>
                    <td>{tx.Description}</td>
                    <td>{tx.Reference}</td>
                    <td>{tx.Amount}</td>
                    <td>{tx.VAT}</td>
                    <td>{tx.Total}</td>
                    <td>{Array.isArray(tx.Actions) ? tx.Actions.join(', ') : tx.Actions}</td>
                    <td>{tx.Done ? '✔️' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {selectedIdx !== null && transactions[selectedIdx] && (
            <div className="edit-panel">
              <h4>Edit Transaction Status</h4>
              <div>
                <strong>Actions:</strong>
                <ul>
                  {ACTIONS.map(action => (
                    <li key={action}>
                      <input
                        type="checkbox"
                        id={`edit-${action}`}
                        checked={editActions.includes(action)}
                        onChange={() => handleEditActionChange(action)}
                      />
                      <label htmlFor={`edit-${action}`}>{action}</label>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <label>
                  <input type="checkbox" checked={editDone} onChange={handleEditDoneChange} /> Done
                </label>
              </div>
              <button onClick={handleUpdate}>Update</button>
              <button onClick={() => setSelectedIdx(null)} style={{marginLeft:8}}>Cancel</button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
