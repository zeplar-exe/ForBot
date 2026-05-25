import { useEffect, useState, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { fetchForum, fetchThreads, updateForum, fetchUsers, fetchSimStatus } from './api'
import { formatDisplayDate } from './date'
// Header is now rendered globally in App

export default function SimulationView(){
  const params = useParams()
  const simId = params.simId ? Number(params.simId) : null
  const navigate = useNavigate()
  const [forum, setForum] = useState<{name:string;topic:string}|null>(null)
  
  const [threads, setThreads] = useState<any[]>([])
  const [userMap, setUserMap] = useState<Record<string, { username: string; profile_picture?: string | null }>>({})
  const [loading, setLoading] = useState(false)
  const [showEditTopic, setShowEditTopic] = useState(false)
  const [editTopic, setEditTopic] = useState('')
  const [running, setRunning] = useState<boolean>(false)
  const prevAdvancingRef = useRef<boolean>(false)

  const toImageSrc = (raw?: string | null) => {
    if (!raw) return null
    if (raw.startsWith('data:')) return raw
    return `data:image/png;base64,${raw}`
  }

  useEffect(()=>{
    if(!simId) return
    let mounted = true
    const load = async ()=>{
      setLoading(true)
      try{
        const f = await fetchForum(simId)
        const t = await fetchThreads(simId)
  const users = await fetchUsers(simId)
  const usersList = users || []
        const map: Record<string, { username: string; profile_picture?: string | null }> = {}
        usersList.forEach((u:any) => { map[String(u.id)] = { username: u.username, profile_picture: u.profile_picture } })
        if(!mounted) return
        setForum(f)
        // ignore created_date here — not editable from this modal
        setThreads(t || [])
        setUserMap(map)
      }catch(err){
        console.error('failed to load simulation view', err)
      }finally{ setLoading(false) }
    }
    load()
    return ()=>{ mounted = false }
  }, [simId])

  if(!simId) return <div className="container"><p>Invalid simulation id</p></div>

  // Poll server status (generating/advancing/running) and refresh threads when advancing finishes
  useEffect(() => {
    let mounted = true
    const poll = async () => {
      if (!simId) return
      try {
        const s = await fetchSimStatus(simId)
        if (!mounted) return
        setRunning(s.running)

        // if advancing transitioned from true -> false, reload threads
        if (prevAdvancingRef.current && !s.advancing) {
          try {
            setLoading(true)
            const t = await fetchThreads(simId)
            if (!mounted) return
            setThreads(t || [])
          } catch (e) {
            console.error('failed to refresh threads after advancing', e)
          } finally {
            setLoading(false)
          }
        }
        prevAdvancingRef.current = !!s.advancing
      } catch (e) {
        // ignore polling errors
      }
    }
    poll()
    const id = setInterval(poll, 4000)
    return () => { mounted = false; clearInterval(id) }
  }, [simId])

  return (
    <div className="container">
      {loading && <p>Loading simulation…</p>}
      {forum && (
        <div>
          <h2>{forum.name}</h2>
          {forum && ((forum as any).created_date) && <p><strong>Created:</strong> {formatDisplayDate((forum as any).created_date)}</p>}
          <p>
            <strong>Topic:</strong>{' '}
            <span
              style={{ cursor: !running ? 'not-allowed' : 'pointer', textDecoration: 'underline', opacity: !running ? 0.6 : 1 }}
              onClick={() => { if (!running) return; setEditTopic(forum.topic || ''); setShowEditTopic(true) }}
            >{forum.topic && forum.topic.length > 160 ? forum.topic.slice(0,160) + '…' : forum.topic}</span>
          </p>
          {showEditTopic && (
            <div className="modal-backdrop">
              <div className="modal">
                <h3>Edit Topic</h3>
                <textarea value={editTopic} onChange={e=>setEditTopic(e.target.value)} style={{minHeight:120}} />
                <p style={{marginTop:8}}><small>Note: creation date cannot be edited here.</small></p>
                <div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:12}}>
                  <button onClick={()=>setShowEditTopic(false)}>Cancel</button>
                  <button onClick={async ()=>{
                    setLoading(true)
                    try{
                      // only send topic when editing — creation date is not editable here
                      await updateForum(simId, { topic: editTopic })
                      setForum({...forum, topic: editTopic})
                      setShowEditTopic(false)
                    }catch(e){ console.error('update failed', e); alert('Update failed: '+e) }
                    finally{ setLoading(false) }
                  }} disabled={!running || loading}>Save</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{marginTop:8, display:'flex', gap:8}}>
        <button onClick={()=>navigate(`/simulations/${simId}/ai-settings`)}>AI Settings</button>
        <button onClick={()=>navigate(`/simulations/${simId}/users`)}>Users</button>
      </div>

  <h3>Threads</h3>
      <ul className="sim-list">
        {threads.length === 0 && <li>No threads yet</li>}
        {threads.map((th:any) => (
          <li key={th.id}>
            <Link to={`/simulations/${simId}/threads/${th.id}`}><strong>{th.title}</strong></Link>
            <div className="thread-author-row">
              {toImageSrc(userMap[th.author]?.profile_picture) ? (
                <img
                  className="thread-avatar"
                  src={toImageSrc(userMap[th.author]?.profile_picture) ?? ''}
                  alt={`${userMap[th.author]?.username ?? 'User'} avatar`}
                />
              ) : (
                <div className="thread-avatar" aria-hidden="true" />
              )}
              <span>by {userMap[th.author]?.username ?? th.author}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
