import { useState } from 'react'

const DEFAULT_API_URL = 'https://crms-pu5p.onrender.com'
const DEFAULT_API_KEY = 'sk_demo_crms_12345'

// Every jurisdiction in the ruleset and its required tax_type + default currency.
const JURISDICTIONS = [
  { value: 'US-CA', label: 'US-CA — California (Sales Tax)', tax_type: 'SALES', currency: 'USD' },
  { value: 'US-TX', label: 'US-TX — Texas (Sales Tax)',      tax_type: 'SALES', currency: 'USD' },
  { value: 'US-NY', label: 'US-NY — New York (Sales Tax)',   tax_type: 'SALES', currency: 'USD' },
  { value: 'EU',    label: 'EU — European Union (VAT)',      tax_type: 'VAT',   currency: 'EUR' },
  { value: 'CA-ON', label: 'CA-ON — Ontario (HST)',          tax_type: 'HST',   currency: 'CAD' },
]

const JURISDICTION_MAP = Object.fromEntries(JURISDICTIONS.map((j) => [j.value, j]))

const PRODUCT_CATEGORIES = [
  { value: 'SAAS', label: 'SAAS' },
  { value: 'DIGITAL_GOODS', label: 'DIGITAL_GOODS' },
  { value: 'SERVICES', label: 'SERVICES' },
  { value: 'TANGIBLE', label: 'TANGIBLE' },
  { value: 'PHYSICAL_GOODS', label: 'PHYSICAL_GOODS' },
]

const BUYER_TYPES = [
  { value: 'CONSUMER', label: 'CONSUMER' },
  { value: 'BUSINESS', label: 'BUSINESS' },
]

const PRESETS = [
  { label: 'CA SaaS → Consumer',      transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 100,    product: { category: 'SAAS' },         buyer: { type: 'CONSUMER' } } },
  { label: 'CA SaaS → Business',      transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 5000,   product: { category: 'SAAS' },         buyer: { type: 'BUSINESS' } } },
  { label: 'CA Tangible → Consumer',  transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 250.5,  product: { category: 'TANGIBLE' },     buyer: { type: 'CONSUMER' } } },
  { label: 'CA Digital → Consumer',   transaction: { jurisdiction: 'US-CA', tax_type: 'SALES', currency: 'USD', amount: 19.99,  product: { category: 'DIGITAL_GOODS' }, buyer: { type: 'CONSUMER' } } },
  { label: 'TX SaaS → Consumer',      transaction: { jurisdiction: 'US-TX', tax_type: 'SALES', currency: 'USD', amount: 100,    product: { category: 'SAAS' },         buyer: { type: 'CONSUMER' } } },
  { label: 'TX Tangible → Business',  transaction: { jurisdiction: 'US-TX', tax_type: 'SALES', currency: 'USD', amount: 500,    product: { category: 'TANGIBLE' },     buyer: { type: 'BUSINESS' } } },
  { label: 'NY SaaS → Consumer',      transaction: { jurisdiction: 'US-NY', tax_type: 'SALES', currency: 'USD', amount: 99,     product: { category: 'SAAS' },         buyer: { type: 'CONSUMER' } } },
  { label: 'EU B2C Digital',          transaction: { jurisdiction: 'EU',    tax_type: 'VAT',   currency: 'EUR', amount: 50,     product: { category: 'SAAS' },         buyer: { type: 'CONSUMER' } } },
  { label: 'EU B2B Reverse Charge',   transaction: { jurisdiction: 'EU',    tax_type: 'VAT',   currency: 'EUR', amount: 500,    product: { category: 'SAAS' },         buyer: { type: 'BUSINESS', vat_id: 'DE123456789', vat_id_confidence: 0.95 } } },
  { label: 'CA-ON Digital Consumer',  transaction: { jurisdiction: 'CA-ON', tax_type: 'HST',   currency: 'CAD', amount: 100,    product: { category: 'SAAS' },         buyer: { type: 'CONSUMER' } } },
]

