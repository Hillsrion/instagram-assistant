import { Settings } from "lucide-react";
import { NewProjectModal } from "@/components/ProjectModals";
import { SettingsModal } from "@/components/SettingsModal";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  const settingsButton = (
    <Button
      variant="ghost"
      className={cn(
        "w-full justify-start gap-3",
        isCollapsed && "justify-center px-0",
      )}
      onClick={() => setIsSettingsOpen(true)}
    >
      <Settings className="h-5 w-5" />
      {!isCollapsed && <span>Réglages</span>}
    </Button>
  );

  return (
    <div className="p-3">
      {isCollapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>{settingsButton}</TooltipTrigger>
          <TooltipContent side="right">Réglages</TooltipContent>
        </Tooltip>
      ) : (
        settingsButton
      )}

      <SettingsModal open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />

      <NewProjectModal
        open={isNewProjectOpen}
        onOpenChange={setIsNewProjectOpen}
      />
    </div>
  );
}
