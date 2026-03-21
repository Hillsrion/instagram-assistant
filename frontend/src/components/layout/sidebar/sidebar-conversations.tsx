import type { UseMutationResult } from "@tanstack/react-query";
import type { ConversationListResponse } from "@/lib/types";
import { ConversationItem } from "./conversation-item";

interface SidebarConversationsProps {
  conversations: ConversationListResponse[] | undefined;
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
  toggleFavoriteMutation: UseMutationResult<
    any,
    Error,
    { id: string; is_favorite: boolean }
  >;
  deleteMutation: UseMutationResult<void, Error, string>;
}

export function SidebarConversations({
  conversations,
  openMenuId,
  setOpenMenuId,
  toggleFavoriteMutation,
  deleteMutation,
}: SidebarConversationsProps) {
  const freeConversations = conversations?.filter(
    (c) =>
      !c.project_id && (c.is_favorite === false || c.is_favorite === undefined),
  );

  return (
    <>
      <div className="px-2 py-2 text-xs font-medium text-muted-foreground shrink-0 mt-4">
        Conversations
      </div>
      <div>
        {freeConversations?.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            Aucune conversation libre
          </div>
        ) : (
          freeConversations?.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
              toggleFavoriteMutation={toggleFavoriteMutation}
              deleteMutation={deleteMutation}
            />
          ))
        )}
      </div>
    </>
  );
}
