import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getChats, getProjects } from "@/lib/api";

export function useSidebar() {
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

  const { data: chats } = useQuery({
    queryKey: ["chats"],
    queryFn: getChats,
  });

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  return {
    chats,
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
  };
}
