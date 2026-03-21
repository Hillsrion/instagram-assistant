import { Settings } from "lucide-react";
import { NewProjectModal } from "@/components/ProjectModals";
import { SettingsModal } from "@/components/SettingsModal";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarFooterProps {
  isCollapsed: boolean;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (open: boolean) => void;
  isNewProjectOpen: boolean;
  setIsNewProjectOpen: (open: boolean) => void;
}

export function SidebarFooter({
  isCollapsed,
  isSettingsOpen,
  setIsSettingsOpen,
  isNewProjectOpen,
  setIsNewProjectOpen,
}: SidebarFooterProps) {
  return (
    <div className="p-3">
      <Button
        variant="ghost"
        className={cn(
          "w-full justify-start gap-3",
          isCollapsed && "justify-center px-0",
        )}
        onClick={() => setIsSettingsOpen(true)}
        title={isCollapsed ? "Réglages" : undefined}
      >
        <Settings className="h-5 w-5" />
        {!isCollapsed && <span>Réglages</span>}
      </Button>

      <SettingsModal open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />

      <NewProjectModal
        open={isNewProjectOpen}
        onOpenChange={setIsNewProjectOpen}
      />
    </div>
  );
}
