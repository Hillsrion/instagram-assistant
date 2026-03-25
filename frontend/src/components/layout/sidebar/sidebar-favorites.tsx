import type { ChatListResponse } from "@/lib/types";
import { ChatItem } from "./chat-item";

interface SidebarFavoritesProps {
  chats: ChatListResponse[];
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
}

export function SidebarFavorites({
  chats,
  openMenuId,
  setOpenMenuId,
}: SidebarFavoritesProps) {
  const favoriteChats = chats.filter((c) => c.is_favorite);

  if (favoriteChats.length === 0) return null;

  return (
    <>
      <div className="px-2 py-2 text-xs font-medium text-muted-foreground flex items-center gap-2 shrink-0">
        Favoris
      </div>
      <div className="flex flex-col mb-4">
        {favoriteChats.map((chat) => (
          <ChatItem
            key={chat.id}
            chat={chat}
            openMenuId={openMenuId}
            setOpenMenuId={setOpenMenuId}
          />
        ))}
      </div>
    </>
  );
}
