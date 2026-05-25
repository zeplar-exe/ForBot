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
    const [topP, setTopP] = useState<number>(0.9)
    const [topK, setTopK] = useState<number>(40)
    const [frequencyPenalty, setFrequencyPenalty] = useState<number>(0.0)
    const [presencePenalty, setPresencePenalty] = useState<number>(0.0)
    const [whitelist, setWhitelist] = useState<string[]>([])
    const [whitelistInput, setWhitelistInput] = useState<string>('')
    const [thinking, setThinking] = useState<string>('medium')
    const [threadCreationChance, setThreadCreationChance] = useState<number>(0.25)
    const [running, setRunning] = useState<boolean>(false)
    const [serverGenerating, setServerGenerating] = useState(false)
    const [serverAdvancing, setServerAdvancing] = useState(false)

    useEffect(() => {
        if (!simId) return
        let mounted = true
        const poll = async () => {
            const s = await fetchSimStatus(simId)
            if (!mounted) return
            setServerGenerating(s.generating)
            setServerAdvancing(s.advancing)
            setRunning(s.running)
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
                const [mres, cfg] = await Promise.all([fetchModels(), fetchAISettings(simId)])
                if (!mounted) return
                setModels(mres.models || [])
                setModel(cfg.model || (mres.models && mres.models[0]) || '')
                setTemperature(cfg.temperature ?? 0.7)
                setTopP(cfg.top_p ?? 0.9)
                setTopK(cfg.top_k ?? 40)
                setFrequencyPenalty(cfg.frequency_penalty ?? 0.0)
                setPresencePenalty(cfg.presence_penalty ?? 0.0)
                setWhitelist(Array.isArray(cfg.whitelist) ? cfg.whitelist : [])
                setThinking(cfg.thinking ?? 'medium')
                setThreadCreationChance(cfg.thread_creation_chance ?? 0.25)
            } catch (e) {
                console.error('failed to load AI settings', e)
                setError('Failed to load settings from server')
            } finally {
                if (mounted) setLoading(false)
            }
        }
        load()
        return () => { mounted = false }
    }, [simId])

    if (!simId) return <div className="container"><p>Invalid simulation id</p></div>

    const isBusy = saving || serverAdvancing || serverGenerating || !running

    return (
        <div className="container">
            <h2>AI Settings</h2>
            {loading && <p>Loading…</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Model</span>
                        <button className="hint" title="Cloud models (openai/, anthropic/) or locally-installed Ollama models">?</button>
                    </div>
                    <select value={model} onChange={e => setModel(e.target.value)} style={{ display: 'block', marginTop: 6 }}>
                        <option value="">(select model)</option>
                        {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Temperature</span>
                        <button className="hint" title="Higher = more random output, lower = more deterministic. Range: 0–2">?</button>
                    </div>
                    <input type="number" step="0.01" min="0" max="2" value={temperature} onChange={e => setTemperature(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>top_p</span>
                        <button className="hint" title="Nucleus sampling: only consider tokens whose cumulative probability ≤ top_p">?</button>
                    </div>
                    <input type="number" step="0.01" min="0" max="1" value={topP} onChange={e => setTopP(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>top_k</span>
                        <button className="hint" title="Top-K sampling: number of candidate tokens to consider (Anthropic / Ollama)">?</button>
                    </div>
                    <input type="number" step="1" min="0" value={topK} onChange={e => setTopK(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Frequency Penalty</span>
                        <button className="hint" title="Reduces repetition of token sequences already seen. Range: −2 to 2 (OpenAI)">?</button>
                    </div>
                    <input type="number" step="0.01" min="-2" max="2" value={frequencyPenalty} onChange={e => setFrequencyPenalty(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Presence Penalty</span>
                        <button className="hint" title="Encourages the model to talk about new topics. Range: −2 to 2 (OpenAI)">?</button>
                    </div>
                    <input type="number" step="0.01" min="-2" max="2" value={presencePenalty} onChange={e => setPresencePenalty(Number(e.target.value))} />
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Thinking</span>
                        <button className="hint" title="Controls reasoning depth for models that support extended thinking: low, medium, high">?</button>
                    </div>
                    <select value={thinking} onChange={e => setThinking(e.target.value)}>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                    </select>
                </label>

                <label style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Thread Creation Chance</span>
                        <button className="hint" title="Probability (0–1) that a user creates a new thread each time they are active">?</button>
                    </div>
                    <input type="number" step="0.01" min="0" max="1" value={threadCreationChance} onChange={e => setThreadCreationChance(Number(e.target.value))} />
                </label>

                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Whitelist</span>
                        <button className="hint" title="Domains or sources allowed for retrieval">?</button>
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                        <input value={whitelistInput} onChange={e => setWhitelistInput(e.target.value)} placeholder="example.com" />
                        <button onClick={() => {
                            const v = whitelistInput.trim()
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
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={() => navigate(-1)} disabled={saving}>Cancel</button>
                <button onClick={async () => {
                    setSaving(true)
                    setError(null)
                    try {
                        await updateAISettings(simId, {
                            model: model || undefined,
                            temperature,
                            top_p: topP,
                            top_k: topK,
                            frequency_penalty: frequencyPenalty,
                            presence_penalty: presencePenalty,
                            whitelist,
                            thinking,
                            thread_creation_chance: threadCreationChance,
                        })
                        navigate(`/simulations/${simId}`)
                    } catch (e: any) {
                        console.error('save failed', e)
                        setError(e?.message || 'Save failed')
                    } finally {
                        setSaving(false)
                    }
                }} disabled={isBusy}>Save</button>
            </div>
        </div>
    )
}
