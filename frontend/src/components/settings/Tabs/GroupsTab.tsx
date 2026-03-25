import {
  FolderOpen,
  FolderPlus,
  MoreVertical,
  Plus,
  Search,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { instagramApi } from "@/lib/api/instagram";
import type { InstagramConversation, SourceGroup } from "@/lib/types";

export function GroupsTab() {
  const [groups, setGroups] = useState<SourceGroup[]>([]);
  const [threads, setThreads] = useState<InstagramConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [isAddThreadModalOpen, setIsAddThreadModalOpen] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [threadSearchQuery, setThreadSearchQuery] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [groupsData, threadsData] = await Promise.all([
        instagramApi.listGroups(),
        instagramApi.listThreads(),
      ]);
      setGroups(groupsData);
      setThreads(threadsData);
    } catch (error) {
      toast.error("Erreur lors du chargement des données");
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      await instagramApi.createGroup({ title: newGroupName });
      toast.success("Groupe créé avec succès");
      setNewGroupName("");
      setIsCreateModalOpen(false);
      fetchData();
    } catch {
      toast.error("Erreur lors de la création du groupe");
    }
  };

  const handleDeleteGroup = async (id: string) => {
    try {
      await instagramApi.deleteGroup(id);
      toast.success("Groupe supprimé");
      fetchData();
    } catch {
      toast.error("Erreur lors de la suppression");
    }
  };

  const handleRemoveFromGroup = async (groupId: string, threadId: string) => {
    try {
      await instagramApi.bulkUpdateGroupThreads(groupId, {
        thread_ids: [threadId],
        action: "remove",
      });
      toast.success("Thread retiré du groupe");
      fetchData();
    } catch {
      toast.error("Erreur lors du retrait du thread");
    }
  };

  const handleAddToGroup = async (groupId: string, threadIds: string[]) => {
    try {
      await instagramApi.bulkUpdateGroupThreads(groupId, {
        thread_ids: threadIds,
        action: "add",
      });
      toast.success("Threads ajoutés au groupe");
      setIsAddThreadModalOpen(false);
      setThreadSearchQuery("");
      fetchData();
    } catch {
      toast.error("Erreur lors de l'ajout des threads");
    }
  };

  const filteredGroups = groups.filter((g) =>
    g.title.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const getGroupThreads = (groupId: string) => {
    const group = groups.find((g) => g.id === groupId);
    if (!group) return [];
    return threads.filter((t) => group.thread_ids.includes(t.id));
  };

  const unassignedThreads = threads.filter(
    (t) => !groups.some((g) => g.thread_ids.includes(t.id)),
  );

  return (
    <div className="mt-0 space-y-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 leading-none">
            Groupes source
          </h2>
          <p className="text-sm text-muted-foreground mt-2">
            Organisez vos threads Instagram par thématiques.
          </p>
        </div>
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          className="gap-2 rounded-xl h-11 px-5 shadow-sm"
        >
          <FolderPlus className="w-4 h-4" />
          Nouveau groupe
        </Button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          placeholder="Rechercher un groupe..."
          className="pl-10 h-11 bg-slate-50 border-slate-200 rounded-xl focus-visible:ring-primary/20"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <ScrollArea className="flex-1 -mx-2 px-2">
        <div className="grid gap-4 pb-4">
          {loading ? (
            Array(3)
              .fill(0)
              .map((_, i) => (
                <div
                  key={i}
                  className="h-32 bg-slate-50 border border-slate-100 animate-pulse rounded-2xl"
                />
              ))
          ) : filteredGroups.length === 0 ? (
            <div className="text-center py-20 bg-slate-50/50 rounded-3xl border border-dashed border-slate-200">
              <FolderOpen className="w-12 h-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 font-medium">Aucun groupe trouvé</p>
              <p className="text-slate-400 text-sm mt-1">
                Créez votre premier groupe pour organiser vos sources.
              </p>
            </div>
          ) : (
            filteredGroups.map((group) => {
              const groupThreads = getGroupThreads(group.id);
              return (
                <div
                  key={group.id}
                  className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow group/card"
                >
                  <div className="p-5 flex items-center justify-between border-b border-slate-50">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary border border-primary/5">
                        <FolderOpen className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-800 leading-tight">
                          {group.title}
                        </h3>
                        <p className="text-xs text-slate-400 font-medium">
                          {group.thread_ids.length} thread
                          {group.thread_ids.length > 1 ? "s" : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-9 gap-1.5 text-slate-600 hover:text-primary hover:bg-primary/5 rounded-lg px-3"
                        onClick={() => {
                          setSelectedGroupId(group.id);
                          setIsAddThreadModalOpen(true);
                        }}
                      >
                        <Plus className="w-4 h-4" />
                        <span className="text-xs font-semibold uppercase tracking-wider">
                          Ajouter
                        </span>
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-slate-400 hover:text-slate-600 rounded-lg"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          className="w-48 rounded-xl p-1 shadow-xl border-slate-200"
                        >
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive focus:bg-destructive/5 rounded-lg gap-2 cursor-pointer"
                            onClick={() => handleDeleteGroup(group.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                            Supprimer le groupe
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>

                  <div className="p-2 bg-slate-50/30">
                    {groupThreads.length > 0 ? (
                      <div className="flex flex-wrap gap-2 p-3">
                        {groupThreads.map((thread) => (
                          <div
                            key={thread.id}
                            className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-full text-sm text-slate-700 shadow-sm animate-in fade-in zoom-in duration-200"
                            title={thread.summary}
                          >
                            <Users className="w-3.5 h-3.5 text-slate-400" />
                            <span className="max-w-[150px] truncate font-medium">
                              {thread.participants
                                .filter(
                                  (p: string) =>
                                    p.toLowerCase() !== "me" &&
                                    p.toLowerCase() !== "user",
                                )
                                .join(", ")}
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                handleRemoveFromGroup(group.id, thread.id)
                              }
                              className="ml-1 text-slate-300 hover:text-destructive transition-colors"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-8 text-center text-xs text-slate-400 font-medium italic">
                        Aucun thread dans ce groupe
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>

      {/* Create Group Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent className="sm:max-w-[400px] rounded-3xl p-6">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold">
              Nouveau groupe
            </DialogTitle>
            <DialogDescription className="text-slate-500">
              Donnez un nom à votre nouveau groupe de sources.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              placeholder="Ex: Famille, Travail, Amis..."
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              className="h-12 rounded-xl bg-slate-50 border-slate-200 focus-visible:ring-primary/20"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleCreateGroup()}
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0 mt-2">
            <Button
              variant="ghost"
              onClick={() => setIsCreateModalOpen(false)}
              className="rounded-xl h-11"
            >
              Annuler
            </Button>
            <Button
              onClick={handleCreateGroup}
              disabled={!newGroupName.trim()}
              className="rounded-xl h-11 px-8 shadow-sm"
            >
              Créer le groupe
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Thread Modal */}
      <Dialog
        open={isAddThreadModalOpen}
        onOpenChange={setIsAddThreadModalOpen}
      >
        <DialogContent className="sm:max-w-[500px] h-[600px] flex flex-col rounded-3xl p-0 overflow-hidden border-none shadow-2xl">
          <DialogHeader className="p-6 pb-4 border-b">
            <DialogTitle className="text-xl font-bold">
              Ajouter des threads
            </DialogTitle>
            <DialogDescription className="text-slate-500">
              Sélectionnez les conversations Instagram à ajouter au groupe.
            </DialogDescription>
          </DialogHeader>

          <div className="px-6 py-4 border-b bg-slate-50/50">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Rechercher par participants..."
                className="pl-10 h-10 bg-white border-slate-200 rounded-xl shadow-sm"
                value={threadSearchQuery}
                onChange={(e) => setThreadSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <ScrollArea className="flex-1 px-6">
            <div className="py-4 space-y-2">
              {unassignedThreads
                .filter((t) =>
                  t.participants
                    .join(" ")
                    .toLowerCase()
                    .includes(threadSearchQuery.toLowerCase()),
                )
                .map((thread) => (
                  <div
                    key={thread.id}
                    className="flex items-center justify-between p-3 rounded-2xl hover:bg-slate-50 border border-transparent hover:border-slate-100 transition-all cursor-pointer group"
                    onClick={() =>
                      selectedGroupId &&
                      handleAddToGroup(selectedGroupId, [thread.id])
                    }
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 rounded-xl bg-white border border-slate-100 flex items-center justify-center text-slate-400 group-hover:text-primary transition-colors">
                        <Users className="w-5 h-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-800 truncate">
                          {thread.participants
                            .filter(
                              (p: string) =>
                                p.toLowerCase() !== "me" &&
                                p.toLowerCase() !== "user",
                            )
                            .join(", ")}
                        </p>
                        <p className="text-[10px] text-slate-400 truncate max-w-[250px]">
                          {thread.summary}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 rounded-lg text-slate-300 group-hover:text-primary group-hover:bg-primary/5"
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              {unassignedThreads.length === 0 && (
                <div className="py-20 text-center">
                  <p className="text-slate-400 text-sm font-medium">
                    Tous les threads sont déjà groupés.
                  </p>
                </div>
              )}
            </div>
          </ScrollArea>

          <div className="p-6 bg-slate-50 border-t">
            <Button
              variant="ghost"
              onClick={() => setIsAddThreadModalOpen(false)}
              className="w-full h-11 rounded-xl text-slate-500 font-semibold"
            >
              Fermer
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
