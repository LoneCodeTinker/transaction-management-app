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
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'notes', label: 'Notes' },
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
  const [showDone, setShowDone] = useState(false);
  // Add payment method state for received tab
  const [receivedMethod, setReceivedMethod] = useState<'cash' | 'bank'>('cash');
  // Paid status for sales tab
  const [paidStatus, setPaidStatus] = useState<'none' | 'partial' | 'full'>('none');
  // Add edit mode state
  const [editIdx, setEditIdx] = useState<number | null>(null);
  // Filter state for transactions list
  const [filter, setFilter] = useState({
    name: '',
    date: '',
    minAmount: '',
    maxAmount: '',
    reference: '',
    datePreset: 'all', // new: preset selector
    customDate: '', // for custom single date
    rangeStart: '', // for date range
    rangeEnd: '',
  });
  // Sort state for transactions list
  const [sort, setSort] = useState<{ key: string; direction: 'asc' | 'desc' }>({ key: '', direction: 'asc' });

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
    // Reset edit index when tab changes or on save
    setEditIdx(null);
    setShowDone(false);
  }, [activeTab, showDone]); // add showDone to dependencies

  // Map filtered index to real index in transactions (fix: use a unique id for each transaction)
  // We'll add a _rowIdx property to each transaction when loading from backend
  useEffect(() => {
    setTransactions(ts => ts.map((tx, idx) => ({ ...tx, _rowIdx: idx })));
  }, [transactions.length]);

  // When a transaction is selected for editing, initialize form values:
  const handleEditTransaction = (rowIdx: number) => {
    const tx = transactions.find(t => t._rowIdx === rowIdx);
    if (!tx) return;
    setEditIdx(rowIdx);
    setForm({
      name: tx.Name || '',
      date: tx.Date || today,
      description: tx.Description || '',
      reference: tx.Reference || '',
      amount: tx.Amount?.toString() || '',
      vat: tx.VAT?.toString() || '',
      total: tx.Total?.toString() || '',
      notes: tx.Description || '', // for received
    });
    if (activeTab === 'sales') {
      setSalesItems(parseSalesDescription(tx.Description));
      setSalesVAT(!!tx.VAT);
      // Parse references
      const ref: ReferenceFields = {
        quotation: { checked: /Quotation#/i.test(tx.Reference), value: (tx.Reference?.match(/Quotation#(\d+)/i)?.[1] || '') },
        invoice: { checked: /Invoice#/i.test(tx.Reference), value: (tx.Reference?.match(/Invoice#(\d+)/i)?.[1] || '') },
        qb: { checked: /QB#/i.test(tx.Reference), value: (tx.Reference?.match(/QB#(\d+)/i)?.[1] || '') },
      };
      setReferenceFields(ref);
    }
    if (activeTab === 'received') {
      setReceivedMethod(tx.Method || 'cash');
    }
    setShowDone(!!tx.Done);
  };

  // Helper to parse sales description string into items array
  function parseSalesDescription(desc: string) {
    if (!desc) return [{ description: '', quantity: 1, price: 0, total: 0, vat: 0 }];
    return desc.split(';').map(itemStr => {
      const m = itemStr.match(/#\d+:\s*(.*?)\s*\|\s*Qty:\s*(\d+)\s*\|\s*Price:\s*([\d.]+)\s*\|\s*Total:\s*([\d.]+)\s*\|\s*VAT:\s*([\d.]+)/i);
      if (m) {
        return {
          description: m[1].trim(),
          quantity: parseInt(m[2]),
          price: parseFloat(m[3]),
          total: parseFloat(m[4]),
          vat: parseFloat(m[5]),
        };
      }
      // fallback: just description
      return { description: itemStr.trim(), quantity: 1, price: 0, total: 0, vat: 0 };
    });
  }

  // Add handler to delete transaction
  const handleDeleteTransaction = async (rowIdx: number) => {
    if (!window.confirm('Are you sure you want to delete this transaction?')) return;
    try {
      const res = await fetch(`/transactions/${activeTab}/${rowIdx}`, { method: 'DELETE' });
      if (res.ok) {
        setMessage('Transaction deleted!');
        setEditIdx(null);
        // Refetch transactions
        const res2 = await fetch(`/transactions/${activeTab}`);
        if (res2.ok) setTransactions(await res2.json());
      } else {
        setMessage('Error deleting transaction');
      }
    } catch {
      setMessage('Network error');
    }
  };

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // Set default filter to 'thismonth' on mount
  React.useEffect(() => {
    setFilter(f => ({ ...f, datePreset: 'thismonth' }));
  }, []);

  // Helper to get date boundaries (fix: use UTC for all date math, but compare to tx.Date as string)
  function getDateRange(preset: string) {
    const now = new Date();
    // Always use UTC for date math, but compare to tx.Date as string (assumed local date in yyyy-mm-dd)
    const today = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    let start: Date | null = null, end: Date | null = null;
    switch (preset) {
      case 'today':
        start = new Date(today);
        end = new Date(today);
        break;
      case 'yesterday':
        start = new Date(today);
        start.setUTCDate(today.getUTCDate() - 1);
        end = new Date(start);
        break;
      case 'thisweek': {
        const day = today.getUTCDay() || 7;
        start = new Date(today);
        start.setUTCDate(today.getUTCDate() - day + 1);
        end = new Date(today);
        break;
      }
      case 'lastweek': {
        const day = today.getUTCDay() || 7;
        end = new Date(today);
        end.setUTCDate(today.getUTCDate() - day);
        start = new Date(end);
        start.setUTCDate(end.getUTCDate() - 6);
        break;
      }
      case 'thismonth':
        start = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 1));
        end = new Date(today);
        break;
      case 'lastmonth': {
        const first = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - 1, 1));
        const last = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 0));
        start = new Date(first);
        end = new Date(last);
        break;
      }
      case 'thisyear':
        start = new Date(Date.UTC(today.getUTCFullYear(), 0, 1));
        end = new Date(today);
        break;
      default:
        start = end = null;
    }
    return { start, end };
  }

  // Helper to sort transactions
  function sortTransactions(arr: any[]) {
    if (!sort.key) return arr;
    return [...arr].sort((a, b) => {
      let aVal = a[sort.key] ?? '';
      let bVal = b[sort.key] ?? '';
      // For Done, convert to 0/1
      if (sort.key === 'Done') {
        aVal = aVal ? 1 : 0;
        bVal = bVal ? 1 : 0;
      }
      // For Amount, parse as float
      if (sort.key === 'Amount') {
        aVal = parseFloat(aVal) || 0;
        bVal = parseFloat(bVal) || 0;
      }
      // For Date, compare as string (yyyy-mm-dd)
      if (sort.key === 'Date') {
        aVal = (aVal || '').slice(0, 10);
        bVal = (bVal || '').slice(0, 10);
      }
      if (aVal < bVal) return sort.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sort.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }

  // Compose filtered and sorted transactions
  const filteredTxs = sortTransactions((showDone ? transactions : transactions.filter(tx => !tx.Done)).filter(tx => {
    // Name filter (case-insensitive substring)
    if (filter.name && !(tx.Name || '').toLowerCase().includes(filter.name.toLowerCase())) return false;
    // Reference filter (case-insensitive substring)
    if (filter.reference && !(tx.Reference || '').toLowerCase().includes(filter.reference.toLowerCase())) return false;
    // Min amount
    if (filter.minAmount && Number(tx.Amount) < Number(filter.minAmount)) return false;
    // Max amount
    if (filter.maxAmount && Number(tx.Amount) > Number(filter.maxAmount)) return false;
    // Date filtering (fix: compare to local yyyy-mm-dd, but use UTC for preset math)
    const txDateStr = tx.Date ? tx.Date.slice(0, 10) : '';
    if (filter.datePreset && filter.datePreset !== 'all') {
      if (filter.datePreset === 'custom') {
        if (filter.customDate && txDateStr !== filter.customDate) return false;
      } else if (filter.datePreset === 'range') {
        if (filter.rangeStart && filter.rangeEnd) {
          if (!txDateStr || txDateStr < filter.rangeStart || txDateStr > filter.rangeEnd) return false;
        }
      } else {
        const { start, end } = getDateRange(filter.datePreset);
        if (start && end && txDateStr) {
          // Convert UTC date to yyyy-mm-dd for comparison
          const startStr = start.toISOString().slice(0, 10);
          const endStr = end.toISOString().slice(0, 10);
          if (txDateStr < startStr || txDateStr > endStr) return false;
        }
      }
    } else if (filter.date) {
      if (txDateStr !== filter.date) return false;
    }
    return true;
  }));

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
    setSalesItems(items => {
      const newItems = [...items, { description: '', quantity: 1, price: 0, total: 0, vat: 0 }];
      setTimeout(() => {
        const idx = newItems.length - 1;
        descriptionRefs.current[idx]?.focus();
      }, 0);
      return newItems;
    });
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
      const payload = {
        type: 'sales',
        name: form.name,
        date: form.date,
        description: salesDescriptionString(salesItems),
        reference: salesReferenceString(referenceFields),
        amount: salesTotal,
        vat: salesVATTotal,
        total: salesTotalWithVAT,
        actions: actions,
        paidStatus: paidStatus === 'none' ? undefined : paidStatus,
        done: showDone,
      };
      if (editIdx !== null) {
        // Update transaction with full payload
        try {
          const res = await fetch(`/transactions/${activeTab}/${editIdx}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (res.ok) {
            setMessage('Transaction updated!');
            setEditIdx(null);
            setForm({ name: '', date: today });
            setSalesItems([{ description: '', quantity: 1, price: 0, total: 0, vat: 0 }]);
            setSalesVAT(true);
            setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' } });
            setActions([]);
            setPaidStatus('none');
            setShowDone(false);
            // Refetch transactions
            const res2 = await fetch(`/transactions/${activeTab}`);
            if (res2.ok) setTransactions(await res2.json());
          } else {
            const data = await res.json();
            setMessage(data.detail || 'Error updating transaction');
          }
        } catch {
          setMessage('Network error');
        }
        return;
      }
      try {
        const res = await fetch('/transaction', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          setMessage('Transaction saved!');
          setForm({ name: '', date: today });
          setSalesItems([{ description: '', quantity: 1, price: 0, total: 0, vat: 0 }]);
          setSalesVAT(true);
          setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' } });
          setActions([]);
          setPaidStatus('none');
        } else {
          const data = await res.json();
          setMessage(data.detail || 'Error saving transaction');
        }
      } catch (err) {
        setMessage('Network error');
      }
      return;
    }
    if (activeTab === 'received') {
      if (!form.name || !form.date || !form.amount) {
        setMessage('Name, date, and amount are required.');
        return;
      }
      const payload = {
        type: 'received',
        name: form.name,
        date: form.date,
        description: form.notes || '', // send as description
        amount: parseFloat(form.amount),
        vat: 0, // required by backend
        total: parseFloat(form.amount), // required by backend
        method: receivedMethod, // send method to backend
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
          setMessage('Payment recorded!');
          setForm({ name: '', date: today, amount: '', notes: '' });
          setReceivedMethod('cash');
          setActions([]);
        } else {
          const data = await res.json();
          setMessage(typeof data.detail === 'string' ? data.detail : 'Error saving payment');
        }
      } catch (err) {
        setMessage('Network error');
      }
      return;
    }
    // Purchases/Expenses custom logic
    if (activeTab === 'purchases' || activeTab === 'expenses') {
      if (!form.name || !form.date || !form.amount || (activeTab === 'purchases' && !form.vat)) {
        setMessage('Please fill all required fields.');
        return;
      }
      let total = form.total;
      if (!total || isNaN(Number(total))) {
        if (activeTab === 'purchases') {
          total = (parseFloat(form.amount) + parseFloat(form.vat)).toString();
        } else {
          total = form.amount;
        }
      }
      const payload = {
        type: activeTab,
        name: form.name,
        date: form.date,
        description: form.description,
        reference: form.reference,
        amount: parseFloat(form.amount),
        vat: activeTab === 'purchases' ? parseFloat(form.vat) : 0,
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
          setForm({ name: '', date: today, description: '', reference: '', amount: '', vat: '', total: '' });
          setActions([]);
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
        setForm({ name: '', date: today, description: '', reference: '', amount: '', vat: '', total: '' });
        setActions([]);
      } else {
        const data = await res.json();
        setMessage(data.detail || 'Error saving transaction');
      }
    } catch (err) {
      setMessage('Network error');
    }
  };

  const descriptionRefs = React.useRef<Array<HTMLInputElement | null>>([]);

  // Add useEffect to focus the last description input when salesItems changes or when editing a transaction
  React.useEffect(() => {
    if (editIdx !== null && salesItems.length === 1) {
      // Focus the first (and only) description field when editing a single-item transaction
      descriptionRefs.current[0]?.focus();
    } else if (salesItems.length > 1) {
      // Focus the last description field when adding or editing multi-item transactions
      descriptionRefs.current[salesItems.length - 1]?.focus();
    }
  }, [salesItems.length, editIdx]);

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
                            <td><input
                              style={{width:'100%'}}
                              value={item.description}
                              onChange={e => handleSalesItemChange(idx, 'description', e.target.value)}
                              ref={el => { descriptionRefs.current[idx] = el; }}
                            /></td>
                            <td><input type="number" min="1" value={item.quantity} onChange={e => handleSalesItemChange(idx, 'quantity', e.target.value)} style={{width:'100%'}} /></td>
                            <td><input type="number" min="0" step="0.01" value={item.price} onChange={e => handleSalesItemChange(idx, 'price', e.target.value)} style={{width:'100%'}} /></td>
                            <td>{Number(item.total).toFixed(2)}</td>
                            <td>{Number(item.vat).toFixed(2)}</td>
                            <td>{salesItems.length > 1 && <button type="button" onClick={() => handleRemoveSalesItem(idx)}>-</button>}</td>
                          </tr>
                        ))}
                        <tr>
                          <td colSpan={5}></td>
                          <td>
                            <button type="button" onClick={handleAddSalesItem} style={{marginTop:4}}>+</button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
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
                {/* Remove actions UI from add form for sales tab */}
              </>
            ) : activeTab === 'received' ? (
              <>
                {TAB_FIELDS.received.map(field => (
                  <div key={field.name}>
                    <label>{field.label}:{field.required && <span style={{color:'red'}}> *</span>}</label>
                    {field.name === 'notes' ? (
                      <textarea name={field.name} value={form[field.name] || ''} onChange={handleFormChange} />
                    ) : (
                      <input
                        name={field.name}
                        type={field.type || 'text'}
                        value={form[field.name] || ''}
                        onChange={handleFormChange}
                        required={field.required}
                        placeholder={field.placeholder}
                        // Remove width:100% for radio/checkbox
                        style={field.type === 'number' || field.type === 'date' ? undefined : {}}
                      />
                    )}
                  </div>
                ))}
                <div style={{marginTop:8}}>
                  <label>Payment Method:</label>
                  <div style={{display:'flex',gap:16,marginTop:4}}>
                    <label style={{display:'flex',alignItems:'center',gap:4}}>
                      <input type="radio" name="receivedMethod" value="cash" checked={receivedMethod === 'cash'} onChange={() => setReceivedMethod('cash')} /> Cash
                    </label>
                    <label style={{display:'flex',alignItems:'center',gap:4}}>
                      <input type="radio" name="receivedMethod" value="bank" checked={receivedMethod === 'bank'} onChange={() => setReceivedMethod('bank')} /> Bank
                    </label>
                  </div>
                </div>
              </>
            ) : (
              TAB_FIELDS[activeTab].map(field => {
                // Hide VAT for expenses
                if (activeTab === 'expenses' && field.name === 'vat') return null;
                // Auto-calc total for purchases/expenses
                let value = form[field.name] || '';
                if (field.name === 'total') {
                  if (activeTab === 'purchases') {
                    value = (form.amount && form.vat) ? (parseFloat(form.amount) + parseFloat(form.vat)).toString() : '';
                  } else if (activeTab === 'expenses') {
                    value = form.amount || '';
                  }
                }
                return (
                  <div key={field.name}>
                    <label>{field.label}:{field.required && <span style={{color:'red'}}> *</span>}</label>
                    {field.name === 'description' ? (
                      <textarea name={field.name} value={form[field.name] || ''} onChange={handleFormChange} />
                    ) : (
                      <input
                        name={field.name}
                        type={field.type || 'text'}
                        value={value}
                        onChange={handleFormChange}
                        required={field.required && (field.name !== 'total')}
                        placeholder={field.placeholder}
                        disabled={field.name === 'total'}
                      />
                    )}
                  </div>
                );
              })
            )}
            <div>
              <label>
                <input type="checkbox" checked={showDone} onChange={e => setShowDone(e.target.checked)} /> Mark as done
              </label>
            </div>
            <button type="submit">{editIdx !== null ? 'Update' : 'Save'}</button>
            {editIdx !== null && (
              <button type="button" onClick={() => {
                setEditIdx(null);
                setForm({ name: '', date: today });
                setSalesItems([{ description: '', quantity: 1, price: 0, total: 0, vat: 0 }]);
                setSalesVAT(true);
                setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' } });
                setActions([]);
                setPaidStatus('none');
                setShowDone(false);
                setReceivedMethod('cash');
              }}>Cancel</button>
            )}
          </form>
          {message && <div className="message">{message}</div>}
        </section>
        <section className="list-section">
          <h3>Transactions List</h3>
          {/* Filter UI */}
          <div style={{display:'flex',gap:12,flexWrap:'wrap',marginBottom:12,alignItems:'flex-end'}}>
            <div>
              <label style={{fontWeight:400}}>Name:</label><br/>
              <input type="text" value={filter.name} onChange={e => setFilter(f => ({...f, name: e.target.value}))} placeholder="Search name" style={{width:120}} />
            </div>
            <div>
              <label style={{fontWeight:400}}>Date Filter:</label><br/>
              <select value={filter.datePreset} onChange={e => setFilter(f => ({...f, datePreset: e.target.value, customDate:'', rangeStart:'', rangeEnd:'', date:''}))} style={{width:150}}>
                <option value="all">All Dates</option>
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="thisweek">This Week</option>
                <option value="lastweek">Last Week</option>
                <option value="thismonth">This Month</option>
                <option value="lastmonth">Last Month</option>
                <option value="thisyear">This Year</option>
                <option value="custom">Custom Date</option>
                <option value="range">Date Range</option>
              </select>
            </div>
            {filter.datePreset === 'custom' && (
              <div>
                <label style={{fontWeight:400}}>Date:</label><br/>
                <input type="date" value={filter.customDate} onChange={e => setFilter(f => ({...f, customDate: e.target.value}))} style={{width:140}} />
              </div>
            )}
            {filter.datePreset === 'range' && (
              <>
                <div>
                  <label style={{fontWeight:400}}>From:</label><br/>
                  <input type="date" value={filter.rangeStart} onChange={e => setFilter(f => ({...f, rangeStart: e.target.value}))} style={{width:120}} />
                </div>
                <div>
                  <label style={{fontWeight:400}}>To:</label><br/>
                  <input type="date" value={filter.rangeEnd} onChange={e => setFilter(f => ({...f, rangeEnd: e.target.value}))} style={{width:120}} />
                </div>
              </>
            )}
            {activeTab !== 'received' && (
              <div>
                <label style={{fontWeight:400}}>Reference:</label><br/>
                <input type="text" value={filter.reference} onChange={e => setFilter(f => ({...f, reference: e.target.value}))} placeholder="Search ref" style={{width:120}} />
              </div>
            )}
            <div>
              <label style={{fontWeight:400}}>Min Amount:</label><br/>
              <input type="number" value={filter.minAmount} onChange={e => setFilter(f => ({...f, minAmount: e.target.value}))} placeholder="Min" style={{width:90}} />
            </div>
            <div>
              <label style={{fontWeight:400}}>Max Amount:</label><br/>
              <input type="number" value={filter.maxAmount} onChange={e => setFilter(f => ({...f, maxAmount: e.target.value}))} placeholder="Max" style={{width:90}} />
            </div>
            <button type="button" onClick={() => {
              setFilter({name:'',date:'',minAmount:'',maxAmount:'',reference:'',datePreset:'thismonth',customDate:'',rangeStart:'',rangeEnd:''});
              setSort({ key: '', direction: 'asc' });
            }} style={{height:36}}>Clear</button>
          </div>
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
                  <th onClick={() => setSort(s => ({ key: 'Name', direction: s.key === 'Name' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Name {sort.key === 'Name' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => setSort(s => ({ key: 'Date', direction: s.key === 'Date' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Date {sort.key === 'Date' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>
                  {activeTab !== 'received' && <th>Description</th>}
                  {activeTab !== 'received' && <th onClick={() => setSort(s => ({ key: 'Reference', direction: s.key === 'Reference' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Reference {sort.key === 'Reference' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>}
                  <th onClick={() => setSort(s => ({ key: 'Amount', direction: s.key === 'Amount' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Amount {sort.key === 'Amount' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>
                  {activeTab === 'purchases' && <th>VAT</th>}
                  <th onClick={() => setSort(s => ({ key: 'Total', direction: s.key === 'Total' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Total {sort.key === 'Total' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>
                  <th>Actions</th>
                  <th onClick={() => setSort(s => ({ key: 'Done', direction: s.key === 'Done' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                    Done {sort.key === 'Done' && (sort.direction === 'asc' ? '▲' : '▼')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredTxs.map((tx) => (
                  <tr key={tx._rowIdx}>
                    <td>{tx.Name}</td>
                    <td>{tx.Date}</td>
                    {activeTab !== 'received' && <td>{tx.Description}</td>}
                    {activeTab !== 'received' && <td>{tx.Reference}</td>}
                    <td>{tx.Amount}</td>
                    {activeTab === 'purchases' && <td>{tx.VAT}</td>}
                    <td>{tx.Total}</td>
                    <td>
                      <button type="button" onClick={() => handleEditTransaction(tx._rowIdx)}>Edit</button>
                      <button type="button" onClick={() => handleDeleteTransaction(tx._rowIdx)} style={{marginLeft:4}}>Delete</button>
                    </td>
                    <td>{tx.Done ? '✔️' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;
