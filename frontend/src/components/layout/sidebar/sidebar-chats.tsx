import type { ChatListResponse } from "@/lib/types";
import { ChatItem } from "./chat-item";

interface SidebarChatsProps {
  chats: ChatListResponse[] | undefined;
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
}

export function SidebarChats({
  chats,
  openMenuId,
  setOpenMenuId,
}: SidebarChatsProps) {
  const freeChats = chats?.filter(
    (c) =>
      !c.project_id && (c.is_favorite === false || c.is_favorite === undefined),
  );

  return (
    <>
      <div className="px-2 py-2 text-xs font-medium text-muted-foreground shrink-0 mt-4">
        Chats
      </div>
      <div className="px-2">
        {freeChats?.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            Aucun chat libre
          </div>
        ) : (
          freeChats?.map((chat) => (
            <ChatItem
              key={chat.id}
              chat={chat}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
            />
          ))
        )}
      </div>
    </>
  );
}
