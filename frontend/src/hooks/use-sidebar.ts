import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  createConversation,
  deleteConversation,
  getConversations,
  getProjects,
  updateConversation,
} from "@/lib/api";

export function useSidebar() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isNewProjectOpen, setIsNewProjectOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [expandedProjects, setExpandedProjects] = useState<
    Record<string, boolean>
  >({});

  const toggleProject = (projectId: string) => {
    setExpandedProjects((prev) => ({
      ...prev,
      [projectId]: !prev[projectId],
    }));
  };

  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: getConversations,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  const createMutation = useMutation({
    mutationFn: (projectId?: string) =>
      createConversation(undefined, projectId),
    onSuccess: (newConv: any) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate({
        to: "/chat/$chatId",
        params: { chatId: newConv.id },
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: ({ id, is_favorite }: { id: string; is_favorite: boolean }) =>
      updateConversation(id, { is_favorite: !is_favorite }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  return {
    conversations,
    projects,
    isSearchOpen,
    setIsSearchOpen,
    isSettingsOpen,
    setIsSettingsOpen,
    isNewProjectOpen,
    setIsNewProjectOpen,
    isCollapsed,
    setIsCollapsed,
    openMenuId,
    setOpenMenuId,
    expandedProjects,
    toggleProject,
    createMutation,
    deleteMutation,
    toggleFavoriteMutation,
  };
}
