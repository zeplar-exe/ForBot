import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { fetchUsers, createUser, updateUser, generateUsers, fetchSimStatus } from './api'

export default function UsersView() {
    const params = useParams()
    const simId = params.simId ? Number(params.simId) : null
    const [users, setUsers] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [serverAdvancing, setServerAdvancing] = useState(false)
    const [running, setRunning] = useState<boolean>(false)
    const [showCreate, setShowCreate] = useState(false)
    const [editUser, setEditUser] = useState<any | null>(null)
    const [form, setForm] = useState({ username: '', signature: '', personality: '', forum_dedication: 0.5, active_start: 0, active_end: 23 })
    const [generateCount, setGenerateCount] = useState('1')

    const load = async () => {
        if (!simId) return
        setLoading(true)
        try {
            const json = await fetchUsers(simId)
            setUsers(json || [])
        } catch (e) { console.error(e) } finally { setLoading(false) }
    }

    useEffect(() => { load() }, [simId])

    useEffect(() => {
        let mounted = true
        const poll = async () => {
            if (!simId) return
            try {
                const s = await fetchSimStatus(simId)
                if (!mounted) return
                setGenerating(s.generating)
                setServerAdvancing(s.advancing)
                setRunning(s.running)
            } catch (e) { /* ignore */ }
        }
        poll()
        const id = setInterval(poll, 8000)
        return () => { mounted = false; clearInterval(id) }
    }, [simId])

        const prevGeneratingRef = useRef<boolean>(false)
        useEffect(()=>{
            if(prevGeneratingRef.current && !generating){
                load()
            }
            prevGeneratingRef.current = generating
        }, [generating])

    const createManual = async () => {
        if (!simId) return
        setLoading(true)
        try {
            const payload = {
                username: form.username,
                signature: form.signature,
                personality: form.personality,
                forum_dedication: Number(form.forum_dedication),
                active_hours: [Number(form.active_start), Number(form.active_end)] as [number, number]
            }
            await createUser(simId, payload)
            await load()
            setShowCreate(false)
        } catch (e) { console.error(e); alert('create failed') } finally { setLoading(false) }
    }

    const generateN = async () => {
        if (!simId) return
        const count = Math.max(1, parseInt(generateCount) || 1)
        setGenerating(true)
        setLoading(true)
        try {
            await generateUsers(simId, count)
            await load()
        } catch (e) { console.error(e); alert('generate failed') } finally { setLoading(false); setGenerating(false) }
    }

    const saveEdit = async () => {
        if (!simId || !editUser) return
        setLoading(true)
        try {
            const uid = editUser.id
            const payload = {
                username: editUser.username,
                signature: editUser.signature,
                personality: editUser.personality,
                forum_dedication: editUser.forum_dedication,
                active_hours: (editUser.active_hours || []) as [number, number]
            }
            await updateUser(simId, uid, payload)
            await load()
            setEditUser(null)
        } catch (e) { console.error(e); alert('save failed') } finally { setLoading(false) }
    }

    if (!simId) return <div className="container"><p>Invalid simulation</p></div>

    return (
        <div>
            <div className="container full">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <h2>Users</h2>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={() => setShowCreate(true)} disabled={loading || generating || serverAdvancing || !running}>Add User</button>
                        <input
                            type="number"
                            min={1}
                            value={generateCount}
                            onChange={e => setGenerateCount(e.target.value)}
                            disabled={loading || generating || serverAdvancing || !running}
                            style={{ width: 52, textAlign: 'center' }}
                        />
                        <button onClick={generateN} disabled={loading || generating || serverAdvancing || !running}>
                            Generate (LLM)
                            {generating && <span className="spinner" aria-hidden="true" style={{ marginLeft: 6 }} />}
                        </button>
                    </div>
                </div>

                <ul className="sim-list">
                    {users.map(u => (
                        <li key={u.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                            {u.profile_picture && (
                                <img
                                    src={`data:image/png;base64,${u.profile_picture}`}
                                    alt={u.username}
                                    style={{ width: 48, height: 48, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                                />
                            )}
                            <div style={{ flex: 1 }}>
                                <strong>{u.username}</strong> <span>({u.forum_dedication})</span>
                                <div>{u.signature}</div>
                                <div style={{ marginTop: 6 }}>
                                    <button disabled={loading || generating || serverAdvancing || running !== true} onClick={() => setEditUser({ ...u })}>Edit</button>
                                </div>
                            </div>
                        </li>
                    ))}
                </ul>

                {showCreate && (
                    <div className="modal-backdrop">
                        <div className="modal">
                            <h3>Create User</h3>
                            <label>Username<input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label>
                            <label>Signature<input value={form.signature} onChange={e => setForm({ ...form, signature: e.target.value })} /></label>
                            <label>Personality<input value={form.personality} onChange={e => setForm({ ...form, personality: e.target.value })} /></label>
                            <label>Forum dedication<input type="number" step="0.01" value={form.forum_dedication} onChange={e => setForm({ ...form, forum_dedication: Number(e.target.value) })} /></label>
                            <label>Active start<input type="number" value={form.active_start} onChange={e => setForm({ ...form, active_start: Number(e.target.value) })} /></label>
                            <label>Active end<input type="number" value={form.active_end} onChange={e => setForm({ ...form, active_end: Number(e.target.value) })} /></label>
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                                <button onClick={() => setShowCreate(false)}>Cancel</button>
                                <button onClick={createManual}>Create</button>
                            </div>
                        </div>
                    </div>
                )}

                {editUser && (
                    <div className="modal-backdrop">
                        <div className="modal">
                            <h3>Edit User</h3>
                            <label>Username<input value={editUser.username} onChange={e => setEditUser({ ...editUser, username: e.target.value })} /></label>
                            <label>Signature<input value={editUser.signature} onChange={e => setEditUser({ ...editUser, signature: e.target.value })} /></label>
                            <label>Personality<input value={editUser.personality} onChange={e => setEditUser({ ...editUser, personality: e.target.value })} /></label>
                            <label>Forum dedication<input type="number" step="0.01" value={editUser.forum_dedication} onChange={e => setEditUser({ ...editUser, forum_dedication: Number(e.target.value) })} /></label>
                            <label>Active hours (start)<input type="number" value={(editUser.active_hours && editUser.active_hours[0]) || 0} onChange={e => setEditUser({ ...editUser, active_hours: [Number(e.target.value), (editUser.active_hours && editUser.active_hours[1]) || 23] })} /></label>
                            <label>Active hours (end)<input type="number" value={(editUser.active_hours && editUser.active_hours[1]) || 23} onChange={e => setEditUser({ ...editUser, active_hours: [(editUser.active_hours && editUser.active_hours[0]) || 0, Number(e.target.value)] })} /></label>
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                                <button onClick={() => setEditUser(null)}>Cancel</button>
                                <button onClick={saveEdit}>Save</button>
                            </div>
                        </div>
                    </div>
                )}

            </div>
        </div>
    )
}
