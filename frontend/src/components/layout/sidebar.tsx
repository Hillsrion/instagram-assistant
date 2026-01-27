import { Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { getConversations, createConversation, deleteConversation } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

export function Sidebar() {
  const queryClient = useQueryClient()
  
  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: getConversations
  })

  const createMutation = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      // Navigate will be handled by the parent or via router hook if needed
      window.location.href = `/chat/${newConv.id}` // Simple navigation for now
    }
  })

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    }
  })

  return (
    <div className="w-64 border-r bg-muted/10 flex flex-col h-full">
      <div className="p-4 border-b">
        <Button 
          className="w-full justify-start gap-2" 
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>
      
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading ? (
            <div className="p-4 text-sm text-muted-foreground text-center">Loading...</div>
          ) : conversations?.length === 0 ? (
            <div className="p-4 text-sm text-muted-foreground text-center">No conversations yet</div>
          ) : (
            conversations?.map((conv) => (
              <div key={conv.id} className="group flex items-center gap-2 rounded-lg hover:bg-muted/50 transition-colors p-1">
                <Link
                  to="/chat/$chatId"
                  params={{ chatId: conv.id }}
                  className={cn(
                    "flex-1 flex flex-col gap-1 p-2 rounded-md text-sm",
                    "data-[status=active]:bg-muted"
                  )}
                  activeProps={{
                     className: "bg-muted"
                  }}
                >
                  <span className="font-medium truncate">{conv.title || "New Conversation"}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
                  </span>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100"
                  onClick={(e) => {
                    e.preventDefault()
                    if (confirm('Delete this conversation?')) {
                      deleteMutation.mutate(conv.id)
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                </Button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
