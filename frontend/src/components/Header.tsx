import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchForum, advanceSimulation, fetchSimStatus } from '../api'
import { formatDisplayDate } from '../date'

export default function Header({ simId: propSimId, forumName, onAdvance }: { simId?: number; forumName?: string; onAdvance?: () => void }) {
    const location = useLocation()
    // Attempt to extract simId from props or from the pathname: /simulations/:simId
    const pathnameMatch = location.pathname.match(/^\/simulations\/(\d+)/)
    const simIdFromPath = pathnameMatch ? Number(pathnameMatch[1]) : undefined
    const simId = propSimId ?? simIdFromPath
    const [name, setName] = useState<string | null>(forumName ?? null)
    const [showAdvance, setShowAdvance] = useState(false)
    const [hours, setHours] = useState(1)
    const [loading, setLoading] = useState(false)
    const [serverAdvancing, setServerAdvancing] = useState(false)
    const [serverGenerating, setServerGenerating] = useState(false)
    const [currentTime, setCurrentTime] = useState<string | null>(null)


    useEffect(() => {
        let mounted = true
        if (!name) {
            ; (async () => {
                try {
                    if (!simId) return
                    const f = await fetchForum(simId)
                    if (!mounted) return
                    setName(f.name)
                } catch (e) {
                    console.error('failed to fetch forum name', e)
                }
            })()
        }
        return () => { mounted = false }
    }, [simId])



    const doAdvance = async () => {
        setLoading(true)
        try {
            if (!simId) throw new Error('No simulation selected')
            await advanceSimulation(simId, Number(hours))
            setShowAdvance(false)
            if (onAdvance) onAdvance()
            // dispatch a global event so pages can refresh themselves when header advances time
            try { window.dispatchEvent(new CustomEvent('forbot:advanced', { detail: { simId, hours: Number(hours) } })) } catch (e) { }
        } catch (e) {
            console.error('advance failed', e)
        } finally { setLoading(false) }
    }

    // poll server status to reflect operations that may be happening on server or other clients
    useEffect(() => {
        let mounted = true
        const poll = async () => {
            if (!simId) return
            try {
                const s = await fetchSimStatus(simId)
                if (!mounted) return
                setServerAdvancing(!!s.advancing)
                setServerGenerating(!!s.generating)
                setCurrentTime(s.current_time ?? null)
            } catch (e) {
                // ignore polling errors
            }
        }
        // initial poll
        poll()
        const id = setInterval(poll, 8000)
        return () => { mounted = false; clearInterval(id) }
    }, [simId])

    return (
        <header className="app-header">
            <div className="header-inner" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div>
                    {/* Breadcrumbs: previous pages are links, current page is bold */}
                    <span>
                        <Link to="/">Home</Link>
                    </span>

                    {simId && (
                        <>
                            <span style={{ margin: '0 8px' }}>›</span>
                            {location.pathname === `/simulations/${simId}` || location.pathname === `/simulations/${simId}/` ? (
                                <strong>{name ?? `Simulation #${simId}`}</strong>
                            ) : (
                                <Link to={`/simulations/${simId}`}>{name ?? `Simulation #${simId}`}</Link>
                            )}
                        </>
                    )}

                    {location.pathname.endsWith('/users') && (
                        <>
                            <span style={{ margin: '0 8px' }}>›</span>
                            <strong>Users</strong>
                        </>
                    )}

                    {location.pathname.includes('/threads/') && (
                        <>
                            <span style={{ margin: '0 8px' }}>›</span>
                            <strong>Thread</strong>
                        </>
                    )}

                    {/* current time shown after breadcrumb links */}
                    {currentTime && (
                        <span style={{ marginLeft: 12, marginRight: 6, fontSize: 12, color: '#444' }}>{formatDisplayDate(currentTime)}</span>
                    )}



                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {/* Only show advance controls when a simulation is active */}
                    {simId ? (
                        <>
                            <button onClick={() => !loading && setShowAdvance(s => !s)} disabled={loading || serverAdvancing}>{showAdvance ? 'Close' : 'Advance Time'}</button>
                            {showAdvance && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8 }}>
                                    <input type="number" min={1} value={hours} onChange={e => setHours(Number(e.target.value || 1))} style={{ width: 80 }} disabled={loading} />
                                    <button onClick={doAdvance} disabled={loading || serverAdvancing}>Advance</button>
                                </div>
                            )}
                            {/* show spinner next to the Advance Time toggle so it's visible even when the inline control is closed */}
                            {(loading || serverAdvancing) && <span className="spinner" aria-hidden="true" style={{ marginLeft: 6 }} />}
                        </>
                    ) : null}
                    {/* Users navigation button next to Advance controls */}
                    {simId && (
                        <Link to={`/simulations/${simId}/users`} style={{ marginLeft: 8 }}>
                            <button>
                                Users
                                {serverGenerating && <span className="spinner" aria-hidden="true" style={{ marginLeft: 6 }} />}
                            </button>
                        </Link>
                    )}
                </div>
            </div>
        </header>
    )
}
