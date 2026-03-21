import { Link, useMatchRoute } from "@tanstack/react-router";
import { MoreVertical, Star } from "lucide-react";
import { ConversationMenu } from "@/components/ConversationMenu";
import { Button } from "@/components/ui/button";
import type { ConversationListResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ConversationItemProps {
  conversation: ConversationListResponse;
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
  isCollapsed?: boolean;
}

export function ConversationItem({
  conversation,
  openMenuId,
  setOpenMenuId,
  isCollapsed,
}: ConversationItemProps) {
  const matchRoute = useMatchRoute();
  const isActive = matchRoute({
    to: "/chat/$chatId",
    params: { chatId: conversation.id },
    fuzzy: false,
  });
  const isMenuOpen = openMenuId === conversation.id;

  if (isCollapsed) return null;

  return (
    <div
      className={cn(
        "group relative flex items-center rounded-lg hover:bg-muted/50 transition-colors p-1 min-w-0 w-full overflow-hidden shrink-0",
        isActive && "bg-muted",
      )}
    >
      <Link
        to="/chat/$chatId"
        params={{ chatId: conversation.id }}
        search={{ q: undefined }}
        className="flex-1 basis-0 min-w-0 overflow-hidden p-1.5 rounded-md text-sm flex items-center gap-2"
      >
        {conversation.is_favorite && (
          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400 shrink-0" />
        )}
        <div className="font-medium truncate block w-full">
          {conversation.title || "New Conversation"}
        </div>
      </Link>

      <div
        className={cn(
          "absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity z-10 cursor-pointer",
          isMenuOpen && "opacity-100",
          "bg-linear-to-l from-70% to-transparent pl-8 rounded-r-lg",
          isActive ? "from-muted" : "from-gray-50 group-hover:from-[#f2f2f3]",
        )}
      >
        <ConversationMenu
          conversation={conversation}
          trigger={
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 hover:bg-muted/30 focus-visible:ring-0"
              onClick={(e) => {
                e.stopPropagation();
                setOpenMenuId(conversation.id);
              }}
            >
              <MoreVertical className="h-4 w-4 text-muted-foreground" />
            </Button>
          }
        />
      </div>
    </div>
  );
}
