import {
  Bot,
  CalendarDays,
  ChevronRight,
  Folder,
  RotateCcw,
  Upload,
  Users,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { MenuSection } from "@/hooks/use-chat-input-menu";
import { cn } from "@/lib/utils";

interface ChatInputMenuSidebarProps {
  activeSection: MenuSection;
  setActiveSection: (section: MenuSection) => void;
  onReset: () => void;
  onUploadClick: () => void;
}

export function ChatInputMenuSidebar({
  activeSection,
  setActiveSection,
  onReset,
  onUploadClick,
}: ChatInputMenuSidebarProps) {
  const menuItems = [
    {
      id: "upload",
      icon: Upload,
      label: "Télécharger des fichiers",
      action: onUploadClick,
    },
    {
      id: "date",
      icon: CalendarDays,
      label: "Date",
      hasSubmenu: true,
    },
    {
      id: "comptes",
      icon: Users,
      label: "Comptes",
      hasSubmenu: true,
    },
    {
      id: "agents",
      icon: Bot,
      label: "Agents",
      hasSubmenu: true,
    },
    {
      id: "projets",
      icon: Folder,
      label: "Projets",
      hasSubmenu: true,
    },
  ];

  return (
    <div
      className={cn(
        "flex flex-col py-2",
        activeSection ? "w-[240px] border-r bg-muted/10" : "flex-1",
      )}
    >
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-0.5">
          {menuItems.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                if (item.hasSubmenu) {
                  setActiveSection(
                    activeSection === item.id ? null : (item.id as MenuSection),
                  );
                } else if (item.action) {
                  item.action();
                }
              }}
              className={cn(
                "w-full flex items-center justify-between px-2 py-1.5 text-sm rounded-md transition-colors",
                activeSection === item.id
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-foreground/80 hover:bg-muted hover:text-foreground",
              )}
            >
              <div className="flex items-center gap-2">
                <item.icon className="h-4 w-4 opacity-70" />
                <span>{item.label}</span>
              </div>
              {item.hasSubmenu && (
                <ChevronRight className="h-4 w-4 opacity-50" />
              )}
            </button>
          ))}
        </div>
      </ScrollArea>

      <div className="px-2 mt-auto pt-2 border-t">
        <button
          type="button"
          onClick={onReset}
          className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-md text-foreground/80 hover:bg-muted hover:text-foreground transition-colors"
        >
          <RotateCcw className="h-4 w-4 opacity-70" />
          <span>Réinitialiser l'entrée</span>
        </button>
      </div>
    </div>
  );
}
