import { useNavigate } from "@tanstack/react-router";
import {
  CommandDialog,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { ChatListResponse } from "@/lib/types";

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chats: ChatListResponse[] | undefined;
}

export function SearchDialog({ open, onOpenChange, chats }: SearchDialogProps) {
  const navigate = useNavigate();

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Rechercher un chat..." />
      <CommandList className="h-[40vh]">
        <CommandEmpty>Aucun chat trouvé.</CommandEmpty>
        {chats?.map((chat) => (
          <CommandItem
            key={chat.id}
            onSelect={() => {
              onOpenChange(false);
              navigate({
                to: "/chat/$chatId",
                params: { chatId: chat.id },
              });
            }}
            className="flex flex-col items-start gap-1 p-3"
          >
            <div className="font-medium truncate w-full text-left">
              {chat.title || "Nouveau chat"}
            </div>
          </CommandItem>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
