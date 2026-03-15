import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, BarChart3, Search, Settings, Instagram, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
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

export function Sidebar() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false) // Command dialog state
  const [isCollapsed, setIsCollapsed] = useState(false)

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: getConversations
  })

  const createMutation = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      window.location.href = `/chat/${newConv.id}`
    }
  })

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    }
  })

  return (
    <div className={cn(
      "bg-muted/10 flex flex-col h-full bg-background transition-all duration-300 ease-in-out",
      isCollapsed ? "w-[60px]" : "w-64"
    )}>
      {/* New Top Header */}
      <div className={cn(
        "p-4 flex items-center justify-between",
        isCollapsed && "flex-col gap-4 px-0"
      )}>
        {!isCollapsed ? (
          <>
            <div className="flex items-center gap-2 overflow-hidden">
              <Instagram className="h-6 w-6 text-primary shrink-0" />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsCollapsed(true)}
              className="h-8 w-8"
            >
              <PanelLeftClose className="h-5 w-5" />
            </Button>
          </>
        ) : (
          <>
            <Instagram className="h-6 w-6 text-primary shrink-0" />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsCollapsed(false)}
              className="h-8 w-8"
            >
              <PanelLeftOpen className="h-5 w-5" />
            </Button>
          </>
        )}
      </div>

      <div className="p-3 space-y-3">
        {/* Navigation Items */}
        <div className="space-y-1">
          <Button
            className={cn(
              "w-full justify-start gap-3",
              isCollapsed && "justify-center px-0"
            )}
            variant="ghost"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            title={isCollapsed ? "Nouvelle conversation" : undefined}
          >
            <Plus className="h-5 w-5" />
            {!isCollapsed && <span>Nouvelle conversation</span>}
          </Button>
          
          <Link
            to="/analytics"
            className="block"
          >
            <Button
              variant="ghost"
              className={cn(
                "w-full justify-start gap-3",
                isCollapsed && "justify-center px-0"
              )}
              title={isCollapsed ? "Analytics" : undefined}
            >
              <BarChart3 className="h-5 w-5" />
              {!isCollapsed && <span>Analytics</span>}
            </Button>
          </Link>

          <Button
            variant="ghost"
            className={cn(
              "w-full justify-start gap-3",
              isCollapsed && "justify-center px-0"
            )}
            onClick={() => setOpen(true)}
            title={isCollapsed ? "Rechercher" : undefined}
          >
            <Search className="h-5 w-5" />
            {!isCollapsed && <span>Rechercher</span>}
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
              </CommandItem>
            ))}
          </CommandList>
        </CommandDialog>
      </div>
      
      {!isCollapsed ? (
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
      ) : (
        <div className="flex-1" />
      )}

      <div className="p-3">
        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              className={cn(
                "w-full justify-start gap-3",
                isCollapsed && "justify-center px-0"
              )}
              title={isCollapsed ? "Réglages" : undefined}
            >
              <Settings className="h-5 w-5" />
              {!isCollapsed && <span>Réglages</span>}
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
