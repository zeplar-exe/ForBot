import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchModels, fetchAISettings, updateAISettings, fetchSimStatus } from './api'

export default function AISettings() {
    const params = useParams()
    const simId = params.simId ? Number(params.simId) : null
    const navigate = useNavigate()

    const [models, setModels] = useState<string[]>([])
    const [loading, setLoading] = useState(false)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [model, setModel] = useState<string>('')
    const [temperature, setTemperature] = useState<number>(0.7)
    const [top_p, setTopP] = useState<number>(0.9)
    const [top_k, setTopK] = useState<number>(40)
    const [max_tokens, setMaxTokens] = useState<number>(2500)
    const [enableForumRag, setEnableForumRag] = useState<boolean>(false)
    const [enableWebRag, setEnableWebRag] = useState<boolean>(false)
    const [whitelist, setWhitelist] = useState<string[]>([])
    const [whitelistInput, setWhitelistInput] = useState<string>('')
    const [thinking, setThinking] = useState<string>('medium')
    const [running, setRunning] = useState<boolean>(false)
    const [serverGenerating, setServerGenerating] = useState(false)
    const [serverAdvancing, setServerAdvancing] = useState(false)

    // poll simulation status and disable Save when simulation is stopped
    useEffect(() => {
        if (!simId) return
        let mounted = true
        const poll = async () => {
            try {
                const s = await fetchSimStatus(simId)
                if (!mounted) return
                setServerGenerating(s.generating)
                setServerAdvancing(s.advancing)
                setRunning(s.running)
            } catch (e) {
                // ignore
            }
        }
        poll()
        const id = setInterval(poll, 4000)
        return () => { mounted = false; clearInterval(id) }
    }, [simId])

    useEffect(() => {
        if (!simId) return
        let mounted = true
        const load = async () => {
            setLoading(true)
            try {
                const mres = await fetchModels()
                if (!mounted) return
                setModels(mres.models || [])
                try {
                    const cfg = await fetchAISettings(simId)
                    if (!mounted) return
                    setModel(cfg.model || (mres.models && mres.models[0]) || '')
                    setTemperature(typeof cfg.temperature === 'number' ? cfg.temperature : 0.7)
                    setTopP(typeof cfg.top_p === 'number' ? cfg.top_p : 0.9)
                    setTopK(typeof cfg.top_k === 'number' ? cfg.top_k : 40)
                    setMaxTokens(typeof cfg.max_tokens === 'number' ? cfg.max_tokens : 2500)
                    setWhitelist(Array.isArray(cfg.whitelist) ? cfg.whitelist : [])
                    setThinking(typeof cfg.thinking === 'string' ? cfg.thinking : 'medium')
                } catch (e) {
                    // if fetching settings fails, still populate models
                    console.error('failed to fetch ai settings', e)
                }
            } catch (e) {
                console.error('failed to fetch models', e)
                setError('Failed to fetch models from server')
            } finally { if (mounted) setLoading(false) }
        }
        load()
        return () => { mounted = false }
    }, [simId])

    if (!simId) return <div className="container"><p>Invalid simulation id</p></div>

    return (
        <div className="container">
            <h2>AI Settings</h2>
            {loading && <p>Loading…</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Model</span>
                        <button className="hint" title="Choose from ollama models installed on the server">?</button>
                    </div>
                    <select value={model} onChange={e => setModel(e.target.value)} style={{ display: 'block', marginTop: 6 }}>
                        <option value="">(select model)</option>
                        {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Temperature</span>
                        <button className="hint" title="Higher values = more randomness, lower = more deterministic">?</button>
                    </div>
                    <input type="number" step="0.01" min="0" max="1" value={temperature} onChange={e => setTemperature(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>top_p</span>
                        <button className="hint" title="Nucleus sampling cumulative probability">?</button>
                    </div>
                    <input type="number" step="0.01" min="0" max="1" value={top_p} onChange={e => setTopP(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>top_k</span>
                        <button className="hint" title="Top-K sampling: number of tokens to consider">?</button>
                    </div>
                    <input type="number" step="1" min="0" value={top_k} onChange={e => setTopK(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>max_tokens</span>
                        <button className="hint" title="Maximum tokens the model may generate">?</button>
                    </div>
                    <input type="number" step="1" min="1" value={max_tokens} onChange={e => setMaxTokens(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input type="checkbox" checked={enableForumRag} onChange={e => setEnableForumRag(e.target.checked)} />
                        <span>Enable Forum RAG</span>
                    </div>
                    <button className="hint" title="Use the forum content as a retrieval source when answering">?</button>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input type="checkbox" checked={enableWebRag} onChange={e => setEnableWebRag(e.target.checked)} />
                        <span>Enable Web RAG</span>
                    </div>
                    <button className="hint" title="Allow web retrieval (external) when answering">?</button>
                </label>

                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Whitelist</span>
                        <button className="hint" title="Domains or sources allowed for web RAG or extra retrieval">?</button>
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                        <input value={whitelistInput} onChange={e => setWhitelistInput(e.target.value)} placeholder="example.com or domain/path" />
                        <button onClick={() => {
                            const v = (whitelistInput || '').trim()
                            if (!v) return
                            if (!whitelist.includes(v)) setWhitelist([...whitelist, v])
                            setWhitelistInput('')
                        }}>Add</button>
                    </div>
                    <ul style={{ marginTop: 8 }}>
                        {whitelist.map((w, i) => (
                            <li key={w + String(i)}>
                                {w} <button onClick={() => setWhitelist(whitelist.filter(x => x !== w))}>Remove</button>
                            </li>
                        ))}
                    </ul>
                </div>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Thinking</span>
                        <button className="hint" title="Controls depth / deliberation: low, medium, high">?</button>
                    </div>
                    <select value={thinking} onChange={e => setThinking(e.target.value)}>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                    </select>
                </label>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={() => navigate(-1)} disabled={saving}>Cancel</button>
                <button onClick={async () => {
                    setSaving(true)
                    setError(null)
                    try {
                        const payload: any = {
                            model: model || undefined,
                            temperature: Number(temperature),
                            top_p: Number(top_p),
                            top_k: Number(top_k),
                            max_tokens: Number(max_tokens),
                            whitelist: whitelist,
                            thinking: thinking,
                        }
                        await updateAISettings(simId, payload)
                        navigate(`/simulations/${simId}`)
                    } catch (e: any) {
                        console.error('save failed', e)
                        setError(e?.message || 'Save failed')
                    } finally { setSaving(false) }
                }} disabled={saving || serverAdvancing || serverGenerating || !running}>Save</button>
            </div>

        </div>
    )
}
