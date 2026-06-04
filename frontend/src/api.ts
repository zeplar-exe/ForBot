const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000"

export type SimSummary = { id: number; name?: string; users: number; threads: number; posts: number; running?: boolean }

export async function fetchSimulations(): Promise<SimSummary[]> {
  const res = await fetch(`${BASE}/simulations`)
  if (!res.ok) throw new Error("Failed to fetch simulations")
  return res.json()
}

export type CreateSimulationPayload = { name?: string; topic?: string; created_date?: string }

export async function createSimulation(payload?: CreateSimulationPayload): Promise<{ id: number }> {
  const res = await fetch(`${BASE}/simulations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : JSON.stringify({}),
  })
  if (!res.ok) throw new Error("Failed to create simulation")
  return res.json()
}

export async function fetchForum(simId: number): Promise<{ name: string; topic: string; created_date?: string }> {
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

export async function updateForum(simId: number, payload: { name?: string; topic?: string; created_date?: string }){
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

export async function fetchModels() {
  const res = await fetch(`${BASE}/models`)
  if (!res.ok) throw new Error('Failed to fetch models')
  return res.json()
}

export async function setSimulationState(simId: number, running: boolean) {
  const res = await fetch(`${BASE}/simulations/${simId}/state`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ running }),
  })
  if(!res.ok) throw new Error('Failed to set simulation state')
  return res.json()
}

export async function runRAG(simId: number, payload: { query: string; source?: string; top_k?: number }){
  const res = await fetch(`${BASE}/simulations/${simId}/rag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if(!res.ok) throw new Error('Failed to run RAG')
  return res.json()
}

export type AISettings = {
  model: string
  temperature: number
  top_p: number
  top_k: number
  frequency_penalty: number
  presence_penalty: number
  whitelist: string[]
  thinking: string
  thread_creation_chance: number
}

export async function fetchAISettings(simId: number): Promise<AISettings> {
  const res = await fetch(`${BASE}/simulations/${simId}/ai_settings`)
  if (!res.ok) throw new Error('Failed to fetch AI settings')
  return res.json()
}

export type AISettingsPayload = {
  model?: string
  temperature?: number
  top_p?: number
  top_k?: number
  frequency_penalty?: number
  presence_penalty?: number
  whitelist?: string[]
  thinking?: string
  thread_creation_chance?: number
}

export async function updateAISettings(simId: number, payload: AISettingsPayload) {
  const res = await fetch(`${BASE}/simulations/${simId}/ai_settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if(!res.ok) throw new Error('Failed to update AI settings')
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

export async function generateUsers(simId: number, count: number = 1){
  const res = await fetch(`${BASE}/simulations/${simId}/generate_users`, { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ num_users: count }) })
  if(!res.ok) throw new Error('Failed to generate users')
  return res.json()
}

export async function fetchSimStatus(simId: number) {
  const res = await fetch(`${BASE}/simulations/${simId}/status`)
  if(!res.ok) throw new Error('Failed to fetch simulation status')
  return res.json() as Promise<{ generating: boolean; advancing: boolean; current_time?: string; running: boolean }>
}

export type Stimulus = { id: string; text: string; created_tick: number }

export async function fetchStimuli(simId: number): Promise<Stimulus[]> {
  const res = await fetch(`${BASE}/simulations/${simId}/stimuli`)
  if (!res.ok) throw new Error('Failed to fetch stimuli')
  return res.json()
}

export async function createStimulus(simId: number, text: string): Promise<Stimulus> {
  const res = await fetch(`${BASE}/simulations/${simId}/stimuli`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error('Failed to create stimulus')
  return res.json()
}

export async function deleteStimulus(simId: number, stimulusId: string): Promise<void> {
  const res = await fetch(`${BASE}/simulations/${simId}/stimuli/${stimulusId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Failed to delete stimulus')
}

export type SimulationDocument = { id: string; title: string; text: string; source: string; summary: string }

export async function fetchDocuments(simId: number): Promise<SimulationDocument[]> {
  const res = await fetch(`${BASE}/simulations/${simId}/documents`)
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}

export async function createDocument(simId: number, payload: { title: string; text: string; source?: string }): Promise<SimulationDocument> {
  const res = await fetch(`${BASE}/simulations/${simId}/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('Failed to create document')
  return res.json()
}

export async function deleteDocument(simId: number, docId: string): Promise<void> {
  const res = await fetch(`${BASE}/simulations/${simId}/documents/${docId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete document')
}

