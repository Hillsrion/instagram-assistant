import { useNavigate } from "@tanstack/react-router";
import {
  CommandDialog,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { ConversationListResponse } from "@/lib/types";

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conversations: ConversationListResponse[] | undefined;
}

export function SearchDialog({
  open,
  onOpenChange,
  conversations,
}: SearchDialogProps) {
  const navigate = useNavigate();

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Rechercher une conversation..." />
      <CommandList className="h-[40vh]">
        <CommandEmpty>Aucune conversation trouvée.</CommandEmpty>
        {conversations?.map((conv) => (
          <CommandItem
            key={conv.id}
            onSelect={() => {
              onOpenChange(false);
              navigate({
                to: "/chat/$chatId",
                params: { chatId: conv.id },
              });
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
  );
}
