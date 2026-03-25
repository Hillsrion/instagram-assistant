import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { createChat, deleteChat, updateChat } from "@/lib/api";

export function useChatActions() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const createMutation = useMutation({
    mutationFn: (projectId?: string) => createChat(undefined, projectId),
    onSuccess: (newChat: any) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      navigate({
        to: "/chat/$chatId",
        params: { chatId: newChat.id },
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteChat(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
    },
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: ({ id, is_favorite }: { id: string; is_favorite: boolean }) =>
      updateChat(id, { is_favorite: !is_favorite }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      queryClient.invalidateQueries({
        queryKey: ["chat", variables.id],
      });
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      updateChat(id, { title }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["chats"] });
      queryClient.invalidateQueries({
        queryKey: ["chat", variables.id],
      });
    },
  });

  return {
    createMutation,
    deleteMutation,
    toggleFavoriteMutation,
    renameMutation,
  };
}
