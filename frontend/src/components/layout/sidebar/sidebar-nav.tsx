import { Link } from "@tanstack/react-router";
import { BarChart3, Folder, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarNavProps {
  isCollapsed: boolean;
  onNewConversation: () => void;
  isCreatingConversation: boolean;
  onSearchOpen: () => void;
  onNewProjectOpen: () => void;
}

export function SidebarNav({
  isCollapsed,
  onNewConversation,
  isCreatingConversation,
  onSearchOpen,
  onNewProjectOpen,
}: SidebarNavProps) {
  return (
    <div className="p-2 space-y-1">
      <Button
        className={cn(
          "w-full justify-start gap-3 text-sm",
          isCollapsed && "justify-center px-0",
        )}
        variant="ghost"
        onClick={onNewConversation}
        disabled={isCreatingConversation}
        title={isCollapsed ? "Nouvelle conversation" : undefined}
      >
        <Plus className="h-5 w-5" />
        {!isCollapsed && <span>Nouvelle conversation</span>}
      </Button>

      <Link to="/analytics" className="block">
        <Button
          variant="ghost"
          className={cn(
            "w-full justify-start gap-3",
            isCollapsed && "justify-center px-0",
          )}
          title={isCollapsed ? "Analytics" : undefined}
        >
          <BarChart3 className="h-5 w-5" />
          {!isCollapsed && <span>Analytics</span>}
        </Button>
      </Link>

      <Button
        variant="ghost"
        className={cn(
          "w-full justify-start gap-3",
          isCollapsed && "justify-center px-0",
        )}
        onClick={onSearchOpen}
        title={isCollapsed ? "Rechercher" : undefined}
      >
        <Search className="h-5 w-5" />
        {!isCollapsed && <span>Rechercher</span>}
      </Button>

      <Button
        className={cn(
          "w-full justify-start gap-3",
          isCollapsed && "justify-center px-0",
        )}
        variant="ghost"
        onClick={onNewProjectOpen}
        title={isCollapsed ? "Nouveau projet" : undefined}
      >
        <Folder className="h-5 w-5" />
        {!isCollapsed && <span>Nouveau projet</span>}
      </Button>
    </div>
  );
}
