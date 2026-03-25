import { useChatActions } from "@/hooks/use-chat-actions";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { SearchDialog } from "./sidebar/search-dialog";
import { SidebarChats } from "./sidebar/sidebar-chats";
import { SidebarFavorites } from "./sidebar/sidebar-favorites";
import { SidebarFooter } from "./sidebar/sidebar-footer";
import { SidebarHeader } from "./sidebar/sidebar-header";
import { SidebarNav } from "./sidebar/sidebar-nav";
import { SidebarProjects } from "./sidebar/sidebar-projects";

export function Sidebar() {
  const {
    chats,
    projects,
    instagramGroups,
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

  const { createMutation } = useChatActions();

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
        onNewChat={() => createMutation.mutate(undefined)}
        isCreatingChat={createMutation.isPending}
        onSearchOpen={() => setIsSearchOpen(true)}
        onNewProjectOpen={() => setIsNewProjectOpen(true)}
      />

      <SearchDialog
        open={isSearchOpen}
        onOpenChange={setIsSearchOpen}
        chats={chats}
      />

      {!isCollapsed ? (
        <div className="flex-1 w-full min-w-0 overflow-y-auto">
          <div className="p-0 w-full min-w-0 flex flex-col">
            <SidebarFavorites
              chats={chats || []}
              openMenuId={openMenuId}
              setOpenMenuId={setOpenMenuId}
            />

            <SidebarProjects
              projects={projects}
              chats={chats}
              instagramGroups={instagramGroups}
              expandedProjects={expandedProjects}
              toggleProject={toggleProject}
            />

            <SidebarChats
              chats={chats}
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
