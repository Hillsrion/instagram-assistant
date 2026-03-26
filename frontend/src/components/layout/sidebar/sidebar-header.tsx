import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
          <div className="flex items-center gap-2 overflow-hidden px-1">
            <img
              src="/logo.png"
              alt="Logo"
              className="h-8 w-8 rounded-lg object-contain shrink-0 p-0.5"
            />
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(true)}
            className="h-8 w-8 ml-auto"
          >
            <PanelLeftClose className="h-5 w-5 text-muted-foreground hover:text-foreground transition-colors" />
          </Button>
        </>
      ) : (
        <>
          <img
            src="/logo.png"
            alt="Logo"
            className="h-8 w-8 rounded-lg object-contain shrink-0 p-0.5 mx-auto"
          />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsCollapsed(false)}
                className="h-8 w-8 mx-auto"
              >
                <PanelLeftOpen className="h-5 w-5 text-muted-foreground hover:text-foreground transition-colors" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              Ouvrir la barre latérale
            </TooltipContent>
          </Tooltip>
        </>
      )}
    </div>
  );
}
