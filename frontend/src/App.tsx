import { useEffect, useState } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import './styles.css'
import { fetchSimulations, createSimulation, fetchForum, setSimulationState } from './api'
import { formatDisplayDate } from './date'
import Header from './components/Header'
import ScrollToTop from './ScrollToTop'
import SimulationView from './SimulationView'
import ThreadView from './ThreadView'
import UsersView from './UsersView'
import AISettings from './AISettings'

type Sim = { id: number; users: number; threads: number; posts: number; running?: boolean }

function Home() {
  const [sims, setSims] = useState<Sim[]>([])
  const [simNames, setSimNames] = useState<Record<number, string>>({})
  const [simMeta, setSimMeta] = useState<Record<number, { name: string; created_date?: string }>>({})
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', topic: '' })
  const [formCreatedDate, setFormCreatedDate] = useState<string | undefined>(undefined)


  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const data = await fetchSimulations()
      setSims(data || [])
      // fetch forum names for each simulation (fire in parallel)
      try {
        const metas = await Promise.all((data || []).map(async (s: any) => {
          try {
            const f = await fetchForum(s.id)
            return [s.id, { name: f.name, created_date: f.created_date }] as const
          } catch (e) {
            return [s.id, { name: '' }] as const
          }
        }))
        const map: Record<number, { name: string; created_date?: string }> = {}
        for (const [id, m] of metas) map[id] = m
        setSimMeta(map)
        // also keep backward-compatible simNames mapping
        const nameMap: Record<number, string> = {}
        for (const id of Object.keys(map)) {
          const nid = Number(id)
          nameMap[nid] = map[nid]?.name || ''
        }
        setSimNames(nameMap)
      } catch (e) {
        console.error('failed to load forum names', e)
      }
    } catch (err) {
      console.error('Failed to load simulations', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = () => setShowCreate(true)

  return (
    <div className="container">
      <h1>ForBot — Simulations</h1>

      <div className="controls">
        <button onClick={handleCreate} disabled={loading}>Create Simulation</button>
        <button onClick={load} disabled={loading}>Refresh</button>
      </div>

      {loading && <p>Loading…</p>}

      <ul className="sim-list">
        {sims.length === 0 && !loading && <li>No simulations yet</li>}
        {sims.map(s => (
          <li key={s.id}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
              <div>
                <Link to={`/simulations/${s.id}`}><strong>#{s.id} {simNames[s.id] ? `- ${simNames[s.id]}` : ''}</strong></Link>
                {simMeta[s.id] && simMeta[s.id].created_date && (
                  <div><small>created: {formatDisplayDate(simMeta[s.id].created_date)}</small></div>
                )}
                <div>users: {s.users} • threads: {s.threads} • posts: {s.posts}</div>
              </div>
              <div>
                <button onClick={async ()=>{
                  try{
                    await setSimulationState(s.id, !s.running)
                    await load()
                  }catch(e){ console.error('toggle failed', e); alert('Failed to toggle simulation state: '+(e instanceof Error ? e.message : String(e))) }
                }}>{s.running ? 'Stop' : 'Start'}</button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {showCreate && (
        <div className="modal-backdrop">
          <div className="modal">
            <h2>Create Simulation</h2>
            <label>
              Forum name
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. World of Warcraft Forum" />
              <button className="hint" title="A short name for your forum">?</button>
            </label>

            <label>
              Topic (long answer)
              <textarea value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })} placeholder="Describe the forum topic in more detail" />
              <button className="hint" title="Longer description of the forum topic">?</button>
            </label>

            <label>
              Created date & time
              <input type="datetime-local" value={formCreatedDate ?? ''} onChange={e => setFormCreatedDate(e.target.value)} />
              <button className="hint" title="Optional local date/time for forum created_date">?</button>
            </label>

            <div className="modal-actions">
              <button onClick={() => setShowCreate(false)}>Cancel</button>
              <button onClick={async () => {
                setLoading(true)
                try {
                  const payload: any = { name: form.name, topic: form.topic }
                  if (formCreatedDate) payload.created_date = formCreatedDate
                  const resp = await createSimulation(payload)
                  setShowCreate(false)
                  await load()
                  navigate(`/simulations/${resp.id}`)
                } catch (err) {
                  console.error('create failed', err)
                } finally { setLoading(false) }
              }}>Create & Open</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  return (
    <main className="page-wrapper">
      <ScrollToTop />
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/simulations/:simId" element={<SimulationView />} />
  <Route path="/simulations/:simId/ai-settings" element={<AISettings />} />
        <Route path="/simulations/:simId/threads/:threadId" element={<ThreadView />} />
        <Route path="/simulations/:simId/users" element={<UsersView />} />
      </Routes>
    </main>
  )
}

export default App
