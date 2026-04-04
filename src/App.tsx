import React, { useState, useEffect } from 'react';
import './App.css';
import editIcon from './assets/edit-icon.svg';
import delIcon from './assets/del-icon3.svg';
import LogoRct from './assets/Logo-rct.svg';
import DoneCheckMark from './assets/DoneCheckMark.svg';

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
  qbEst: { checked: boolean; value: string };
}

function App() {
  const today = new Date().toISOString().slice(0, 10);
  const [activeTab, setActiveTab] = useState('sales');
  const [form, setForm] = useState<Record<string, string>>({
    name: '',
    date: today,
    project_name: '',
    placed_by: '',
    mobile_number: '',
    status: '',
  });
  // Sales tab specific state
  const [salesItems, setSalesItems] = useState([
    { description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }
  ]);
  const [salesDiscount, setSalesDiscount] = useState(0); // Discount for the whole sale
  const [salesVAT, setSalesVAT] = useState(true); // VAT checkbox
  const [showAdditionalDetails, setShowAdditionalDetails] = useState(false); // Collapsible section
  const [referenceFields, setReferenceFields] = useState<ReferenceFields>({
    quotation: { checked: false, value: '' },
    invoice: { checked: false, value: '' },
    qb: { checked: false, value: '' },
    qbEst: { checked: false, value: '' },
  });
  const [actions, setActions] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDone, setShowDone] = useState(false);
  const [formDone, setFormDone] = useState(false); // Separate form done state
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
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set()); // Track expanded sales rows

  useEffect(() => {
    const fetchTransactions = async () => {
      setLoading(true);
      try {
        // For sales tab, fetch from new /orders endpoint
        // For other tabs, fetch from legacy /transactions endpoint
        const endpoint = activeTab === 'sales' ? '/orders' : `/transactions/${activeTab}`;
        const res = await fetch(endpoint);
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
    // Reset edit index and formDone when tab changes or on save
    setEditIdx(null);
    setFormDone(false);
  }, [activeTab]); // Only depend on activeTab

  // When a transaction is selected for editing, initialize form values:
  const handleEditTransaction = (txId: number) => {
    const tx = transactions.find(t => t.id === txId);
    if (!tx) return;
    setEditIdx(txId);
    setForm({
      name: tx.Name || '',
      date: tx.Date || today,
      description: tx.Description || '',
      reference: tx.Reference || '',
      amount: tx.Amount?.toString() || '',
      vat: tx.VAT?.toString() || '',
      total: tx.Total?.toString() || '',
      notes: activeTab === 'received' ? (tx.Description || '') : '',
    });
    setFormDone(!!tx.Done); // Set formDone from transaction
    if (activeTab === 'sales') {
      // For orders, use structured items array instead of parsing description
      const items = (tx.items && Array.isArray(tx.items)) 
        ? tx.items.map((item: any) => ({
            id: item.id, // Keep track of item ID for updates
            description: item.description || '',
            quantity: item.quantity || 1,
            price: item.price?.toString() || '',
            total: item.total || 0,
            vat: item.vat || 0,
            per_item_discount: item.per_item_discount || 0
          }))
        : [{ description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }];
      setSalesItems(items);
      setSalesDiscount(tx.discount || 0);
      setSalesVAT(!!tx.vat_total);
      // Clear reference fields for orders (they don't use references)
      setReferenceFields({
        quotation: { checked: false, value: '' },
        invoice: { checked: false, value: '' },
        qb: { checked: false, value: '' },
        qbEst: { checked: false, value: '' }
      });
    }
    if (activeTab === 'received') {
      setReceivedMethod(tx.Method || 'cash');
    }
    // Do not change showDone when editing a transaction
  };

  // Helper to summarize sales order items for table display
  function salesSummary(tx: any) {
    if (!tx.items || !Array.isArray(tx.items)) return '';
    const itemCount = tx.items.length;
    const isTax = !!tx.vat_total && tx.vat_total > 0;
    return `${itemCount} item${itemCount > 1 ? 's' : ''}, ${isTax ? 'Tax' : 'Non-tax'} client`;
  }

  // Add handler to delete transaction/order
  const handleDeleteTransaction = async (txId: number) => {
    if (!window.confirm('Are you sure you want to delete this transaction?')) return;
    try {
      const endpoint = activeTab === 'sales' ? `/orders/${txId}` : `/transactions/${activeTab}/${txId}`;
      const res = await fetch(endpoint, { method: 'DELETE' });
      if (res.ok) {
        setMessage('Transaction deleted!');
        setEditIdx(null);
        // Refetch transactions/orders
        const fetchEndpoint = activeTab === 'sales' ? '/orders' : `/transactions/${activeTab}`;
        const res2 = await fetch(fetchEndpoint);
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
    try {
      // Robust guard for null/invalid tx
      if (!tx || typeof tx !== 'object') return false;
      // Name filter (case-insensitive substring)
      if (filter.name && !(tx.Name || '').toLowerCase().includes(filter.name.toLowerCase())) return false;
      // Reference filter (case-insensitive substring)
      if (filter.reference && !(String(tx.Reference ?? '').toLowerCase().includes(filter.reference.toLowerCase()))) return false;
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
    } catch (err) {
      console.error('Error in transaction filter:', err, tx);
      return false;
    }
  }));

  // Handle sales items table changes
  const handleSalesItemChange = (idx: number, field: string, value: string | number) => {
    setSalesItems(items => {
      const newItems = [...items];
      // Fix price input: allow entering .5 as 0.5
      let val = value;
      if (field === 'price' && typeof val === 'string') {
        if (val.startsWith('.')) val = '0' + val;
        // Only allow up to 3 decimals
        val = val.replace(/^(\d*)\.(\d{0,3}).*$/, (_, int, dec) => `${int}.${dec}`);
      }
      newItems[idx] = { ...newItems[idx], [field]: val };
      // Auto-calc total and VAT with proper rounding
      const qty = parseFloat(newItems[idx].quantity as any) || 0;
      const price = parseFloat(newItems[idx].price as any) || 0;
      newItems[idx].total = +(qty * price).toFixed(2);
      newItems[idx].vat = salesVAT ? +(newItems[idx].total * 0.15).toFixed(2) : 0;
      return newItems;
    });
  };
  const handleAddSalesItem = () => {
    setSalesItems(items => {
      const newItems = [...items, { description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }];
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
  const salesTotalAfterDiscount = +(salesTotal - salesDiscount).toFixed(2);
  const salesVATTotal = +(salesTotalAfterDiscount * (salesVAT ? 0.15 : 0)).toFixed(2);
  const salesTotalWithVAT = +(salesTotalAfterDiscount + salesVATTotal).toFixed(2);

  // Helper to create unified order payload for POST and PUT /orders
  function buildOrderPayload() {
    const structuredItems = salesItems
      .filter(item => item.description.trim()) // Only include items with description
      .map(item => ({
        description: item.description,
        quantity: parseInt(item.quantity.toString()) || 1,
        price: parseFloat(item.price.toString()) || 0,
        vat: parseFloat(item.vat.toString()) || 0,
      }));
    
    const payload: any = {
      client_name: form.name,
      date: form.date,
      items: structuredItems,
      discount: salesDiscount,
    };
    
    const references = createReferencesArray(referenceFields);
    if (references) {
      payload.references = references;
    }
    
    return payload;
  }

  // Helper to flatten sales items and references for backend
  function salesDescriptionString(items: typeof salesItems) {
    // Compose items string, then append discount as last item
    const itemsStr = items.map((item, idx) =>
      `#${idx+1}: ${item.description} | Qty: ${item.quantity} | Price: ${item.price} | Total: ${item.total} | VAT: ${item.vat}`
    ).join('; ');
    return itemsStr + `; Discount: ${salesDiscount}`;
  }
  function salesReferenceString(refs: ReferenceFields) {
    return [
      refs.quotation.checked ? `Quotation#${refs.quotation.value}` : null,
      refs.invoice.checked ? `Invoice#${refs.invoice.value}` : null,
      refs.qb.checked ? `QB#${refs.qb.value}` : null,
      refs.qbEst.checked ? `QB Est#${refs.qbEst.value}` : null
    ].filter(Boolean).join(', ');
  }
  
  // Helper to convert referenceFields to structured references array
  function createReferencesArray(refs: ReferenceFields) {
    const refArray = [
      refs.quotation.checked && refs.quotation.value ? { reference_type: 'quotation', reference_value: refs.quotation.value } : null,
      refs.invoice.checked && refs.invoice.value ? { reference_type: 'invoice', reference_value: refs.invoice.value } : null,
      refs.qb.checked && refs.qb.value ? { reference_type: 'qb', reference_value: refs.qb.value } : null,
      refs.qbEst.checked && refs.qbEst.value ? { reference_type: 'qbEst', reference_value: refs.qbEst.value } : null
    ].filter(Boolean) as Array<{ reference_type: string; reference_value: string }>;
    return refArray.length > 0 ? refArray : undefined;
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
        discount: salesDiscount,
        actions: actions,
        paidStatus: paidStatus === 'none' ? undefined : paidStatus,
        done: formDone, // Use formDone for transaction
      };
      if (editIdx !== null) {
        // Update order/transaction
        try {
          if (activeTab === 'sales') {
            // For orders: use unified payload function
            const orderUpdatePayload = buildOrderPayload();
            
            const orderRes = await fetch(`/orders/${editIdx}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(orderUpdatePayload),
            });
            if (!orderRes.ok) {
              const errData = await orderRes.json();
              setMessage(errData.detail || 'Error updating order');
              return;
            }
            
            setMessage('Order updated!');
          } else {
            // For transactions, use old endpoint
            const res = await fetch(`/transactions/${activeTab}/${editIdx}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            });
            if (!res.ok) {
              const data = await res.json();
              setMessage(data.detail || 'Error updating transaction');
              return;
            }
            setMessage('Transaction updated!');
          }
          
          setEditIdx(null);
          setForm({ name: '', date: today, project_name: '', placed_by: '', mobile_number: '', status: '' });
          setSalesItems([{ description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }]);
          setSalesDiscount(0);
          setSalesVAT(true);
          setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' }, qbEst: { checked: false, value: '' } });
          setActions([]);
          setPaidStatus('none');
          setFormDone(false);
          // Refetch transactions/orders
          const endpoint = activeTab === 'sales' ? '/orders' : `/transactions/${activeTab}`;
          const res2 = await fetch(endpoint);
          if (res2.ok) setTransactions(await res2.json());
        } catch {
          setMessage('Network error');
        }
        return;
      }
      try {
        const structuredPayload = buildOrderPayload();
        const res = await fetch('/orders/structured', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(structuredPayload),
        });
        if (res.ok) {
          setMessage('Order saved!');
          setForm({ name: '', date: today, project_name: '', placed_by: '', mobile_number: '', status: '' });
          setSalesItems([{ description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }]);
          setSalesDiscount(0);
          setSalesVAT(true);
          setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' }, qbEst: { checked: false, value: '' } });
          setActions([]);
          setPaidStatus('none');
          setFormDone(false);
          // Refetch orders from new endpoint
          const orderRes = await fetch('/orders');
          if (orderRes.ok) setTransactions(await orderRes.json());
        } else {
          const data = await res.json();
          setMessage(data.detail || 'Error saving order');
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
        done: formDone,
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
            setMessage('Payment updated!');
            setEditIdx(null);
            setForm({ name: '', date: today, amount: '', notes: '' });
            setReceivedMethod('cash');
            setActions([]);
            setFormDone(false);
            // Refetch transactions
            const res2 = await fetch(`/transactions/${activeTab}`);
            if (res2.ok) setTransactions(await res2.json());
          } else {
            const data = await res.json();
            setMessage(typeof data.detail === 'string' ? data.detail : 'Error updating payment');
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
          setMessage('Payment recorded!');
          setForm({ name: '', date: today, amount: '', notes: '' });
          setReceivedMethod('cash');
          setActions([]);
          setFormDone(false);
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
    <div className="App">
      <header className="header">
        <img src={LogoRct} alt="Orders Tracking Logo" className="header-logo" />
        <h1 className="header-title">Orders Tracking</h1>
      </header>
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
                  <div style={{overflowX:'auto', maxWidth:'100%'}}>
                    <table className="sales-items-table" style={{minWidth:900, tableLayout:'fixed'}}>
                      <colgroup>
                        <col style={{width:'32%'}} />
                        <col style={{width:'13%'}} />
                        <col style={{width:'15%'}} />
                        <col style={{width:'18%'}} />
                        <col style={{width:'15%'}} />
                        <col style={{width:'7%'}} />
                      </colgroup>
                      <thead>
                        <tr>
                          <th style={{minWidth:180, padding:'8px'}}>Item Description</th>
                          <th style={{minWidth:80, padding:'8px'}}>Quantity</th>
                          <th style={{minWidth:90, padding:'8px'}}>Price</th>
                          <th style={{minWidth:110, padding:'8px'}}>Total</th>
                          <th style={{minWidth:90, padding:'8px'}}>VAT 15%</th>
                          <th style={{width:40}}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {salesItems.map((item, idx) => (
                          <tr key={idx}>
                            <td style={{padding:'6px'}}><input
                              style={{width:'100%', minWidth:120, padding:'6px'}}
                              value={item.description}
                              onChange={e => handleSalesItemChange(idx, 'description', e.target.value)}
                              ref={el => { descriptionRefs.current[idx] = el; }}
                            /></td>
                            <td style={{padding:'6px'}}><input type="number" min="1" value={item.quantity} onChange={e => handleSalesItemChange(idx, 'quantity', e.target.value)} style={{width:'100%', minWidth:60, padding:'6px'}} /></td>
                            <td style={{padding:'6px'}}><div><input type="number" min="0" step="0.001" value={item.price} onChange={e => handleSalesItemChange(idx, 'price', e.target.value)} style={{width:'100%', minWidth:70, padding:'6px'}} /></div><div style={{fontSize:'0.75em', color:'#666', marginTop:'4px'}}><label><input type="number" min="0" step="0.01" value={item.per_item_discount} onChange={e => handleSalesItemChange(idx, 'per_item_discount', e.target.value)} style={{width:50, padding:'3px'}} /> Discount</label></div></td>
                            <td style={{padding:'6px'}}>{Number(item.total).toFixed(2)}</td>
                            <td style={{padding:'6px'}}>{Number(item.vat).toFixed(2)}</td>
                            <td style={{padding:'6px'}}>{salesItems.length > 1 && <button type="button" onClick={() => handleRemoveSalesItem(idx)}>-</button>}</td>
                          </tr>
                        ))}
                        <tr>
                          <td colSpan={6}></td>
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
                    <label><input type="checkbox" checked={referenceFields.qbEst.checked} onChange={e => handleReferenceChange('qbEst', e.target.checked)} /> QB Est. # <input type="number" style={{width:70}} value={referenceFields.qbEst.value} onChange={e => handleReferenceChange('qbEst', true, e.target.value)} disabled={!referenceFields.qbEst.checked} /></label>
                  </div>
                </div>
                <div style={{marginTop:16}}>
                  <div style={{marginTop:8}}>
                    <label>Discount:</label>
                    <input type="number" min="0" step="0.01" value={salesDiscount} onChange={e => setSalesDiscount(Number(e.target.value))} style={{width:100,marginLeft:8}} />
                  </div>
                  <strong>Total: </strong>{salesTotal.toFixed(2)} &nbsp; <strong>Discount: </strong>{salesDiscount.toFixed(2)} &nbsp; <strong>Total after Discount: </strong>{salesTotalAfterDiscount.toFixed(2)} &nbsp; <strong>VAT: </strong>{salesVATTotal.toFixed(2)} &nbsp; <strong>Total (with VAT): </strong>{salesTotalWithVAT.toFixed(2)}
                </div>
                <div style={{marginTop:16, border:'1px solid #ddd', borderRadius:'4px', padding:'12px'}}>
                  <button type="button" onClick={() => setShowAdditionalDetails(!showAdditionalDetails)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1em', fontWeight:500, padding:0, color:'#0066cc'}}>
                    {showAdditionalDetails ? '▼' : '▶'} Additional Details (Optional)
                  </button>
                  {showAdditionalDetails && (
                    <div style={{marginTop:12, paddingTop:12, borderTop:'1px solid #ddd'}}>
                      <div style={{marginBottom:10}}>
                        <label>Project:</label>
                        <input type="text" name="project_name" value={form.project_name || ''} onChange={handleFormChange} placeholder="Project (optional)" style={{width:'100%', marginTop:4}} />
                      </div>
                      <div style={{marginBottom:10}}>
                        <label>Placed by:</label>
                        <input type="text" name="placed_by" value={form.placed_by || ''} onChange={handleFormChange} placeholder="Placed by (optional)" style={{width:'100%', marginTop:4}} />
                      </div>
                      <div style={{marginBottom:10}}>
                        <label>Mobile Number:</label>
                        <input type="text" name="mobile_number" value={form.mobile_number || ''} onChange={handleFormChange} placeholder="Auto-filled if empty" style={{width:'100%', marginTop:4}} />
                      </div>
                      <div>
                        <label>Status:</label>
                        <select name="status" value={form.status || ''} onChange={handleFormChange} style={{width:'100%', marginTop:4}}>
                          <option value="">-- Select Status --</option>
                          <option value="Draft">Draft</option>
                          <option value="Confirmed">Confirmed</option>
                          <option value="Delivered">Delivered</option>
                        </select>
                      </div>
                    </div>
                  )}
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
                <input type="checkbox" checked={formDone} onChange={e => setFormDone(e.target.checked)} /> Mark as done
              </label>
            </div>
            <button type="submit">{editIdx !== null ? 'Update' : 'Save'}</button>
            {editIdx !== null && (
              <button type="button" style={{marginLeft:'0.5em'}} onClick={() => {
                setEditIdx(null);
                setForm({ name: '', date: today, project_name: '', placed_by: '', mobile_number: '', status: '' });
                setSalesItems([{ description: '', quantity: 1, price: '', total: 0, vat: 0, per_item_discount: 0 }]);
                setSalesVAT(true);
                setReferenceFields({ quotation: { checked: false, value: '' }, invoice: { checked: false, value: '' }, qb: { checked: false, value: '' }, qbEst: { checked: false, value: '' } });
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
            <>
              {/* Collapse All button for sales expanded rows */}
              {activeTab === 'sales' && filteredTxs.length > 0 && (
                <button
                  type="button"
                  style={{marginBottom:8,marginLeft:8,background:'#5fa49f',color:'#fff',border:'none',borderRadius:4,padding:'6px 16px',fontWeight:500,cursor:'pointer'}}
                  onClick={() => setExpandedRows(new Set())}
                >
                  Collapse All
                </button>
              )}
              <table className="tx-table">
                <thead style={{position:'sticky',top:0,zIndex:2,background:'#fff'}}>
                  <tr>
                    <th onClick={() => setSort(s => ({ key: 'Name', direction: s.key === 'Name' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Name {sort.key === 'Name' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>
                    <th onClick={() => setSort(s => ({ key: 'Date', direction: s.key === 'Date' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Date {sort.key === 'Date' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>
                    {activeTab === 'sales' && <th>Description</th>}
                    {activeTab !== 'sales' && activeTab !== 'received' && <th onClick={() => setSort(s => ({ key: 'Reference', direction: s.key === 'Reference' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Reference {sort.key === 'Reference' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>}
                    {/* Amount column only for non-sales, non-received */}
                    {activeTab !== 'sales' && activeTab !== 'received' && <th onClick={() => setSort(s => ({ key: 'Amount', direction: s.key === 'Amount' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Amount {sort.key === 'Amount' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>}
                    {activeTab === 'purchases' && <th>VAT</th>}
                    {/* Total column for non-received */}
                    {activeTab !== 'received' && <th onClick={() => setSort(s => ({ key: 'Total', direction: s.key === 'Total' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Total {sort.key === 'Total' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>}
                    {activeTab === 'received' && <th>Notes</th>}
                    {activeTab === 'received' && <th>Method</th>}
                    <th style={{ width: 64, minWidth: 64, maxWidth: 64, textAlign: 'center' }}>Actions</th>
                    {activeTab !== 'sales' && <th onClick={() => setSort(s => ({ key: 'Done', direction: s.key === 'Done' && s.direction === 'asc' ? 'desc' : 'asc' }))} style={{cursor:'pointer'}}>
                      Done {sort.key === 'Done' && (sort.direction === 'asc' ? '▲' : '▼')}
                    </th>}
                  </tr>
                </thead>
                <tbody>
                  {filteredTxs.map((tx) => (
                    <React.Fragment key={tx.id}>
                      <tr
                        className={activeTab === 'sales' ? 'expandable-row' : ''}
                        style={activeTab === 'sales' ? {cursor:'pointer'} : {}}
                        onClick={activeTab === 'sales' ? (e) => {
                          // Only expand if not clicking on a button
                          if ((e.target as HTMLElement).tagName === 'BUTTON') return;
                          setExpandedRows(rows => {
                            const newRows = new Set(rows);
                            if (newRows.has(tx.id)) newRows.delete(tx.id);
                            else newRows.add(tx.id);
                            return newRows;
                          });
                        } : undefined}
                      >
                        <td>{tx.Name}</td>
                        <td>{tx.Date}</td>
                        {activeTab === 'sales' && <td>{salesSummary(tx)}</td>}
                        {activeTab !== 'sales' && activeTab !== 'received' && <td>{tx.Reference}</td>}
                        {/* Amount for non-sales, non-received transactions */}
                        {activeTab !== 'sales' && activeTab !== 'received' && <td>{tx.Amount}</td>}
                        {activeTab === 'purchases' && <td>{tx.VAT}</td>}
                        {/* Total for sales shows total_with_vat, others show Total */}
                        {activeTab !== 'received' && <td>{activeTab === 'sales' ? tx.total_with_vat : tx.Total}</td>}
                        {activeTab === 'received' && <td>{tx.Description}</td>}
                        {activeTab === 'received' && <td>{tx.Method ? (tx.Method.charAt(0).toUpperCase() + tx.Method.slice(1)) : ''}</td>}
                        <td style={{ width: 64, minWidth: 64, maxWidth: 64, textAlign: 'center' }}>
                          <button type="button" className="icon-btn" onClick={e => { e.stopPropagation(); handleEditTransaction(tx.id); }} style={{background:'none',border:'none',padding:0,cursor:'pointer',display:'inline-flex',alignItems:'center',justifyContent:'center'}} title="Edit">
                            <img src={editIcon} alt="Edit" style={{width:22,height:22,verticalAlign:'middle'}} />
                          </button>
                          <button type="button" className="icon-btn" onClick={e => { e.stopPropagation(); handleDeleteTransaction(tx.id); }} style={{background:'none',border:'none',padding:0,marginLeft:8,cursor:'pointer',display:'inline-flex',alignItems:'center',justifyContent:'center'}} title="Delete">
                            <img src={delIcon} alt="Delete" style={{width:22,height:22,verticalAlign:'middle'}} />
                          </button>
                        </td>
                        {activeTab !== 'sales' && <td>{tx.Done ? <img src={DoneCheckMark} alt="Done" style={{width:22,height:22,display:'block',margin:'0 auto'}} /> : ''}</td>}
                      </tr>
                      {/* Expandable details row for sales - now uses structured items array */}
                      {activeTab === 'sales' && expandedRows.has(tx.id) && (
                        <tr className="expanded-row-details">
                          <td colSpan={8} style={{background:'#f9f9f9',padding:'8px 16px'}}>
                            <strong>Items:</strong>
                            <ul style={{margin:'8px 0 0 0',padding:'0 0 0 16px'}}>
                              {(tx.items && Array.isArray(tx.items) ? tx.items : []).map((item: any, idx: number) => (
                                <li key={idx}>{item.description} | Qty: {item.quantity} | Price: {item.price?.toFixed(2)} | Total: {item.total?.toFixed(2)} | VAT: {item.vat?.toFixed(2)}</li>
                              ))}
                            </ul>
                            <div style={{marginTop:8}}><strong>VAT:</strong> {tx.vat_total > 0 ? 'Taxed' : 'Not taxed'}</div>
                            {tx.discount > 0 && (
                              <div style={{marginTop:8}}><strong>Discount:</strong> {tx.discount.toFixed(2)}</div>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
        {/* Scroll-to-top button */}
        <button
          className="scroll-to-top-btn"
          onClick={() => window.scrollTo({top:0,behavior:'smooth'})}
          aria-label="Scroll to top"
        >
          ↑
        </button>
      </div>
    </div>
  );
}

export default App;
