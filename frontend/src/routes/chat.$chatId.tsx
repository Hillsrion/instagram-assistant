import { useEffect, useRef, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Send, StopCircle, User, Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { getConversation } from '@/lib/api'
import { useChatStream } from '@/hooks/use-chat-stream'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

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

  // Chat hook
  const { 
    messages, 
    setMessages, 
    sendMessage, 
    isStreaming, 
    streamStatus, 
    stopStream 
  } = useChatStream({ chatId })

  // Sync with initial loaded messages
  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages)
    }
  }, [conversation, setMessages])

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamStatus])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputRef.current?.value) {
      sendMessage(inputRef.current.value)
      inputRef.current.value = ''
    }
  }

  // Source viewer
  const SourceChip = ({ source }: { source: any }) => {
    const [open, setOpen] = useState(false)
    
    // Fetch full chunk on open if needed, or rely on what we have
    // Usually we need to fetch /api/chunks/{chunk_id} to get full content if not present
    // For now we'll just show what's in the source object + a placeholder if preview missing

    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <button className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs hover:bg-muted/80 transition-colors mx-0.5 align-middle">
             <span className="font-bold text-primary">[{source.rank}]</span>
             <span className="truncate max-w-[100px]">{source.file}</span>
          </button>
        </DialogTrigger>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Source #{source.rank}: {source.file}</DialogTitle>
            <DialogDescription>
              {(source.participants || []).join(', ')} • {source.date_start}
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="flex-1 mt-4 p-4 border rounded-md bg-muted/20">
             <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed">
               {/* In a real app we'd fetch the full content here */}
               {source.preview || "Detailed content not available in this view."}
             </pre>
          </ScrollArea>
          <div className="text-xs text-muted-foreground mt-2">
            Confidence: {Math.round(source.score * 100)}%
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <div className="flex h-full flex-col relative">
       {/* Header */}
       <div className="border-b p-4 flex items-center justify-between bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-10 w-full">
         <div className="flex items-center gap-2">
           <h2 className="font-semibold text-lg">{conversation?.title || 'Chat'}</h2>
           {isLoading && <span className="text-xs text-muted-foreground animate-pulse">Loading...</span>}
         </div>
       </div>

       {/* Messages Area */}
       <ScrollArea className="flex-1 p-4">
         <div className="max-w-3xl mx-auto space-y-6 pb-20">
           {messages.map((msg, i) => (
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
                 {msg.sources && msg.sources.length > 0 && (
                   <div className="flex flex-wrap gap-2 mt-1">
                     {msg.sources.map((source, idx) => (
                       <SourceChip key={idx} source={source} />
                     ))}
                   </div>
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
    </div>
  )
}
