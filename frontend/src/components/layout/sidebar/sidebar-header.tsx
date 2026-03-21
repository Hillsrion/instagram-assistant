import { Instagram, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarHeaderProps {
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
}

export function SidebarHeader({
  isCollapsed,
  setIsCollapsed,
}: SidebarHeaderProps) {
  return (
    <div
      className={cn(
        "p-4 flex items-center justify-between",
        isCollapsed && "flex-col gap-4 px-0",
      )}
    >
      {!isCollapsed ? (
        <>
          <div className="flex items-center gap-2 overflow-hidden">
            <Instagram className="h-5 w-5 text-primary shrink-0" />
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(true)}
            className="h-8 w-8"
          >
            <PanelLeftClose className="h-6 w-6" />
          </Button>
        </>
      ) : (
        <>
          <Instagram className="h-6 w-6 text-primary shrink-0" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(false)}
            className="h-8 w-8"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </Button>
        </>
      )}
    </div>
  );
}
