import type { UseMutationResult } from "@tanstack/react-query";
import type { ConversationListResponse } from "@/lib/types";
import { ConversationItem } from "./conversation-item";

interface SidebarFavoritesProps {
  conversations: ConversationListResponse[];
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
  toggleFavoriteMutation: UseMutationResult<
    any,
    Error,
    { id: string; is_favorite: boolean }
  >;
  deleteMutation: UseMutationResult<void, Error, string>;
}

export function SidebarFavorites({
  conversations,
  openMenuId,
  setOpenMenuId,
  toggleFavoriteMutation,
  deleteMutation,
}: SidebarFavoritesProps) {
  const favoriteConversations = conversations.filter((c) => c.is_favorite);

  if (favoriteConversations.length === 0) return null;

  return (
    <>
      <div className="px-2 py-2 text-xs font-medium text-muted-foreground flex items-center gap-2 shrink-0">
        Favoris
      </div>
      <div className="flex flex-col mb-4">
        {favoriteConversations.map((conv) => (
          <ConversationItem
            key={conv.id}
            conversation={conv}
            openMenuId={openMenuId}
            setOpenMenuId={setOpenMenuId}
            toggleFavoriteMutation={toggleFavoriteMutation}
            deleteMutation={deleteMutation}
          />
        ))}
      </div>
    </>
  );
}
