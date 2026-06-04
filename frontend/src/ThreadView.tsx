import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchPosts, fetchUsers, fetchThreads, fetchForum } from './api'
import { formatDisplayDate } from './date'

export default function ThreadView() {
  const params = useParams()
  const simId = params.simId ? Number(params.simId) : null
  const threadId = params.threadId ?? null

  const [posts, setPosts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [userMap, setUserMap] = useState<Record<string, { username: string; profile_picture?: string | null; signature?: string | null }>>({})
  const [threadTitle, setThreadTitle] = useState<string | null>(null)
  const [threadSummary, setThreadSummary] = useState<string | null>(null)
  const [forumCreatedDate, setForumCreatedDate] = useState<string | null>(null)

  const toImageSrc = (raw?: string | null) => {
    if (!raw) return null
    if (raw.startsWith('data:')) return raw
    return `data:image/png;base64,${raw}`
  }

  const escapeHtml = (unsafe: string) =>
    unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')

  // Compute an ISO date string from forum creation time + tick offset (hours)
  const tickToIso = (createdTick: number): string | null => {
    if (!forumCreatedDate) return null
    const base = new Date(forumCreatedDate).getTime()
    if (isNaN(base)) return null
    return new Date(base + createdTick * 3_600_000).toISOString()
  }

  useEffect(() => {
    if (!simId || !threadId) return
    let mounted = true
    const load = async () => {
      setLoading(true)
      try {
        const [all, users, threads, forum] = await Promise.all([
          fetchPosts(simId),
          fetchUsers(simId),
          fetchThreads(simId),
          fetchForum(simId),
        ])
        const filtered = (all || []).filter((p: any) => String(p.thread_id) === String(threadId))
        const map: Record<string, { username: string; profile_picture?: string | null; signature?: string | null }> = {}
        ;(users || []).forEach((u: any) => {
          map[String(u.id)] = {
            username: u.username,
            profile_picture: u.profile_picture,
            signature: u.signature ?? null,
          }
        })
        if (!mounted) return
        // Newest first
        setPosts([...filtered].sort((a, b) => (a.created_tick ?? 0) - (b.created_tick ?? 0)))
        setUserMap(map)
        const found = (threads || []).find((t: any) => String(t.id) === String(threadId))
        setThreadTitle(found ? found.title : null)
        setThreadSummary(found?.summary ?? null)
        setForumCreatedDate((forum as any)?.created_date ?? null)
      } catch (err) {
        console.error('failed to load posts', err)
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [simId, threadId])

  if (!simId || !threadId) return <div className="container"><p>Invalid thread</p></div>

  return (
    <div>
      <div className="container">
        <h3>{threadTitle ?? 'Posts'}</h3>
        {threadSummary && (
          <p style={{ color: '#aaa', fontSize: '0.9em', marginTop: -8, marginBottom: 12 }}>{threadSummary}</p>
        )}
        {loading && <p>Loading…</p>}
        <div className="posts-container">
          <ul className="post-list">
            {posts.length === 0 && !loading && <li className="post-empty">No posts yet</li>}
            {posts.map(p => {
              const dateStr = p.created_tick != null
                ? tickToIso(p.created_tick)
                : (p.created_date ?? p.timestamp_created ?? null)
              const sig = userMap[p.author_id]?.signature
              return (
                <li key={p.id} className="post-item">
                  {toImageSrc(userMap[p.author_id]?.profile_picture) ? (
                    <img
                      className="post-avatar"
                      src={toImageSrc(userMap[p.author_id]?.profile_picture) ?? ''}
                      alt={`${userMap[p.author_id]?.username ?? 'User'} avatar`}
                    />
                  ) : (
                    <div className="post-avatar" aria-hidden="true" />
                  )}
                  <div className="post-body">
                    <div style={{ marginBottom: 6 }}>
                      <strong>{userMap[p.author_id]?.username ?? p.author_id}</strong>
                      {' '}
                      <small style={{ color: '#888' }}>{formatDisplayDate(dateStr)}</small>
                    </div>
                    <div dangerouslySetInnerHTML={{ __html: p.content ? escapeHtml(p.content).replace(/\n/g, '<br/>') : '' }} />
                    {sig && (
                      <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px solid #333', color: '#888', fontSize: '0.85em' }}>
                        {sig}
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
