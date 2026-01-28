import { useState, useCallback, useRef } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { Message } from '@/lib/types'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'

interface UseChatStreamProps {
  chatId: string
  onFinish?: () => void
}

export function useChatStream({ chatId, onFinish }: UseChatStreamProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const abortController = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (content: string, mode: string = 'regular') => {
    if (!content.trim()) return

    // Add user message
    const userMsg: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMsg])
    setIsStreaming(true)
    setStreamStatus('Initializing...')

    // Prepare assistant message placeholder
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }])

    abortController.current = new AbortController()

    try {
      await fetchEventSource('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          conversation_id: chatId,
          model: selectedModel,
          mode: mode
        }),
        signal: abortController.current.signal,
        onmessage(ev) {
          const data = JSON.parse(ev.data)

          if (data.type === 'progress') {
            setStreamStatus(data.message)
          } else if (data.type === 'chunk') {
            setMessages(prev => {
              const last = prev[prev.length - 1]
              if (last.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + data.content }
                ]
              }
              return prev
            })
          } else if (data.type === 'sources') {
             setMessages(prev => {
              const last = prev[prev.length - 1]
              if (last.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  {
                    ...last,
                    sources: data.sources,
                    summary_sources: data.summary_sources || []
                  }
                ]
              }
              return prev
            })
          } else if (data.type === 'done') {
            setIsStreaming(false)
            setStreamStatus('')
            queryClient.invalidateQueries({ queryKey: ['conversations'] })
            if (onFinish) onFinish()
          } else if (data.error) {
            throw new Error(data.error)
          }
        },
        onerror(err) {
          console.error('Stream error:', err)
          toast.error('Failed to send message')
          setIsStreaming(false)
          setStreamStatus('')
        }
      })
    } catch (error) {
      console.error('Fetch error:', error)
      setIsStreaming(false)
    }
  }, [chatId, queryClient, onFinish, selectedModel])

  const stopStream = useCallback(() => {
    if (abortController.current) {
      abortController.current.abort()
      abortController.current = null
      setIsStreaming(false)
      setStreamStatus('Stopped')
    }
  }, [])

  return {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
    selectedModel,
    setSelectedModel
  }
}
