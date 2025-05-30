import React, { useState, useEffect } from 'react';
import './App.css';

const TABS = [
  { key: 'sales', label: 'Sales', entity: 'Customer' },
  { key: 'received', label: 'Received Amount', entity: 'Customer' },
  { key: 'purchases', label: 'Purchases', entity: 'Vendor' },
  { key: 'expenses', label: 'Expenses', entity: 'Vendor' },
];

// Per-tab field and action configuration
const TAB_FIELDS: Record<string, Array<{name: string, label: string, type?: string, required?: boolean, placeholder?: string}>> = {
  sales: [
    { name: 'name', label: 'Customer Name', required: true },
    { name: 'date', label: 'Date', type: 'date', required: true },
  ],
  received: [
    { name: 'name', label: 'Customer Name', required: true },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'description', label: 'Description' },
    { name: 'reference', label: 'Reference #' },
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'total', label: 'Total (Received)', type: 'number', placeholder: 'Auto-calculated if empty' },
  ],
  purchases: [
    { name: 'name', label: 'Vendor Name', required: true },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'description', label: 'Description' },
    { name: 'reference', label: 'Reference #' },
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'vat', label: 'VAT', type: 'number', required: true },
    { name: 'total', label: 'Total (with VAT)', type: 'number', placeholder: 'Auto-calculated if empty' },
  ],
  expenses: [
    { name: 'name', label: 'Vendor Name', required: true },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'description', label: 'Description' },
    { name: 'reference', label: 'Reference #' },
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'total', label: 'Total (Expense)', type: 'number', placeholder: 'Auto-calculated if empty' },
  ],
};

const TAB_ACTIONS: Record<string, string[]> = {
  sales: [
    'Scanned the bill',
    'Registered in the system',
    'Paid?',
    'Registered the payment in the system',
  ],
  received: [
    'Received in cash',
    'Received in bank',
    'Receipt issued',
  ],
  purchases: [
    'Scanned the bill',
    'Registered in the system',
    'Paid?',
    'Registered the payment in the system',
  ],
  expenses: [
    'Expense approved',
    'Paid?',
    'Receipt attached',
  ],
};

// Reference fields type with index signature
interface ReferenceFields {
  [key: string]: { checked: boolean; value: string };
  quotation: { checked: boolean; value: string };
  invoice: { checked: boolean; value: string };
  qb: { checked: boolean; value: string };
}

