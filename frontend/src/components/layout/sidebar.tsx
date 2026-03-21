import { useConversationActions } from "@/hooks/use-conversation-actions";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { SearchDialog } from "./sidebar/search-dialog";
import { SidebarConversations } from "./sidebar/sidebar-conversations";
import { SidebarFavorites } from "./sidebar/sidebar-favorites";
import { SidebarFooter } from "./sidebar/sidebar-footer";
import { SidebarHeader } from "./sidebar/sidebar-header";
import { SidebarNav } from "./sidebar/sidebar-nav";
import { SidebarProjects } from "./sidebar/sidebar-projects";

export function Sidebar() {
  const {
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
  } = useSidebar();

  const { createMutation } = useConversationActions();

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-gray-50 transition-all duration-300 ease-in-out border-r border-gray-200 shrink-0 overflow-hidden",
        isCollapsed ? "w-[60px]" : "w-64 min-w-0 max-w-64",
      )}
    >
      <SidebarHeader
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
      />

      <SidebarNav
        isCollapsed={isCollapsed}
        onNewConversation={() => createMutation.mutate(undefined)}
        isCreatingConversation={createMutation.isPending}
        onSearchOpen={() => setIsSearchOpen(true)}
        onNewProjectOpen={() => setIsNewProjectOpen(true)}
      />

      <SearchDialog
        open={isSearchOpen}
        onOpenChange={setIsSearchOpen}
        conversations={conversations}
      />

      {!isCollapsed ? (
        <div className="flex-1 w-full min-w-0 overflow-y-auto">
          <div className="p-0 w-full min-w-0 flex flex-col">
            <SidebarFavorites
              conversations={conversations || []}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
            />

            <SidebarProjects
              projects={projects}
              conversations={conversations}
              expandedProjects={expandedProjects}
              toggleProject={toggleProject}
            />

            <SidebarConversations
              conversations={conversations}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1" />
      )}

      <SidebarFooter
        isCollapsed={isCollapsed}
        isSettingsOpen={isSettingsOpen}
        setIsSettingsOpen={setIsSettingsOpen}
        isNewProjectOpen={isNewProjectOpen}
        setIsNewProjectOpen={setIsNewProjectOpen}
      />
    </div>
  );
}
