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

export async function evaluateTitle(message: string, model?: string): Promise<{ title: string }> {
  const res = await fetch(`${API_BASE}/evaluate-title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, model })
  })
  if (!res.ok) throw new Error('Failed to evaluate title')
  return res.json()
}

export async function getChunkContent(chunkId: string): Promise<ChunkDetail> {
  const res = await fetch(`${API_BASE}/chunks/${chunkId}`)
  if (!res.ok) throw new Error('Failed to fetch chunk content')
  return res.json()
}

export async function getParticipants(): Promise<Array<{ name: string; count: number }>> {
  const res = await fetch(`${API_BASE}/participants`)
  if (!res.ok) throw new Error('Failed to fetch participants')
  return res.json()
}

// ============================================================
// Analytics APIs
// ============================================================

export async function getParticipantStats(): Promise<{ participants: Record<string, any> }> {
  const res = await fetch(`${API_BASE}/analytics/participant_stats`)
  if (!res.ok) throw new Error('Failed to fetch participant stats')
  return res.json()
}

export async function getMessageCount(
  participant?: string,
  start?: string,
  end?: string
): Promise<{ count: number }> {
  const params = new URLSearchParams()
  if (participant) params.append('participant', participant)
  if (start) params.append('start', start)
  if (end) params.append('end', end)

  const res = await fetch(`${API_BASE}/analytics/message_count?${params}`)
  if (!res.ok) throw new Error('Failed to fetch message count')
  return res.json()
}

export async function getConversationTimeline(participant: string): Promise<{ timeline: Array<any> }> {
  const res = await fetch(`${API_BASE}/analytics/conversation_timeline?participant=${encodeURIComponent(participant)}`)
  if (!res.ok) throw new Error('Failed to fetch conversation timeline')
  return res.json()
}

export async function getTopicParticipants(topic: string): Promise<{ participants: string[] }> {
  const res = await fetch(`${API_BASE}/analytics/topic_participants?topic=${encodeURIComponent(topic)}`)
  if (!res.ok) throw new Error('Failed to fetch topic participants')
  return res.json()
}

export async function getConversationParticipants(conversationId: string): Promise<{ participants: Array<any> }> {
  const res = await fetch(`${API_BASE}/analytics/conversation_participants?conversation_id=${encodeURIComponent(conversationId)}`)
  if (!res.ok) throw new Error('Failed to fetch conversation participants')
  return res.json()
}

export async function getDateRange(): Promise<{ date_start: string; date_end: string }> {
  const res = await fetch(`${API_BASE}/analytics/date_range`)
  if (!res.ok) throw new Error('Failed to fetch date range')
  return res.json()
}

export async function getAnalyticsOverview(): Promise<{
  total_messages: number
  total_conversations: number
  total_chunks: number
  total_participants: number
  date_start: string
  date_end: string
}> {
  const res = await fetch(`${API_BASE}/analytics/overview`)
  if (!res.ok) throw new Error('Failed to fetch analytics overview')
  return res.json()
}

export async function getMonthlyTimeline(participant?: string): Promise<{ timeline: Array<any> }> {
  const params = new URLSearchParams()
  if (participant) params.append('participant', participant)

  const res = await fetch(`${API_BASE}/analytics/monthly_timeline?${params}`)
  if (!res.ok) throw new Error('Failed to fetch monthly timeline')
  return res.json()
}

// ============================================================
// Onboarding APIs
// ============================================================

export async function startImport(source_path: string): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/onboarding/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_path })
  })
  if (!res.ok) throw new Error('Failed to start import')
  return res.json()
}

export async function listImportedConversations(): Promise<Array<{
  id: string,
  title: string,
  msg_count: number,
  date_range: string
}>> {
  const res = await fetch(`${API_BASE}/onboarding/conversations`)
  if (!res.ok) throw new Error('Failed to list imported conversations')
  return res.json()
}

export async function startRag(
  min_messages: number = 0,
  force_reset: boolean = false
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/onboarding/rag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filter_config: { min_messages },
      force_reset
    })
  })
  if (!res.ok) throw new Error('Failed to start RAG')
  return res.json()
}

export async function uploadFile(file: File): Promise<{ path: string }> {
  const formData = new FormData()
  formData.append('file', file)
  
  const res = await fetch(`${API_BASE}/onboarding/upload`, {
    method: 'POST',
    body: formData
  })
  if (!res.ok) throw new Error('Failed to upload file')
  return res.json()
}

export async function browseFolder(): Promise<{ path: string | null }> {
  const res = await fetch(`${API_BASE}/onboarding/browse`, {
    method: 'POST'
  })
  if (!res.ok) throw new Error('Failed to open dialog')
  return res.json()
}
