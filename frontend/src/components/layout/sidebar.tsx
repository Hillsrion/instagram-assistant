import { useState } from 'react' // Added import
import { Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, BarChart3, Search, Settings } from 'lucide-react'
import { getConversations, createConversation, deleteConversation } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandItem,
} from "@/components/ui/command"
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

export function Sidebar() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false) // Command dialog state

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
    <div className="w-64 border-r bg-muted/10 flex flex-col h-full bg-background">
      <div className="p-3 border-b space-y-3">
        {/* Navigation Items */}
        <div className="space-y-1">
          <Button
            className="w-full justify-start gap-3"
            variant="ghost"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            <Plus className="h-5 w-5" />
            <span>Nouvelle conversation</span>
          </Button>
          
          <Link
            to="/analytics"
            className="block"
          >
            <Button
              variant="ghost"
              className="w-full justify-start gap-3"
            >
              <BarChart3 className="h-5 w-5" />
              <span>Analytics</span>
            </Button>
          </Link>

          <Button
            variant="ghost"
            className="w-full justify-start gap-3"
            onClick={() => setOpen(true)}
          >
            <Search className="h-5 w-5" />
            <span>Rechercher</span>
          </Button>
        </div>

        <CommandDialog open={open} onOpenChange={setOpen}>
          <CommandInput placeholder="Rechercher une conversation..." />
          <CommandList className="h-[40vh]">
            <CommandEmpty>Aucune conversation trouvée.</CommandEmpty>
            {conversations?.map((conv) => (
              <CommandItem
                key={conv.id}
                onSelect={() => {
                  setOpen(false)
                  window.location.href = `/chat/${conv.id}`
                }}
                className="flex flex-col items-start gap-1 p-3"
              >
                <div className="font-medium">{conv.title || "Nouvelle conversation"}</div>
                <div className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
                </div>
              </CommandItem>
            ))}
          </CommandList>
        </CommandDialog>
      </div>
      
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading ? (
            <div className="p-4 text-sm text-muted-foreground text-center">Loading...</div>
          ) : conversations?.length === 0 ? (
            <div className="p-4 text-sm text-muted-foreground text-center">
              No conversations yet
            </div>
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

      <div className="p-3 border-t">
        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-start gap-3"
            >
              <Settings className="h-5 w-5" />
              <span>Réglages</span>
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Réglages</DialogTitle>
              <DialogDescription>
                Configurez vos préférences ici.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <p className="text-sm text-muted-foreground">Les options de configuration seront bientôt disponibles.</p>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
