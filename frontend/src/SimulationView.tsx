import { useEffect, useState, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { fetchForum, fetchThreads, updateForum, fetchUsers, fetchSimStatus, fetchStimuli, createStimulus, deleteStimulus, fetchDocuments, createDocument, deleteDocument, type Stimulus, type SimulationDocument } from './api'
import { formatDisplayDate } from './date'
// Header is now rendered globally in App

export default function SimulationView(){
  const params = useParams()
  const simId = params.simId ? Number(params.simId) : null
  const navigate = useNavigate()
  const [forum, setForum] = useState<{name:string;topic:string;created_date?:string}|null>(null)

  const [threads, setThreads] = useState<any[]>([])
  const [userMap, setUserMap] = useState<Record<string, { username: string; profile_picture?: string | null }>>({})
  const [loading, setLoading] = useState(false)
  const [showEditTopic, setShowEditTopic] = useState(false)
  const [editTopic, setEditTopic] = useState('')
  const [running, setRunning] = useState<boolean>(false)
  const prevAdvancingRef = useRef<boolean>(false)

  // Stimuli state
  const [stimuli, setStimuli] = useState<Stimulus[]>([])
  const [showStimuli, setShowStimuli] = useState(false)
  const [newStimulusText, setNewStimulusText] = useState('')
  const [stimuliLoading, setStimuliLoading] = useState(false)

  // Documents state
  const [documents, setDocuments] = useState<SimulationDocument[]>([])
  const [showDocuments, setShowDocuments] = useState(false)
  const [docLoading, setDocLoading] = useState(false)
  const [newDocTitle, setNewDocTitle] = useState('')
  const [newDocText, setNewDocText] = useState('')
  const [newDocSource, setNewDocSource] = useState('')

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
        setThreads([...(t || [])].sort((a: any, b: any) => (b.created_tick ?? 0) - (a.created_tick ?? 0)))
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
            setThreads([...(t || [])].sort((a: any, b: any) => (b.created_tick ?? 0) - (a.created_tick ?? 0)))
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

  const openStimuli = async () => {
    setShowStimuli(true)
    setStimuliLoading(true)
    try {
      const data = await fetchStimuli(simId)
      setStimuli(data)
    } catch (e) {
      console.error('failed to load stimuli', e)
    } finally {
      setStimuliLoading(false)
    }
  }

  const handleAddStimulus = async () => {
    const text = newStimulusText.trim()
    if (!text) return
    setStimuliLoading(true)
    try {
      const s = await createStimulus(simId, text)
      setStimuli(prev => [...prev, s])
      setNewStimulusText('')
    } catch (e) {
      console.error('failed to add stimulus', e)
      alert('Failed to add stimulus: ' + e)
    } finally {
      setStimuliLoading(false)
    }
  }

  const openDocuments = async () => {
    setShowDocuments(true)
    setDocLoading(true)
    try {
      setDocuments(await fetchDocuments(simId))
    } catch (e) {
      console.error('failed to load documents', e)
    } finally {
      setDocLoading(false)
    }
  }

  const handleAddDocument = async () => {
    if (!newDocTitle.trim() || !newDocText.trim()) return
    setDocLoading(true)
    try {
      const doc = await createDocument(simId, { title: newDocTitle.trim(), text: newDocText.trim(), source: newDocSource.trim() })
      setDocuments(prev => [...prev, doc])
      setNewDocTitle(''); setNewDocText(''); setNewDocSource('')
    } catch (e) {
      console.error('failed to add document', e)
      alert('Failed to add document: ' + e)
    } finally {
      setDocLoading(false)
    }
  }

  const handleDeleteDocument = async (id: string) => {
    setDocLoading(true)
    try {
      await deleteDocument(simId, id)
      setDocuments(prev => prev.filter(d => d.id !== id))
    } catch (e) {
      console.error('failed to delete document', e)
      alert('Failed to delete document: ' + e)
    } finally {
      setDocLoading(false)
    }
  }

  const handleDeleteStimulus = async (id: string) => {
    setStimuliLoading(true)
    try {
      await deleteStimulus(simId, id)
      setStimuli(prev => prev.filter(s => s.id !== id))
    } catch (e) {
      console.error('failed to delete stimulus', e)
      alert('Failed to delete stimulus: ' + e)
    } finally {
      setStimuliLoading(false)
    }
  }

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
        <button onClick={openDocuments}>Documents</button>
      </div>

      <div style={{display:'flex', alignItems:'center', gap:8, marginTop:16}}>
        <h3 style={{margin:0}}>Threads</h3>
        <button
          title="Manage stimuli"
          style={{padding:'2px 10px', fontSize:18, lineHeight:1, cursor:'pointer'}}
          onClick={openStimuli}
        >+</button>
      </div>
      <ul className="sim-list">
        {threads.length === 0 && <li>No threads yet</li>}
        {threads.map((th:any) => (
          <li key={th.id}>
            <Link to={`/simulations/${simId}/threads/${th.id}`}><strong>{th.title}</strong></Link>
            <div className="thread-author-row">
              {toImageSrc(userMap[th.author_id]?.profile_picture) ? (
                <img
                  className="thread-avatar"
                  src={toImageSrc(userMap[th.author_id]?.profile_picture) ?? ''}
                  alt={`${userMap[th.author_id]?.username ?? 'User'} avatar`}
                />
              ) : (
                <div className="thread-avatar" aria-hidden="true" />
              )}
              <span>by {userMap[th.author_id]?.username ?? th.author_id}</span>
            </div>
          </li>
        ))}
      </ul>

      {showDocuments && (
        <div className="modal-backdrop">
          <div className="modal" style={{minWidth:480, maxWidth:620}}>
            <h3>Documents</h3>
            <p style={{marginTop:0, color:'#888', fontSize:13}}>
              Documents injected as context into thread and post generation.
            </p>

            <div style={{maxHeight:240, overflowY:'auto', border:'1px solid #333', borderRadius:6, marginBottom:12}}>
              {docLoading && <p style={{padding:12, margin:0}}>Loading…</p>}
              {!docLoading && documents.length === 0 && (
                <p style={{padding:12, margin:0, color:'#888'}}>No documents yet.</p>
              )}
              {documents.map(d => (
                <div key={d.id} style={{display:'flex', alignItems:'flex-start', gap:8, padding:'8px 12px', borderBottom:'1px solid #222'}}>
                  <div style={{flex:1}}>
                    <div style={{fontWeight:600, fontSize:14}}>{d.title}</div>
                    {d.source && <div style={{fontSize:12, color:'#666'}}>{d.source}</div>}
                    {d.summary && <div style={{fontSize:12, color:'#aaa', marginTop:2}}>{d.summary}</div>}
                  </div>
                  <button
                    style={{padding:'2px 8px', fontSize:12, cursor:'pointer', flexShrink:0}}
                    onClick={() => handleDeleteDocument(d.id)}
                    disabled={docLoading}
                  >✕</button>
                </div>
              ))}
            </div>

            <label style={{display:'block', marginBottom:6}}>
              Title
              <input value={newDocTitle} onChange={e => setNewDocTitle(e.target.value)} placeholder="Document title" style={{display:'block', width:'100%', marginTop:4}} />
            </label>
            <label style={{display:'block', marginBottom:6}}>
              Source <span style={{color:'#666', fontSize:12}}>(optional)</span>
              <input value={newDocSource} onChange={e => setNewDocSource(e.target.value)} placeholder="URL or reference" style={{display:'block', width:'100%', marginTop:4}} />
            </label>
            <label style={{display:'block', marginBottom:8}}>
              Text
              <textarea
                value={newDocText}
                onChange={e => setNewDocText(e.target.value)}
                placeholder="Paste the full document text…"
                style={{display:'block', width:'100%', minHeight:100, resize:'vertical', marginTop:4}}
              />
            </label>
            <div style={{display:'flex', justifyContent:'flex-end', gap:8}}>
              <button onClick={() => { setShowDocuments(false); setNewDocTitle(''); setNewDocText(''); setNewDocSource('') }}>Close</button>
              <button onClick={handleAddDocument} disabled={docLoading || !newDocTitle.trim() || !newDocText.trim()}>
                {docLoading ? 'Summarizing…' : 'Add'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showStimuli && (
        <div className="modal-backdrop">
          <div className="modal" style={{minWidth:420, maxWidth:560}}>
            <h3>Stimuli</h3>
            <p style={{marginTop:0, color:'#888', fontSize:13}}>
              Events injected into thread creation as raw material for users to react to.
            </p>

            <div style={{maxHeight:280, overflowY:'auto', border:'1px solid #333', borderRadius:6, marginBottom:12}}>
              {stimuliLoading && <p style={{padding:12, margin:0}}>Loading…</p>}
              {!stimuliLoading && stimuli.length === 0 && (
                <p style={{padding:12, margin:0, color:'#888'}}>No stimuli yet.</p>
              )}
              {stimuli.map(s => (
                <div key={s.id} style={{display:'flex', alignItems:'flex-start', gap:8, padding:'8px 12px', borderBottom:'1px solid #222'}}>
                  <span style={{flex:1, fontSize:14, whiteSpace:'pre-wrap', wordBreak:'break-word'}}>{s.text}</span>
                  <span style={{color:'#666', fontSize:12, whiteSpace:'nowrap', marginTop:2}}>tick {s.created_tick}</span>
                  <button
                    style={{padding:'2px 8px', fontSize:12, cursor:'pointer', flexShrink:0}}
                    onClick={() => handleDeleteStimulus(s.id)}
                    disabled={stimuliLoading}
                  >✕</button>
                </div>
              ))}
            </div>

            <div style={{display:'flex', gap:8}}>
              <textarea
                value={newStimulusText}
                onChange={e => setNewStimulusText(e.target.value)}
                placeholder="Describe an event or piece of news…"
                style={{flex:1, minHeight:64, resize:'vertical'}}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAddStimulus() }}
              />
            </div>
            <div style={{display:'flex', justifyContent:'flex-end', gap:8, marginTop:8}}>
              <button onClick={() => { setShowStimuli(false); setNewStimulusText('') }}>Close</button>
              <button onClick={handleAddStimulus} disabled={stimuliLoading || !newStimulusText.trim()}>Add</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
