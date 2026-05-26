import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchPosts, fetchUsers, fetchThreads } from './api'
import { formatDisplayDate } from './date'

export default function ThreadView() {
  const params = useParams()
  const simId = params.simId ? Number(params.simId) : null
  const threadId = params.threadId ?? null

  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [userMap, setUserMap] = useState<Record<string, { username: string; profile_picture?: string | null }>>({})
  const [threadTitle, setThreadTitle] = useState<string | null>(null)

  const toImageSrc = (raw?: string | null) => {
    if (!raw) return null
    if (raw.startsWith('data:')) return raw
    return `data:image/png;base64,${raw}`
  }

  // escape HTML and convert newlines to <br/> to preserve line breaks safely
  const escapeHtml = (unsafe: string) => {
    return unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
  }

  useEffect(() => {
    if (!simId || !threadId) return
    let mounted = true
    const load = async () => {
      setLoading(true)
      try {
        const [all, users, threads] = await Promise.all([fetchPosts(simId), fetchUsers(simId), fetchThreads(simId)])
        const filtered = (all || []).filter((p: any) => String(p.thread_id) === String(threadId))
        const usersList = users || []
        const map: Record<string, { username: string; profile_picture?: string | null }> = {}
        usersList.forEach((u: any) => { map[String(u.id)] = { username: u.username, profile_picture: u.profile_picture } })
        if (!mounted) return
        setPosts(filtered)
        setUserMap(map)
        const found = (threads || []).find((t: any) => String(t.id) === String(threadId))
        setThreadTitle(found ? found.title : null)
      } catch (err) {
        console.error('failed to load posts', err)
      } finally { setLoading(false) }
    }
    load()
    return () => { mounted = false }
  }, [simId, threadId])

  if (!simId || !threadId) return <div className="container"><p>Invalid thread</p></div>

  return (
    <div>
      <div className="container">
        <h3>{threadTitle ?? 'Posts'}</h3>
        {loading && <p>Loading…</p>}
        <div className="posts-container">
          <ul className="post-list">
            {posts.length === 0 && <li className="post-empty">No posts yet</li>}
            {posts.map(p => (
              <li key={p.id} className="post-item">
                {toImageSrc(userMap[p.author_id]?.profile_picture) ? (
                  <img className="post-avatar" src={toImageSrc(userMap[p.author_id]?.profile_picture) ?? ''} alt={`${userMap[p.author_id]?.username ?? 'User'} avatar`} />
                ) : (
                  <div className="post-avatar" aria-hidden="true" />
                )}
                <div className="post-body">
                  <div style={{ marginBottom: 6 }}><strong>{userMap[p.author_id]?.username ?? p.author_id}</strong> <small>{formatDisplayDate(p.created_date ?? p.timestamp_created)}</small></div>
                  <div dangerouslySetInnerHTML={{ __html: (p.content ? escapeHtml(p.content).replace(/\n/g, '<br/>') : '') }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
