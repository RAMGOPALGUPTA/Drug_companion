import { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Classification = 'positive' | 'negative' | 'inconclusive';
type Case = {
  id: string;
  classification: Classification;
  confidence: number;
  operator_id: string;
  model_version: string;
  captured_at: string;
};
type Summary = {
  total: number;
  positive: number;
  negative: number;
  inconclusive: number;
  average_confidence: number;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const emptySummary: Summary = { total: 0, positive: 0, negative: 0, inconclusive: 0, average_confidence: 0 };

function title(value: string) {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function App() {
  const [cases, setCases] = useState<Case[]>([]);
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [filter, setFilter] = useState<'all' | Classification>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ limit: '100' });
    if (filter !== 'all') params.set('classification', filter);
    try {
      const [caseResponse, summaryResponse] = await Promise.all([
        fetch(`${apiBase}/api/v1/cases?${params}`),
        fetch(`${apiBase}/api/v1/cases/summary`),
      ]);
      if (!caseResponse.ok || !summaryResponse.ok) throw new Error('The API is not available.');
      setCases(await caseResponse.json() as Case[]);
      setSummary(await summaryResponse.json() as Summary);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load records.');
      setCases([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SIH · digital companion</p>
          <h1>Field testing operations</h1>
          <p className="subtle">Review synchronized presumptive-test records. Results are not laboratory confirmation.</p>
        </div>
        <button className="refresh" onClick={() => void refresh()} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh records'}</button>
      </header>

      <section className="stat-grid" aria-label="Case summary">
        <Stat label="Total records" value={summary.total} tone="neutral" />
        <Stat label="Positive" value={summary.positive} tone="positive" />
        <Stat label="Negative" value={summary.negative} tone="negative" />
        <Stat label="Inconclusive" value={summary.inconclusive} tone="warning" />
        <Stat label="Average confidence" value={`${(summary.average_confidence * 100).toFixed(1)}%`} tone="neutral" />
      </section>

      <section className="records-card">
        <div className="records-heading">
          <div><h2>Recent records</h2><p>{filter === 'all' ? 'Showing the latest 100 captures' : `Showing ${filter} captures`}</p></div>
          <label>Result filter
            <select value={filter} onChange={(event) => setFilter(event.target.value as 'all' | Classification)}>
              <option value="all">All results</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="inconclusive">Inconclusive</option>
            </select>
          </label>
        </div>

        {error && <p className="error" role="alert">{error} Start the API with Docker and try again.</p>}
        {!error && !loading && cases.length === 0 && <p className="empty">No records have synchronized yet.</p>}
        {!error && cases.length > 0 && <div className="table-scroll"><table>
          <thead><tr><th>Case</th><th>Result</th><th>Confidence</th><th>Model</th><th>Operator</th><th>Captured</th></tr></thead>
          <tbody>{cases.map((item) => <tr key={item.id}>
            <td className="case-id" title={item.id}>{item.id.slice(0, 8)}</td>
            <td><span className={`badge ${item.classification}`}>{title(item.classification)}</span></td>
            <td>{(item.confidence * 100).toFixed(1)}%</td>
            <td>{item.model_version}</td>
            <td>{item.operator_id}</td>
            <td>{new Date(item.captured_at).toLocaleString()}</td>
          </tr>)}</tbody>
        </table></div>}
      </section>
    </main>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone: string }) {
  return <article className={`stat ${tone}`}><p>{label}</p><strong>{value}</strong></article>;
}

createRoot(document.getElementById('root')!).render(<App />);