function App() {
  const today = new Date().toISOString().slice(0, 10);
  const [activeTab, setActiveTab] = useState('sales');
  const [form, setForm] = useState<Record<string, string>>({
    name: '',
    date: today,
  });
  // Sales tab specific state
  const [salesItems, setSalesItems] = useState([
    { description: '', quantity: 1, price: 0, total: 0, vat: 0 }
  ]);
  const [salesVAT, setSalesVAT] = useState(true); // VAT checkbox
  const [referenceFields, setReferenceFields] = useState<ReferenceFields>({
    quotation: { checked: false, value: '' },
    invoice: { checked: false, value: '' },
    qb: { checked: false, value: '' },
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

  // Handle sales items table changes
  const handleSalesItemChange = (idx: number, field: string, value: string | number) => {
    setSalesItems(items => {
      const newItems = [...items];
      newItems[idx] = { ...newItems[idx], [field]: value };
      // Auto-calc total and VAT
      const qty = parseFloat(newItems[idx].quantity as any) || 0;
      const price = parseFloat(newItems[idx].price as any) || 0;
      newItems[idx].total = qty * price;
      newItems[idx].vat = salesVAT ? +(newItems[idx].total * 0.15).toFixed(2) : 0;
      return newItems;
    });
  };
  const handleAddSalesItem = () => {
    setSalesItems(items => [...items, { description: '', quantity: 1, price: 0, total: 0, vat: 0 }]);
  };
  const handleRemoveSalesItem = (idx: number) => {
    setSalesItems(items => items.length > 1 ? items.filter((_, i) => i !== idx) : items);
  };
  const handleSalesVATChange = () => {
    setSalesVAT(v => !v);
    setSalesItems(items => items.map(item => ({
      ...item,
      vat: !salesVAT ? +(item.total * 0.15).toFixed(2) : 0
    })));
  };
  const handleReferenceChange = (key: string, checked: boolean, value?: string) => {
    setReferenceFields(refs => ({
      ...refs,
      [key]: {
        checked,
        value: value !== undefined ? value : refs[key]?.value || ''
      }
    }));
  };

  // Calculate totals for sales
  const salesTotal = salesItems.reduce((sum, item) => sum + (parseFloat(item.total as any) || 0), 0);
  const salesVATTotal = salesItems.reduce((sum, item) => sum + (parseFloat(item.vat as any) || 0), 0);
  const salesTotalWithVAT = salesTotal + salesVATTotal;

  // Helper to flatten sales items and references for backend
  function salesDescriptionString(items: typeof salesItems) {
    return items.map((item, idx) =>
      `#${idx+1}: ${item.description} | Qty: ${item.quantity} | Price: ${item.price} | Total: ${item.total} | VAT: ${item.vat}`
    ).join('; ');
  }
  function salesReferenceString(refs: ReferenceFields) {
    return [
      refs.quotation.checked ? `Quotation#${refs.quotation.value}` : null,
      refs.invoice.checked ? `Invoice#${refs.invoice.value}` : null,
      refs.qb.checked ? `QB#${refs.qb.value}` : null
    ].filter(Boolean).join(', ');
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    if (activeTab === 'sales') {
      if (!form.name || !form.date) {
        setMessage('Customer name and date are required.');
        return;
      }
      // Transform for backend compatibility
      const payload = {
        type: 'sales',
        name: form.name,
        date: form.date,
        description: salesDescriptionString(salesItems),
        reference: salesReferenceString(referenceFields),
        amount: salesTotal,
        vat: salesVATTotal,
        total: salesTotalWithVAT,
        actions: [],
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
          setForm({ name: '', date: '' });
          setSalesItems([{ description: '', quantity: 1, price: 0, total: 0, vat: 0 }]);
          setSalesVAT(true);
          setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' } });
        } else {
          const data = await res.json();
          setMessage(data.detail || 'Error saving transaction');
        }
      } catch (err) {
        setMessage('Network error');
      }
      return;
    }

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

  // Replace ACTIONS with per-tab actions
  const actionsList = TAB_ACTIONS[activeTab] || [];

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
            {activeTab === 'sales' ? (
              <>
                <div>
                  <label>Customer Name:<span style={{color:'red'}}> *</span></label>
                  <input name="name" value={form.name} onChange={handleFormChange} required />
                </div>
                <div>
                  <label>Date:<span style={{color:'red'}}> *</span></label>
                  <input name="date" type="date" value={form.date} onChange={handleFormChange} required />
                </div>
                <div style={{marginTop:16}}>
                  <label>Items:</label>
                  <div style={{overflowX:'auto'}}>
                  <table className="sales-items-table" style={{minWidth:600}}>
                    <thead>
                      <tr>
                        <th style={{minWidth:220, width:220}}>Item Description</th>
                        <th style={{minWidth:100, width:100}}>Quantity</th>
                        <th style={{minWidth:100, width:100}}>Price</th>
                        <th style={{minWidth:100, width:100}}>Total</th>
                        <th style={{minWidth:100, width:100}}>VAT 15%</th>
                        <th style={{width:40}}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesItems.map((item, idx) => (
                        <tr key={idx}>
                          <td><input style={{width:'100%'}} value={item.description} onChange={e => handleSalesItemChange(idx, 'description', e.target.value)} /></td>
                          <td><input type="number" min="1" value={item.quantity} onChange={e => handleSalesItemChange(idx, 'quantity', e.target.value)} style={{width:'100%'}} /></td>
                          <td><input type="number" min="0" step="0.01" value={item.price} onChange={e => handleSalesItemChange(idx, 'price', e.target.value)} style={{width:'100%'}} /></td>
                          <td>{Number(item.total).toFixed(2)}</td>
                          <td>{Number(item.vat).toFixed(2)}</td>
                          <td>{salesItems.length > 1 && <button type="button" onClick={() => handleRemoveSalesItem(idx)}>-</button>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                  <button type="button" onClick={handleAddSalesItem} style={{marginTop:4}}>+ Add Item</button>
                  <div style={{marginTop:8}}>
                    <label><input type="checkbox" checked={salesVAT} onChange={handleSalesVATChange} /> VAT 15% (uncheck for non-tax customers)</label>
                  </div>
                </div>
                <div style={{marginTop:16}}>
                  <label>References:</label>
                  <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                    <label><input type="checkbox" checked={referenceFields.quotation.checked} onChange={e => handleReferenceChange('quotation', e.target.checked)} /> Formal Quotation # <input type="number" style={{width:70}} value={referenceFields.quotation.value} onChange={e => handleReferenceChange('quotation', true, e.target.value)} disabled={!referenceFields.quotation.checked} /></label>
                    <label><input type="checkbox" checked={referenceFields.invoice.checked} onChange={e => handleReferenceChange('invoice', e.target.checked)} /> Formal Invoice # <input type="number" style={{width:70}} value={referenceFields.invoice.value} onChange={e => handleReferenceChange('invoice', true, e.target.value)} disabled={!referenceFields.invoice.checked} /></label>
                    <label><input type="checkbox" checked={referenceFields.qb.checked} onChange={e => handleReferenceChange('qb', e.target.checked)} /> QB # <input type="number" style={{width:70}} value={referenceFields.qb.value} onChange={e => handleReferenceChange('qb', true, e.target.value)} disabled={!referenceFields.qb.checked} /></label>
                  </div>
                </div>
                <div style={{marginTop:16}}>
                  <strong>Total: </strong>{salesTotal.toFixed(2)} &nbsp; <strong>VAT: </strong>{salesVATTotal.toFixed(2)} &nbsp; <strong>Total (with VAT): </strong>{salesTotalWithVAT.toFixed(2)}
                </div>
              </>
            ) : (
              TAB_FIELDS[activeTab].map(field => (
                <div key={field.name}>
                  <label>{field.label}:{field.required && <span style={{color:'red'}}> *</span>}</label>
                  {field.name === 'description' ? (
                    <textarea name={field.name} value={form[field.name]} onChange={handleFormChange} />
                  ) : (
                    <input
                      name={field.name}
                      type={field.type || 'text'}
                      value={form[field.name]}
                      onChange={handleFormChange}
                      required={field.required}
                      placeholder={field.placeholder}
                    />
                  )}
                </div>
              ))
            )}
            <button type="submit">Save</button>
          </form>
          {message && <div className="message">{message}</div>}
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
                  <tr key={tx.ID || tx.Reference || idx} className={selectedIdx === getRealIdx(idx) ? 'selected' : ''} onClick={() => handleRowClick(idx)} style={{cursor:'pointer'}}>
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
        </section>
        {selectedIdx !== null && (
          <section className="edit-section">
            <h2>Edit Transaction</h2>
            <form onSubmit={e => {
              e.preventDefault();
              handleUpdate();
            }}>
              <div>
                <label>Actions:</label>
                {actionsList.map(action => (
                  <div key={action}>
                    <label>
                      <input
                        type="checkbox"
                        checked={editActions.includes(action)}
                        onChange={() => handleEditActionChange(action)}
                      />
                      {action}
                    </label>
                  </div>
                ))}
              </div>
              <div>
                <label>
                  <input
                    type="checkbox"
                    checked={editDone}
                    onChange={handleEditDoneChange}
                  />
                  Mark as done
                </label>
              </div>
              <button type="submit">Update</button>
              <button type="button" onClick={() => setSelectedIdx(null)}>Cancel</button>
            </form>
          </section>
        )}
      </div>
    </div>
  );
}

export default App;
