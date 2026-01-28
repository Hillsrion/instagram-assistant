import { useEffect, useRef, useState, useMemo } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Send, StopCircle, User, Bot, FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { getConversation, getOllamaModels, getParticipants } from '@/lib/api'
import { useChatStream } from '@/hooks/use-chat-stream'
import { SourcesModal } from '@/components/SourcesModal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { FiltersPanel } from '@/components/filters-panel'
import { cn } from '@/lib/utils'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Source, SummarySource } from '@/lib/types'

export const Route = createFileRoute('/chat/$chatId')({
  component: ChatRoute,
})

function ChatRoute() {
  const { chatId } = Route.useParams()
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: conversation, isLoading } = useQuery({
    queryKey: ['conversation', chatId],
    queryFn: () => getConversation(chatId),
    refetchOnWindowFocus: false
  })

  // Load available models
  const { data: modelsData } = useQuery({
    queryKey: ['ollama-models'],
    queryFn: () => getOllamaModels(),
    refetchOnWindowFocus: false
  })

  // Load participants for filter
  const { data: participantsData } = useQuery({
    queryKey: ['participants'],
    queryFn: () => getParticipants(),
    refetchOnWindowFocus: false
  })

  const participantNames = useMemo(() => {
    return participantsData?.map(p => p.name) || []
  }, [participantsData])

  // Chat hook
  const {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamStatus,
    stopStream,
    selectedModel,
    setSelectedModel
  } = useChatStream({ chatId })

  // Sync with initial loaded messages
  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages)
    }
  }, [conversation, setMessages])

  // Set default model when models are loaded
  useEffect(() => {
    if (modelsData?.default_model && !selectedModel) {
      setSelectedModel(modelsData.default_model)
    }
  }, [modelsData, selectedModel, setSelectedModel])

  // Filters State
  const [filterParticipant, setFilterParticipant] = useState<string>('')
  const [filterDateStart, setFilterDateStart] = useState<string>('')
  const [filterDateEnd, setFilterDateEnd] = useState<string>('')

  // Filter Logic
  const filteredMessages = useMemo(() => {
    return messages.filter(msg => {
      // Participant Filter
      // We filter assistant messages based on whether their sources mention the participant
      if (filterParticipant) {
        if (msg.role === 'assistant') {
          const hasParticipantInSources = msg.sources?.some(s => 
            s.participants.some(p => p.toLowerCase().includes(filterParticipant.toLowerCase()))
          )
          const hasParticipantInSummarySources = msg.summary_sources?.some(s => 
            s.participants.some(p => p.toLowerCase().includes(filterParticipant.toLowerCase()))
          )
          
          if (!hasParticipantInSources && !hasParticipantInSummarySources) {
            return false
          }
        }
        // For user messages, we might want to keep them to see the context of the questions asked,
        // or filter them if they mention the participant. 
        // Let's keep them for now to maintain conversation flow, or maybe filter them too?
        // User's request implies they want to see "discussions de mes dm", which are in the sources.
      }

      // Date Filter
      if (filterDateStart || filterDateEnd) {
        const msgDate = new Date(msg.timestamp)
        if (filterDateStart) {
          const start = new Date(filterDateStart)
          if (msgDate < start) return false
        }
        if (filterDateEnd) {
          const end = new Date(filterDateEnd)
          end.setHours(23, 59, 59, 999) // End of day
          if (msgDate > end) return false
        }
      }

      return true
    })
  }, [messages, filterParticipant, filterDateStart, filterDateEnd])

  // Auto-scroll (only if not filtering, or maybe always? If filtering, we might not want to scroll to bottom if we are looking at old messages)
  // Let's keep it simple for now and scroll.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filteredMessages, streamStatus])

  const [sourcesModalOpen, setSourcesModalOpen] = useState(false)
  const [selectedMessageSources, setSelectedMessageSources] = useState<{
    sources: Source[]
    summary_sources: SummarySource[]
  } | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputRef.current?.value) {
      sendMessage(inputRef.current.value)
      inputRef.current.value = ''
    }
  }

  return (
    <div className="flex h-full flex-col relative">
       {/* Header */}
       <div className="border-b p-4 flex items-center justify-between bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10 w-full">
         <div className="flex items-center gap-2">
           <h2 className="font-semibold text-lg">{conversation?.title || 'Chat'}</h2>
           {isLoading && <span className="text-xs text-muted-foreground animate-pulse">Loading...</span>}
         </div>

         {/* Model Selector */}
         {modelsData?.models && modelsData.models.length > 0 && (
           <Select value={selectedModel || modelsData.default_model || ''} onValueChange={setSelectedModel}>
             <SelectTrigger className="w-48">
               <SelectValue placeholder="Select model..." />
             </SelectTrigger>
             <SelectContent>
               {modelsData.models.map((model) => (
                 <SelectItem key={model.name} value={model.name}>
                   {model.name.includes(':') ? model.name : `${model.name}:latest`}
                   {model.name === modelsData.default_model && ' (default)'}
                 </SelectItem>
               ))}
             </SelectContent>
           </Select>
         )}
       </div>

       {/* Filters */}
       <div className="px-4 py-1 border-b bg-muted/5 backdrop-blur-sm z-10 sticky top-0">
          <div className="max-w-3xl mx-auto">
            <FiltersPanel
              participants={participantNames}
              onParticipantChange={setFilterParticipant}
              onDateRangeChange={(start, end) => {
                   setFilterDateStart(start)
                   setFilterDateEnd(end)
              }}
            />
          </div>
       </div>

       {/* Messages Area */}
       <ScrollArea className="flex-1 p-4">
         <div className="max-w-3xl mx-auto space-y-6 pb-20">
           {filteredMessages.map((msg, i) => (
             <div 
               key={i} 
               className={cn(
                 "flex gap-4",
                 msg.role === 'user' ? "flex-row-reverse" : "flex-row"
               )}
             >
               <Avatar className={cn(
                 "h-8 w-8", 
                 msg.role === 'assistant' ? "bg-primary/10" : "bg-muted"
               )}>
                 <AvatarFallback>
                   {msg.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                 </AvatarFallback>
               </Avatar>
               
               <div className={cn(
                 "flex flex-col gap-2 max-w-[80%]",
                 msg.role === 'user' ? "items-end" : "items-start"
               )}>
                 <div className={cn(
                   "rounded-lg px-4 py-3 text-sm",
                   msg.role === 'user' 
                     ? "bg-primary text-primary-foreground" 
                     : "bg-muted/50 border"
                 )}>
                    {msg.role === 'assistant' ? (
                       <div className="prose dark:prose-invert prose-sm max-w-none break-words">
                         <ReactMarkdown>{msg.content}</ReactMarkdown>
                       </div>
                    ) : (
                       <div className="whitespace-pre-wrap">{msg.content}</div>
                    )}
                 </div>

                 {/* Sources */}
                 {((msg.sources && msg.sources.length > 0) || (msg.summary_sources && msg.summary_sources.length > 0)) && (
                   <button
                     onClick={() => {
                       setSelectedMessageSources({
                         sources: msg.sources || [],
                         summary_sources: msg.summary_sources || []
                       })
                       setSourcesModalOpen(true)
                     }}
                     className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 hover:bg-primary/20 text-primary text-xs font-medium transition-colors mt-2"
                   >
                     <FileText className="h-3 w-3" />
                     {(msg.sources?.length || 0) + (msg.summary_sources?.length || 0)} sources
                   </button>
                 )}
               </div>
             </div>
           ))}
           
           {/* Stream Status Indicator */}
           {isStreaming && (
             <div className="flex items-center gap-2 text-xs text-muted-foreground ml-12 animate-pulse">
               <div className="h-2 w-2 rounded-full bg-primary animate-bounce" />
               {streamStatus}
             </div>
           )}
           
           <div ref={scrollRef} />
         </div>
       </ScrollArea>

       {/* Input Area */}
       <div className="p-4 border-t bg-background/95 backdrop-blur">
         <div className="max-w-3xl mx-auto flex gap-2">
           <Input 
             ref={inputRef}
             placeholder="Ask a question about your conversations..."
             className="flex-1"
             onKeyDown={(e) => {
               if (e.key === 'Enter' && !e.shiftKey) {
                 e.preventDefault()
                 handleSubmit(e)
               }
             }}
             disabled={isStreaming}
           />
           {isStreaming ? (
             <Button variant="destructive" size="icon" onClick={stopStream}>
               <StopCircle className="h-4 w-4" />
             </Button>
           ) : (
             <Button size="icon" onClick={handleSubmit} disabled={isLoading}>
               <Send className="h-4 w-4" />
             </Button>
           )}
         </div>
       </div>

       {/* Sources Modal */}
       {selectedMessageSources && (
         <SourcesModal
           sources={selectedMessageSources.sources}
           summaryources={selectedMessageSources.summary_sources}
           open={sourcesModalOpen}
           onOpenChange={setSourcesModalOpen}
         />
       )}
    </div>
  )
}
