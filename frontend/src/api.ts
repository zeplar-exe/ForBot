const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"

export type SimSummary = { id: number; name: string; users: number; threads: number; posts: number }

export async function fetchSimulations(): Promise<SimSummary[]> {
  const res = await fetch(`${BASE}/simulations`)
  if (!res.ok) throw new Error("Failed to fetch simulations")
  return res.json()
}

export type CreateSimulationPayload = { name?: string; purpose?: string; topic?: string; created_date?: string }

export async function createSimulation(payload?: CreateSimulationPayload): Promise<{ id: number }> {
  const res = await fetch(`${BASE}/simulations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : JSON.stringify({}),
  })
  if (!res.ok) throw new Error("Failed to create simulation")
  return res.json()
}

export async function fetchForum(simId: number): Promise<{ name: string; purpose: string; topic: string; created_date?: string }> {
  const res = await fetch(`${BASE}/simulations/${simId}/forum`)
  if (!res.ok) throw new Error("Failed to fetch forum")
  return res.json()
}

export async function fetchThreads(simId: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/threads`)
  if (!res.ok) throw new Error("Failed to fetch threads")
  return res.json()
}

export async function fetchPosts(simId: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/posts`)
  if (!res.ok) throw new Error("Failed to fetch posts")
  return res.json()
}

export async function advanceSimulation(simId: number, hours: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/advance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours }),
  })
  if (!res.ok) throw new Error('Failed to advance simulation')
  return res.json()
}

export async function updateForum(simId: number, payload: { name?: string; purpose?: string; topic?: string; created_date?: string }){
  const res = await fetch(`${BASE}/simulations/${simId}/forum`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if(!res.ok) throw new Error('Failed to update forum')
  return res.json()
}

export async function fetchUsers(simId: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/users`)
  if (!res.ok) throw new Error('Failed to fetch users')
  return res.json()
}

export async function createUser(simId: number, payload: { username: string; signature?: string; personality?: string; forum_dedication?: number; active_hours?: [number, number] }){
  const res = await fetch(`${BASE}/simulations/${simId}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if(!res.ok) throw new Error('Failed to create user')
  return res.json()
}

export async function updateUser(simId: number, userId: string, payload: any){
  const res = await fetch(`${BASE}/simulations/${simId}/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if(!res.ok) throw new Error('Failed to update user')
  return res.json()
}

export async function deleteUser(simId: number, userId: string){
  const res = await fetch(`${BASE}/simulations/${simId}/users/${userId}`, { method: 'DELETE' })
  if(!res.ok) throw new Error('Failed to delete user')
  return res.json()
}

export async function generateSingleUser(simId: number){
  const res = await fetch(`${BASE}/simulations/${simId}/generate_users`, { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ num_users: 1 }) })
  if(!res.ok) throw new Error('Failed to generate user')
  return res.json()
}

export async function fetchSimStatus(simId: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/status`)
  if(!res.ok) throw new Error('Failed to fetch simulation status')
  return res.json() as Promise<{ generating: boolean; advancing: boolean; current_time?: string }>
}