// --- Scenario Explorer: run one base transaction across many jurisdiction × product × buyer combos
function ScenarioExplorer({ apiUrl, apiKey }) {
  const [amount, setAmount] = useState(100)
  const [selectedJurs, setSelectedJurs] = useState(['US-CA', 'EU', 'CA-ON'])
  const [selectedProducts, setSelectedProducts] = useState(['SAAS', 'DIGITAL_GOODS'])
  const [selectedBuyers, setSelectedBuyers] = useState(['CONSUMER', 'BUSINESS'])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [error, setError] = useState(null)
  const [expandedRow, setExpandedRow] = useState(null)

  const toggleJur = (v) => setSelectedJurs((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])
  const toggleProduct = (v) => setSelectedProducts((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])
  const toggleBuyer = (v) => setSelectedBuyers((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])
  const selectAllJurs = () => setSelectedJurs(JURISDICTIONS.map((j) => j.value))
  const selectAllProducts = () => setSelectedProducts(PRODUCT_CATEGORIES.map((p) => p.value))
  const selectAllBuyers = () => setSelectedBuyers(BUYER_TYPES.map((b) => b.value))

  const runScenario = async () => {
    const combos = []
    for (const j of selectedJurs) {
      const meta = JURISDICTION_MAP[j]
      for (const cat of selectedProducts) {
        for (const buyer of selectedBuyers) {
          combos.push({
            jurisdiction: j,
            tax_type: meta.tax_type,
            currency: meta.currency,
            amount,
            product: { category: cat },
            buyer: { type: buyer },
          })
        }
      }
    }
    setLoading(true)
    setError(null)
    setResults([])
    setProgress({ done: 0, total: combos.length })

    const base = apiUrl.replace(/\/$/, '')
    const url = `${base}/v1/evaluations`
    const effective_at = new Date().toISOString().slice(0, 19) + 'Z'
    const out = []

    for (let i = 0; i < combos.length; i++) {
      setProgress({ done: i, total: combos.length })
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
          body: JSON.stringify({ effective_at, transaction: combos[i] }),
        })
        const data = await res.json()
        out.push({
          transaction: combos[i],
          ok: res.ok,
          response: data,
        })
      } catch (err) {
        out.push({ transaction: combos[i], ok: false, response: { error: err.message } })
      }
    }

    setProgress({ done: combos.length, total: combos.length })
    setResults(out)
    setLoading(false)
  }

  return (
    <section>
      <h2>Scenario Explorer</h2>
      <p className="field-hint">Run one base transaction across multiple jurisdictions, product categories, and buyer types. Compare tax outcomes in one view.</p>

      <label>Base amount</label>
      <input
        type="number"
        step="0.01"
        min="0"
        value={amount}
        onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
        style={{ maxWidth: '8rem', marginBottom: '1rem' }}
      />

      <div className="scenario-axes">
        <div className="axis">
          <label>Jurisdictions</label>
          <button type="button" className="axis-all" onClick={selectAllJurs}>All</button>
          {JURISDICTIONS.map((j) => (
            <label key={j.value} className="checkbox-label">
              <input type="checkbox" checked={selectedJurs.includes(j.value)} onChange={() => toggleJur(j.value)} />
              {j.value}
            </label>
          ))}
        </div>
        <div className="axis">
          <label>Product categories</label>
          <button type="button" className="axis-all" onClick={selectAllProducts}>All</button>
          {PRODUCT_CATEGORIES.map((p) => (
            <label key={p.value} className="checkbox-label">
              <input type="checkbox" checked={selectedProducts.includes(p.value)} onChange={() => toggleProduct(p.value)} />
              {p.label}
            </label>
          ))}
        </div>
        <div className="axis">
          <label>Buyer type</label>
          <button type="button" className="axis-all" onClick={selectAllBuyers}>All</button>
          {BUYER_TYPES.map((b) => (
            <label key={b.value} className="checkbox-label">
              <input type="checkbox" checked={selectedBuyers.includes(b.value)} onChange={() => toggleBuyer(b.value)} />
              {b.label}
            </label>
          ))}
        </div>
      </div>

      <p className="field-hint">
        {selectedJurs.length * selectedProducts.length * selectedBuyers.length} combinations will be evaluated.
      </p>

      <button type="button" className="btn-primary" onClick={runScenario} disabled={loading}>
        {loading ? `Running… ${progress.done}/${progress.total}` : 'Run scenario'}
      </button>

      {error && <pre className="response error">{error}</pre>}

      {results.length > 0 && (
        <div className="scenario-table-wrap">
          <table className="scenario-table">
            <thead>
              <tr>
                <th>Jurisdiction</th>
                <th>Product</th>
                <th>Buyer</th>
                <th>Taxable</th>
                <th>Rate</th>
                <th>Rule</th>
                <th>Risks</th>
                <th>Obligations</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {results.map((row, i) => {
                const r = row.response?.result
                const ok = row.ok && r
                const rate = ok && r.rate != null ? `${(r.rate * 100).toFixed(2)}%` : (row.response?.error ? 'Error' : '-')
                const ruleId = ok ? r.matched_rule_id || '-' : '-'
                const riskCount = ok && r.risk_flags?.length ? r.risk_flags.length : 0
                const obCount = ok && r.obligations?.length ? r.obligations.length : 0
                const key = `${row.transaction.jurisdiction}-${row.transaction.product.category}-${row.transaction.buyer.type}`
                const isExpanded = expandedRow === i
                return (
                  <tr key={key} className={!row.ok ? 'row-error' : ''}>
                    <td>{row.transaction.jurisdiction}</td>
                    <td>{row.transaction.product.category}</td>
                    <td>{row.transaction.buyer.type}</td>
                    <td>
                      {ok ? (
                        <span className={`result-badge small ${r.taxable ? 'taxable' : 'exempt'}`}>
                          {r.taxable ? 'Yes' : 'No'}
                        </span>
                      ) : '-'}
                    </td>
                    <td>{rate}</td>
                    <td className="rule-cell">{ruleId}</td>
                    <td>{riskCount ? <span className="risk-dot">{riskCount}</span> : '-'}</td>
                    <td>{obCount ? <span className="ob-dot">{obCount}</span> : '-'}</td>
                    <td>
                      <button type="button" className="row-detail-btn" onClick={() => setExpandedRow(isExpanded ? null : i)}>
                        {isExpanded ? '−' : '+'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {expandedRow !== null && results[expandedRow] && (() => {
            const row = results[expandedRow]
            const res = row.response?.result
            return (
              <div className="row-detail">
                <h3>Detail: {row.transaction.jurisdiction} / {row.transaction.product.category} / {row.transaction.buyer.type}</h3>
                {res?.rate_components?.length > 0 && (
                  <div className="rate-components">
                    {res.rate_components.map((rc) => (
                      <span key={rc.name} className="rate-component">{rc.name}: {(rc.rate * 100).toFixed(2)}%</span>
                    ))}
                  </div>
                )}
                {res?.risk_flags?.length > 0 && (
                  <div className="risk-flags">
                    {res.risk_flags.map((rf, idx) => (
                      <span key={idx} className={`risk-flag severity-${rf.severity?.toLowerCase()}`}>{rf.type}</span>
                    ))}
                  </div>
                )}
                {res?.obligations?.length > 0 && (
                  <div className="obligations">
                    {res.obligations.map((ob, idx) => (
                      <div key={idx} className="obligation">
                        <span className="ob-type">{ob.type}</span>
                        {ob.message && <span className="ob-message"> — {ob.message}</span>}
                      </div>
                    ))}
                  </div>
                )}
                <pre className="response small">{JSON.stringify(row.response, null, 2)}</pre>
              </div>
            )
          })()}
        </div>
      )}
    </section>
  )
}

function App() {
  const [tab, setTab] = useState('evaluator')
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL)
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY)
  const [transaction, setTransaction] = useState(PRESETS[0].transaction)
  const [explainFull, setExplainFull] = useState(false)
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const applyPreset = (preset) => {
    setTransaction({ ...preset.transaction })
    setResponse(null)
    setError(null)
  }

  const handleJurisdictionChange = (jur) => {
    const meta = JURISDICTION_MAP[jur]
    setTransaction((t) => ({
      ...t,
      jurisdiction: jur,
      tax_type: meta.tax_type,
      currency: meta.currency,
    }))
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
      ...(explainFull && { options: { explain: 'full', near_miss: 3, counterfactuals: 2 } }),
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

  const setNested = (obj, keys, value) => {
    if (keys.length === 1) return { ...obj, [keys[0]]: value }
    return { ...obj, [keys[0]]: setNested(obj[keys[0]] || {}, keys.slice(1), value) }
  }

  const updateTransaction = (path, value) => {
    setTransaction((t) => setNested(t, path.split('.'), value))
  }

  const getVal = (path) => {
    return path.split('.').reduce((obj, key) => obj?.[key] ?? '', transaction)
  }

  const jurMeta = JURISDICTION_MAP[transaction.jurisdiction]

  return (
    <>
      <h1>CRMS Evaluator</h1>
      <p className="subtitle">Test tax/compliance evaluations against the CRMS API</p>

      <nav className="tabs">
        <button type="button" className={tab === 'evaluator' ? 'tab active' : 'tab'} onClick={() => setTab('evaluator')}>
          Single evaluation
        </button>
        <button type="button" className={tab === 'scenario' ? 'tab active' : 'tab'} onClick={() => setTab('scenario')}>
          Scenario Explorer
        </button>
      </nav>

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

      {tab === 'evaluator' && (
        <>
          <form onSubmit={handleSubmit}>
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
                value={transaction.jurisdiction}
                onChange={(e) => handleJurisdictionChange(e.target.value)}
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j.value} value={j.value}>{j.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Tax Type</label>
              <div className="tax-type-badge">{jurMeta?.tax_type ?? transaction.tax_type}</div>
              <p className="field-hint">Determined by jurisdiction</p>
            </div>
          </div>

          <label>Amount ({transaction.currency})</label>
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
                <option value="DIGITAL_GOODS">DIGITAL_GOODS</option>
                <option value="SERVICES">SERVICES</option>
                <option value="TANGIBLE">TANGIBLE</option>
                <option value="PHYSICAL_GOODS">PHYSICAL_GOODS</option>
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

          <div className="explain-option">
            <label className="explain-option-label">
              <input
                type="checkbox"
                checked={explainFull}
                onChange={(e) => setExplainFull(e.target.checked)}
              />
              <span>Include full trace (why this rule fired, evidence paths, near-miss rules, counterfactuals)</span>
            </label>
            <p className="field-hint">When enabled, the API returns an auditable reasoning trace and counterfactual guidance.</p>
          </div>

              <button type="submit" disabled={loading}>
                {loading ? 'Evaluating…' : 'Evaluate'}
              </button>
            </section>
          </form>

          {loading && !response && !error && (
            <section>
              <p className="loading">Evaluating… (Render free tier may take ~30s to wake)</p>
            </section>
          )}

          {(response || error) && (
            <section>
              <h2>Response</h2>
              {response && (
            <>
              <div className={`result-badge ${response.result.taxable ? 'taxable' : 'exempt'}`}>
                {response.result.taxable ? 'Taxable' : 'Exempt'} — {response.result.rate ? `${(response.result.rate * 100).toFixed(2)}%` : '0%'}
                {response.result.matched_rule_id && (
                  <span className="rule-id"> · {response.result.matched_rule_id}</span>
                )}
              </div>

              {response.result.rate_components?.length > 0 && (
                <div className="rate-components">
                  <strong>Rate breakdown:</strong>
                  {response.result.rate_components.map((rc) => (
                    <span key={rc.name} className="rate-component">
                      {rc.name}: {(rc.rate * 100).toFixed(2)}%
                    </span>
                  ))}
                </div>
              )}

              {response.result.risk_flags?.length > 0 && (
                <div className="risk-flags">
                  <strong>Risk flags:</strong>
                  {response.result.risk_flags.map((rf, i) => (
                    <span key={i} className={`risk-flag severity-${rf.severity?.toLowerCase()}`}>
                      {rf.type} ({rf.severity})
                    </span>
                  ))}
                </div>
              )}

              {response.result.obligations?.length > 0 && (
                <div className="obligations">
                  <strong>Obligations:</strong>
                  {response.result.obligations.map((ob, i) => (
                    <div key={i} className="obligation">
                      <span className="ob-type">{ob.type}</span>
                      {ob.message && <span className="ob-message"> — {ob.message}</span>}
                    </div>
                  ))}
                </div>
              )}

              {/* Show trace section when user requested full trace (so they see either data or a clear message) */}
              {(explainFull || response.explanation?.trace) && (
                <div className="trace-section">
                  <h3>Reasoning trace</h3>
                  {response.explanation?.trace ? (
                    <>
                      {response.explanation.trace.winner && (
                        <p><strong>Winner:</strong> {response.explanation.trace.winner.rule_id} — {response.explanation.trace.winner.name}</p>
                      )}
                      <p><strong>Confidence:</strong> {response.explanation.trace.confidence}</p>
                      {response.explanation.trace.evidence_paths_used?.length > 0 && (
                        <p><strong>Evidence paths used:</strong> {response.explanation.trace.evidence_paths_used.join(', ')}</p>
                      )}
                      {response.explanation.trace.missing_evidence?.length > 0 && (
                        <p><strong>Missing evidence:</strong> {response.explanation.trace.missing_evidence.join(', ')}</p>
                      )}
                      {response.explanation.trace.steps?.length > 0 && (
                        <details className="trace-details" open>
                          <summary>Rule steps ({response.explanation.trace.steps.length})</summary>
                          {response.explanation.trace.steps.map((s, i) => (
                            <div key={i} className="trace-step">
                              <span className={s.matched ? 'trace-matched' : ''}>{s.rule_id}</span> (priority {s.priority}) — {s.matched ? 'matched' : 'did not match'}
                              {s.evaluated?.length > 0 && (
                                <ul>
                                  {s.evaluated.filter(e => e.node_type === 'leaf').slice(0, 8).map((e, j) => (
                                    <li key={j} className={e.passed ? 'trace-pass' : 'trace-fail'}>
                                      {e.path || e.op}: {String(e.actual)} {e.op === 'eq' ? '==' : e.op} {String(e.expected)} → {e.passed ? '✓' : '✗'}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          ))}
                        </details>
                      )}
                      {response.explanation.trace.near_miss_rules?.length > 0 && (
                        <p><strong>Near-miss rules:</strong> {response.explanation.trace.near_miss_rules.map(r => r.rule_id).join(', ')}</p>
                      )}
                      {response.explanation.trace.counterfactuals?.length > 0 && (
                        <div className="counterfactuals">
                          <h4 className="counterfactuals-title">Counterfactuals (to change outcome)</h4>
                          <details className="counterfactuals-explainer">
                            <summary>What are counterfactuals?</summary>
                            <p>Suggestions for what to change so this transaction would get a different result (e.g. exempt instead of taxable). Each block is built from a &quot;near-miss&quot; rule that almost matched. Apply the listed changes to see the preview outcome.</p>
                          </details>
                          <div className="counterfactual-current">
                            Currently: {response.result.taxable ? 'taxable' : 'exempt'} at {((response.result.rate || 0) * 100).toFixed(2)}%
                          </div>
                          {response.explanation.trace.counterfactuals.map((cf, i) => (
                            <div key={i} className="counterfactual-card">
                              <div className="counterfactual-goal">
                                <span className="counterfactual-goal-label">Goal:</span> <span className="counterfactual-goal-value">{cf.goal.replace(/_/g, ' ')}</span>
                                <span className="counterfactual-rule"> (from rule {cf.based_on_rule_id})</span>
                                {cf.changes?.length > 0 && (
                                  <span className="counterfactual-count"> · {cf.changes.length} change{cf.changes.length !== 1 ? 's' : ''}</span>
                                )}
                              </div>
                              <ul className="counterfactual-changes">
                                {cf.changes?.map((ch, j) => (
                                  <li key={j} className="counterfactual-change">
                                    <span className="cf-path">{ch.path}</span>
                                    <span className="cf-arrow"> → </span>
                                    <span className="cf-value">{ch.suggested_value != null ? String(ch.suggested_value) : 'provide'}</span>
                                    <span className="cf-reason"> — {ch.reason}</span>
                                  </li>
                                ))}
                              </ul>
                              {cf.outcome_preview && (
                                <div className="counterfactual-preview">
                                  <span className="cf-preview-label">With these changes:</span>{' '}
                                  {cf.outcome_preview.taxable ? 'taxable' : 'exempt'} at {((cf.outcome_preview.rate || 0) * 100).toFixed(2)}%
                                  {response.result.taxable !== cf.outcome_preview.taxable && (
                                    <span className="cf-preview-diff">
                                      {' '}Outcome would flip: {response.result.taxable ? 'Taxable' : 'Exempt'}
                                      {' '}&rarr; {cf.outcome_preview.taxable ? 'Taxable' : 'Exempt'} ({((cf.outcome_preview.rate || 0) * 100).toFixed(2)}%)
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <p className="trace-missing">
                        Full trace was requested but this API did not return a trace. To use full trace:
                      </p>
                      <ol className="trace-missing-steps">
                        <li>Run the CRMS backend locally: <code>uvicorn crms.main:app --reload --port 8000</code> (after migrations and <code>python scripts/seed.py</code>).</li>
                        <li>Set <strong>Base URL</strong> above to <code>http://localhost:8000</code> and Evaluate again.</li>
                      </ol>
                      <p className="trace-missing">Or redeploy your CRMS backend so the live API includes the trace feature.</p>
                    </>
                  )}
                </div>
              )}

              <details>
                <summary>Full JSON response</summary>
                <pre className="response success">{JSON.stringify(response, null, 2)}</pre>
              </details>
            </>
          )}
              {error && (
                <pre className="response error">
                  {JSON.stringify(error, null, 2)}
                </pre>
              )}
            </section>
          )}
        </>
      )}

      {tab === 'scenario' && <ScenarioExplorer apiUrl={apiUrl} apiKey={apiKey} />}
    </>
  )
}

export default App
