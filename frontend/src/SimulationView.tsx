import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { fetchForum, fetchThreads, updateForum, fetchUsers } from './api'
import { formatDisplayDate } from './date'
// Header is now rendered globally in App

export default function SimulationView(){
  const params = useParams()
  const simId = params.simId ? Number(params.simId) : null
  const navigate = useNavigate()
  const [forum, setForum] = useState<{name:string;purpose:string;topic:string}|null>(null)
  const [forumCreatedDate, setForumCreatedDate] = useState<string | undefined>(undefined)
  const [threads, setThreads] = useState<any[]>([])
  const [userMap, setUserMap] = useState<Record<string,string>>({})
  const [loading, setLoading] = useState(false)
  const [showEditTopic, setShowEditTopic] = useState(false)
  const [editTopic, setEditTopic] = useState('')

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
  const map: Record<string,string> = {}
  usersList.forEach((u:any) => { map[String(u.id)] = u.username })
        if(!mounted) return
        setForum(f)
        // convert ISO to datetime-local value
        const toDatetimeLocal = (iso?: string | null) => {
          if(!iso) return ''
          const d = new Date(iso)
          const pad = (n:number)=>n.toString().padStart(2,'0')
          return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
        }
        setForumCreatedDate(toDatetimeLocal((f as any).created_date))
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

  useEffect(()=>{
    const onAdvanced = (e: any) => {
      if(!simId) return
      if(e?.detail?.simId !== simId) return
      ;(async ()=>{ setLoading(true); try{ const t = await fetchThreads(simId); setThreads(t || []) }catch(e){console.error(e)}finally{setLoading(false)} })()
    }
    window.addEventListener('forbot:advanced', onAdvanced)
    return ()=> window.removeEventListener('forbot:advanced', onAdvanced)
  }, [simId])

  return (
    <div className="container">
      {loading && <p>Loading simulation…</p>}
      {forum && (
        <div>
          <h2>{forum.name}</h2>
          <p><strong>Purpose:</strong> {forum.purpose}</p>
          {forum && ((forum as any).created_date) && <p><strong>Created:</strong> {formatDisplayDate((forum as any).created_date)}</p>}
          <p><strong>Topic:</strong> <span style={{cursor:'pointer',textDecoration:'underline'}} onClick={()=>{ setEditTopic(forum.topic || ''); setShowEditTopic(true) }}>{forum.topic && forum.topic.length > 160 ? forum.topic.slice(0,160) + '…' : forum.topic}</span></p>
          {showEditTopic && (
            <div className="modal-backdrop">
              <div className="modal">
                <h3>Edit Topic</h3>
                <textarea value={editTopic} onChange={e=>setEditTopic(e.target.value)} style={{minHeight:120}} />
                <label style={{marginTop:8}}>
                  Created date & time
                  <input type="datetime-local" value={forumCreatedDate ?? ''} onChange={e=>setForumCreatedDate(e.target.value)} />
                </label>
                <div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:12}}>
                  <button onClick={()=>setShowEditTopic(false)}>Cancel</button>
                  <button onClick={async ()=>{
                    setLoading(true)
                    try{
                      await updateForum(simId, { topic: editTopic, created_date: forumCreatedDate })
                      setForum({...forum, topic: editTopic})
                      setShowEditTopic(false)
                    }catch(e){ console.error('update failed', e); alert('Update failed: '+e) }
                    finally{ setLoading(false) }
                  }}>Save</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

  <h3>Threads</h3>
      <ul className="sim-list">
        {threads.length === 0 && <li>No threads yet</li>}
        {threads.map((th:any) => (
          <li key={th.id}>
            <Link to={`/simulations/${simId}/threads/${th.id}`}><strong>{th.title}</strong></Link>
            <div>by {userMap[th.author] ?? th.author}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
