import { Link } from "@tanstack/react-router";
import { BarChart3, Folder, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SidebarNavProps {
  isCollapsed: boolean;
  onNewChat: () => void;
  isCreatingChat: boolean;
  onSearchOpen: () => void;
  onNewProjectOpen: () => void;
}

export function SidebarNav({
  isCollapsed,
  onNewChat,
  isCreatingChat,
  onSearchOpen,
  onNewProjectOpen,
}: SidebarNavProps) {
  const NavItem = ({
    onClick,
    icon: Icon,
    label,
    disabled,
    to,
  }: {
    onClick?: () => void;
    icon: any;
    label: string;
    disabled?: boolean;
    to?: string;
  }) => {
    const button = (
      <Button
        className={cn(
          "w-full justify-start gap-3 text-sm",
          isCollapsed && "justify-center px-0",
        )}
        variant="ghost"
        onClick={onClick}
        disabled={disabled}
      >
        <Icon className="h-5 w-5" />
        {!isCollapsed && <span>{label}</span>}
      </Button>
    );

    const content = to ? (
      <Link to={to} className="block">
        {button}
      </Link>
    ) : (
      button
    );

    if (isCollapsed) {
      return (
        <Tooltip>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
      );
    }

    return content;
  };

  return (
    <div className="p-2 space-y-1">
      <NavItem
        onClick={onNewChat}
        icon={Plus}
        label="Nouveau chat"
        disabled={isCreatingChat}
      />
      <NavItem to="/analytics" icon={BarChart3} label="Analytics" />
      <NavItem onClick={onSearchOpen} icon={Search} label="Rechercher" />
      <NavItem
        onClick={onNewProjectOpen}
        icon={Folder}
        label="Nouveau projet"
      />
    </div>
  );
}
