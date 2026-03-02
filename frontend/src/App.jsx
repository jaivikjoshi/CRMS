import { useState } from 'react'

const DEFAULT_API_URL = 'https://crms-pu5p.onrender.com'
const DEFAULT_API_KEY = 'sk_demo_crms_12345'

const PRESETS = [
  { label: 'CA SaaS → Consumer', transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 100, product: { category: 'SAAS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'CA SaaS → Business', transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 5000, product: { category: 'SAAS' }, buyer: { type: 'BUSINESS' } } },
  { label: 'CA Tangible → Consumer', transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 250.5, product: { category: 'TANGIBLE' }, buyer: { type: 'CONSUMER' } } },
  { label: 'CA Digital → Consumer', transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 19.99, product: { category: 'DIGITAL_GOODS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'TX SaaS → Consumer', transaction: { jurisdiction: 'US-TX', tax_type: 'SALES', currency: 'USD', amount: 100, product: { category: 'SAAS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'TX Tangible → Business', transaction: { jurisdiction: 'US-TX', tax_type: 'SALES', currency: 'USD', amount: 500, product: { category: 'TANGIBLE' }, buyer: { type: 'BUSINESS' } } },
  { label: 'NY SaaS → Consumer', transaction: { jurisdiction: 'US-NY', tax_type: 'SALES', currency: 'USD', amount: 99, product: { category: 'SAAS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'EU B2C Digital', transaction: { jurisdiction: 'EU', tax_type: 'VAT', currency: 'EUR', amount: 50, product: { category: 'SAAS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'EU B2B Reverse Charge', transaction: { jurisdiction: 'EU', tax_type: 'VAT', currency: 'EUR', amount: 500, product: { category: 'SAAS' }, buyer: { type: 'BUSINESS', vat_id: 'DE123456789', vat_id_confidence: 0.95 } } },
  { label: 'CA-ON Digital Consumer', transaction: { jurisdiction: 'CA-ON', tax_type: 'HST', currency: 'CAD', amount: 100, product: { category: 'SAAS' }, buyer: { type: 'CONSUMER' } } },
]

function App() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL)
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY)
  const [transaction, setTransaction] = useState(PRESETS[0].transaction)
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const applyPreset = (preset) => {
    setTransaction({ ...preset.transaction })
    setResponse(null)
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setResponse(null)
    setError(null)

    const base = apiUrl.replace(/\/$/, '')
    const url = `${base}/v1/evaluations`
    const body = {
      effective_at: new Date().toISOString().slice(0, 19) + 'Z',
      transaction,
    }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data)
        setResponse(null)
      } else {
        setResponse(data)
        setError(null)
      }
    } catch (err) {
      setError({ error: err.message })
      setResponse(null)
    } finally {
      setLoading(false)
    }
  }

  const updateTransaction = (path, value) => {
    const [key, ...rest] = path.split('.')
    if (rest.length === 0) {
      setTransaction((t) => ({ ...t, [key]: value }))
      return
    }
    const sub = rest.join('.')
    setTransaction((t) => ({
      ...t,
      [key]: key === 'product' || key === 'buyer'
        ? { ...(t[key] || {}), [rest[0]]: value }
        : t[key],
    }))
  }

  const getVal = (path) => {
    const [a, b] = path.split('.')
    return b ? (transaction[a]?.[b] ?? '') : (transaction[a] ?? '')
  }

  return (
    <>
      <h1>CRMS Evaluator</h1>
      <p className="subtitle">Test tax/compliance evaluations against the CRMS API</p>

      <form onSubmit={handleSubmit}>
        <section>
          <h2>API</h2>
          <label>Base URL</label>
          <input
            type="url"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="https://crms-xxxx.onrender.com"
          />
          <label>API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk_demo_crms_12345"
          />
        </section>

        <section>
          <h2>Transaction</h2>
          <div className="presets">
            {PRESETS.map((p) => (
              <button key={p.label} type="button" className="preset" onClick={() => applyPreset(p)}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="grid">
            <div>
              <label>Jurisdiction</label>
              <select
                value={getVal('jurisdiction')}
                onChange={(e) => updateTransaction('jurisdiction', e.target.value)}
              >
                <option value="US-CA">US-CA</option>
                <option value="US-TX">US-TX</option>
                <option value="US-NY">US-NY</option>
                <option value="EU">EU</option>
                <option value="CA-ON">CA-ON</option>
              </select>
            </div>
            <div>
              <label>Tax Type</label>
              <select
                value={getVal('tax_type')}
                onChange={(e) => updateTransaction('tax_type', e.target.value)}
              >
                <option value="SALES">SALES</option>
                <option value="VAT">VAT</option>
                <option value="HST">HST</option>
                <option value="USE">USE</option>
              </select>
            </div>
          </div>
          <label>Amount</label>
          <input
            type="number"
            step="0.01"
            value={getVal('amount')}
            onChange={(e) => updateTransaction('amount', parseFloat(e.target.value) || 0)}
            placeholder="100"
          />
          <div className="grid">
            <div>
              <label>Product Category</label>
              <select
                value={getVal('product.category')}
                onChange={(e) => updateTransaction('product.category', e.target.value)}
              >
                <option value="SAAS">SAAS</option>
                <option value="TANGIBLE">TANGIBLE</option>
                <option value="PHYSICAL_GOODS">PHYSICAL_GOODS</option>
                <option value="DIGITAL_GOODS">DIGITAL_GOODS</option>
                <option value="SERVICES">SERVICES</option>
              </select>
            </div>
            <div>
              <label>Buyer Type</label>
              <select
                value={getVal('buyer.type')}
                onChange={(e) => updateTransaction('buyer.type', e.target.value)}
              >
                <option value="CONSUMER">CONSUMER</option>
                <option value="BUSINESS">BUSINESS</option>
              </select>
            </div>
          </div>
          <button type="submit" disabled={loading}>
            {loading ? 'Evaluating…' : 'Evaluate'}
          </button>
        </section>
      </form>

      {(response || error) && (
        <section>
          <h2>Response</h2>
          {response && (
            <>
              <div className={`result-badge ${response.result.taxable ? 'taxable' : 'exempt'}`}>
                {response.result.taxable ? 'Taxable' : 'Exempt'} — {response.result.rate ? `${(response.result.rate * 100).toFixed(2)}%` : '0%'}
              </div>
              <pre className={`response ${error ? 'error' : 'success'}`}>
                {JSON.stringify(response, null, 2)}
              </pre>
            </>
          )}
          {error && (
            <pre className="response error">
              {JSON.stringify(error, null, 2)}
            </pre>
          )}
        </section>
      )}

      {loading && !response && !error && (
        <section>
          <p className="loading">Evaluating… (Render free tier may take ~30s to wake)</p>
        </section>
      )}
    </>
  )
}

export default App
