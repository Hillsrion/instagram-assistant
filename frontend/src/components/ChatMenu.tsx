import { MoreHorizontal, Pencil, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
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
import { useChatActions } from "@/hooks/use-chat-actions";
import type { ChatListResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChatMenuProps {
  chat: ChatListResponse | { id: string; title: string; is_favorite: boolean };
  align?: "start" | "end";
  trigger?: React.ReactNode;
}

export function ChatMenu({ chat, align = "end", trigger }: ChatMenuProps) {
  const { toggleFavoriteMutation, deleteMutation, renameMutation } =
    useChatActions();
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [newTitle, setNewTitle] = useState(chat.title || "");

  const handleRename = () => {
    if (newTitle.trim() && newTitle !== chat.title) {
      renameMutation.mutate({ id: chat.id, title: newTitle.trim() });
    }
    setIsRenameOpen(false);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {trigger || (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 hover:bg-muted/30 focus-visible:ring-0"
            >
              <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
            </Button>
          )}
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align} className="min-w-[180px]">
          <DropdownMenuItem
            className="gap-2 cursor-pointer"
            onClick={() =>
              toggleFavoriteMutation.mutate({
                id: chat.id,
                is_favorite: chat.is_favorite,
              })
            }
          >
            <Star
              className={cn(
                "h-4 w-4",
                chat.is_favorite && "fill-amber-400 text-amber-400",
              )}
            />
            <span>
              {chat.is_favorite ? "Retirer des favoris" : "Mettre en favoris"}
            </span>
          </DropdownMenuItem>

          <DropdownMenuItem
            className="focus:bg-destructive/10 text-destructive focus:text-destructive gap-2 cursor-pointer transition-colors"
            onClick={() => {
              setNewTitle(chat.title || "");
              setIsRenameOpen(true);
            }}
          >
            <Pencil className="h-4 w-4" />
            <span>Renommer</span>
          </DropdownMenuItem>

          <DropdownMenuItem
            className="focus:bg-destructive/10 text-destructive focus:text-destructive gap-2 cursor-pointer transition-colors"
            onClick={() => {
              if (confirm("Supprimer ce chat ?")) {
                deleteMutation.mutate(chat.id);
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            <span>Supprimer</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={isRenameOpen} onOpenChange={setIsRenameOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Renommer le chat</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <Input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Titre du chat"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleRename();
                }
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRenameOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleRename} disabled={renameMutation.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
