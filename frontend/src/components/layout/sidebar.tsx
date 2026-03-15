import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useMatchRoute } from "@tanstack/react-router";
import {
  BarChart3,
  Instagram,
  MoreVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Star,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  createConversation,
  deleteConversation,
  getConversations,
  updateConversation,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false); // Command dialog state
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: getConversations,
  });

  const createMutation = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (newConv: any) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      window.location.href = `/chat/${newConv.id}`;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: ({ id, is_favorite }: { id: string; is_favorite: boolean }) =>
      updateConversation(id, { is_favorite: !is_favorite }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const matchRoute = useMatchRoute();

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-gray-50 transition-all duration-300 ease-in-out border-r border-gray-200 shrink-0 overflow-hidden",
        isCollapsed ? "w-[60px]" : "w-64 min-w-0 max-w-64",
      )}
    >
      {/* New Top Header */}
      <div
        className={cn(
          "p-4 flex items-center justify-between",
          isCollapsed && "flex-col gap-4 px-0",
        )}
      >
        {!isCollapsed ? (
          <>
            <div className="flex items-center gap-2 overflow-hidden">
              <Instagram className="h-5 w-5 text-primary shrink-0" />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsCollapsed(true)}
              className="h-8 w-8"
            >
              <PanelLeftClose className="h-6 w-6" />
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

      <div className="p-2 space-y-2">
        {/* Navigation Items */}
        <div className="space-y-1">
          <Button
            className={cn(
              "w-full justify-start gap-3 text-sm",
              isCollapsed && "justify-center px-0",
            )}
            variant="ghost"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            title={isCollapsed ? "Nouvelle conversation" : undefined}
          >
            <Plus className="h-5 w-5" />
            {!isCollapsed && <span>Nouvelle conversation</span>}
          </Button>

          <Link to="/analytics" className="block">
            <Button
              variant="ghost"
              className={cn(
                "w-full justify-start gap-3",
                isCollapsed && "justify-center px-0",
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
              isCollapsed && "justify-center px-0",
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
                  setOpen(false);
                  window.location.href = `/chat/${conv.id}`;
                }}
                className="flex flex-col items-start gap-1 p-3"
              >
                <div className="font-medium truncate w-full text-left">
                  {conv.title || "Nouvelle conversation"}
                </div>
              </CommandItem>
            ))}
          </CommandList>
        </CommandDialog>
      </div>

      {!isCollapsed ? (
        <div className="flex-1 w-full min-w-0 overflow-y-auto">
          <div className="p-2 w-full min-w-0 flex flex-col">
            {" "}
            {/* Favorites Section */}
            {conversations?.some((c) => c.is_favorite) && (
              <>
                <div className="px-2 py-2 text-xs font-medium text-muted-foreground flex items-center gap-2 shrink-0">
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  Favoris
                </div>
                <div className="flex flex-col mb-4">
                  {conversations
                    ?.filter((c) => c.is_favorite)
                    .map((conv) => {
                      const isActive = matchRoute({
                        to: "/chat/$chatId",
                        params: { chatId: conv.id },
                        fuzzy: false,
                      });
                      const isMenuOpen = openMenuId === conv.id;

                      return (
                        <div
                          key={conv.id}
                          className={cn(
                            "group relative flex items-center rounded-lg hover:bg-muted/50 transition-colors p-1 min-w-0 w-full overflow-hidden shrink-0",
                            isActive && "bg-muted",
                          )}
                        >
                          <Link
                            to="/chat/$chatId"
                            params={{ chatId: conv.id }}
                            className="flex-1 basis-0 min-w-0 overflow-hidden p-1.5 rounded-md text-sm"
                          >
                            <div className="font-medium truncate block w-full">
                              {conv.title || "New Conversation"}
                            </div>
                          </Link>

                          <DropdownMenu
                            onOpenChange={(isOpen) =>
                              setOpenMenuId(isOpen ? conv.id : null)
                            }
                          >
                            <DropdownMenuTrigger asChild>
                              <div
                                className={cn(
                                  "absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity z-10 cursor-pointer",
                                  isMenuOpen && "opacity-100",
                                  "bg-linear-to-l from-70% to-transparent pl-8 rounded-r-lg",
                                  isActive
                                    ? "from-muted"
                                    : "from-gray-50 group-hover:from-[#f2f2f3]",
                                )}
                              >
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 shrink-0 hover:bg-muted/30 focus-visible:ring-0"
                                >
                                  <MoreVertical className="h-4 w-4 text-muted-foreground" />
                                </Button>
                              </div>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent
                              align="end"
                              className="min-w-[180px]"
                            >
                              <DropdownMenuItem
                                className="gap-2 cursor-pointer"
                                onClick={() =>
                                  toggleFavoriteMutation.mutate({
                                    id: conv.id,
                                    is_favorite: conv.is_favorite,
                                  })
                                }
                              >
                                <Star
                                  className={cn(
                                    "h-4 w-4",
                                    conv.is_favorite &&
                                      "fill-amber-400 text-amber-400",
                                  )}
                                />
                                <span>
                                  {conv.is_favorite
                                    ? "Retirer des favoris"
                                    : "Mettre en favoris"}
                                </span>
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="focus:bg-muted/80 gap-2 cursor-pointer transition-colors"
                                onClick={() => {
                                  if (
                                    confirm("Supprimer cette conversation ?")
                                  ) {
                                    deleteMutation.mutate(conv.id);
                                  }
                                }}
                              >
                                <Trash2 className="h-4 w-4" />
                                <span>Supprimer</span>
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      );
                    })}
                </div>
              </>
            )}
            <div className="px-2 py-2 text-xs font-medium text-muted-foreground shrink-0">
              Chat
            </div>
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                Loading...
              </div>
            ) : conversations?.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                No conversations yet
              </div>
            ) : (
              conversations
                ?.filter(
                  (c) => c.is_favorite === false || c.is_favorite === undefined,
                )
                ?.map((conv) => {
                  const isActive = matchRoute({
                    to: "/chat/$chatId",
                    params: { chatId: conv.id },
                    fuzzy: false,
                  });
                  const isMenuOpen = openMenuId === conv.id;

                  return (
                    <div
                      key={conv.id}
                      className={cn(
                        "group relative flex items-center rounded-lg hover:bg-muted/50 transition-colors p-1 min-w-0 w-full overflow-hidden shrink-0",
                        isActive && "bg-muted",
                      )}
                    >
                      <Link
                        to="/chat/$chatId"
                        params={{ chatId: conv.id }}
                        className="flex-1 basis-0 min-w-0 overflow-hidden p-1.5 rounded-md text-sm"
                      >
                        <div className="font-medium truncate block w-full">
                          {conv.title || "New Conversation"}
                        </div>
                      </Link>

                      <DropdownMenu
                        onOpenChange={(isOpen) =>
                          setOpenMenuId(isOpen ? conv.id : null)
                        }
                      >
                        <DropdownMenuTrigger asChild>
                          <div
                            className={cn(
                              "absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity z-10 cursor-pointer",
                              isMenuOpen && "opacity-100",
                              "bg-linear-to-l from-70% to-transparent pl-8 rounded-r-lg",
                              isActive
                                ? "from-muted"
                                : "from-gray-50 group-hover:from-[#f2f2f3]",
                            )}
                          >
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 shrink-0 hover:bg-muted/30 focus-visible:ring-0"
                            >
                              <MoreVertical className="h-4 w-4 text-muted-foreground" />
                            </Button>
                          </div>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          className="min-w-[180px]"
                        >
                          <DropdownMenuItem
                            className="gap-2 cursor-pointer"
                            onClick={() =>
                              toggleFavoriteMutation.mutate({
                                id: conv.id,
                                is_favorite: conv.is_favorite,
                              })
                            }
                          >
                            <Star className="h-4 w-4" />
                            <span>Mettre en favoris</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="focus:bg-muted/80 gap-2 cursor-pointer transition-colors"
                            onClick={() => {
                              if (confirm("Supprimer cette conversation ?")) {
                                deleteMutation.mutate(conv.id);
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                            <span>Supprimer</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  );
                })
            )}
          </div>
        </div>
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
                isCollapsed && "justify-center px-0",
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
              <p className="text-sm text-muted-foreground">
                Les options de configuration seront bientôt disponibles.
              </p>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
