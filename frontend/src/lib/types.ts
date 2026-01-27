// Basic types based on the backend API
export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: Source[]
}

export interface Source {
  rank: number
  file: string
  participants: string[]
  date_start: string
  date_end: string
  score: number
  expanded?: boolean
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count?: number
  messages?: Message[]
}

export interface ConversationListResponse {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}
