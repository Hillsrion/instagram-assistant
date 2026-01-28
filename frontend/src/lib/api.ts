import type { Conversation, ConversationListResponse, ChunkDetail } from "./types"

const API_BASE = '/api'

export async function getOllamaModels(): Promise<{ models: Array<{ name: string; size: number; modified_at: string }>; default_model: string }> {
  try {
    const res = await fetch(`${API_BASE}/ollama/models`)
    if (!res.ok) throw new Error('Failed to fetch models')
    return res.json()
  } catch (error) {
    console.error('Error fetching Ollama models:', error)
    return { models: [], default_model: '' }
  }
}

export async function getConversations(): Promise<ConversationListResponse[]> {
  const res = await fetch(`${API_BASE}/conversations`)
  if (!res.ok) throw new Error('Failed to fetch conversations')
  return res.json()
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations/${id}`)
  if (!res.ok) throw new Error('Failed to fetch conversation')
  return res.json()
}

export async function createConversation(title?: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE'
  })
  if (!res.ok) throw new Error('Failed to delete conversation')
}

export async function updateConversation(id: string, title: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
  if (!res.ok) throw new Error('Failed to update conversation')
  return res.json()
}

export async function getChunkContent(chunkId: string): Promise<ChunkDetail> {
  const res = await fetch(`${API_BASE}/chunks/${chunkId}`)
  if (!res.ok) throw new Error('Failed to fetch chunk content')
  return res.json()
}
