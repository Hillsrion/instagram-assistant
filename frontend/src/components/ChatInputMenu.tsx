import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  BookOpen,
  Bot,
  CalendarDays,
  Check,
  ChevronRight,
  Folder,
  Plus,
  RotateCcw,
  Search,
  Upload,
  User,
  Users,
} from "lucide-react";
import React, { useMemo, useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getProjects } from "@/lib/api/projects";
import { cn } from "@/lib/utils";

type MenuSection = "date" | "comptes" | "agents" | "projets" | "outils" | null;

interface ChatInputMenuProps {
  children: React.ReactNode;
  // Accounts
  participantNames: string[];
  selectedParticipant: string;
  onSelectParticipant: (name: string) => void;
  isBroadSearch: boolean;
  onBroadSearchChange: (isBroad: boolean) => void;
  selectedGroup: string;
  onSelectGroup: (group: string) => void;
  // Date
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
  // Action
  onReset: () => void;
  onFilesSelected: (files: FileList) => void;
  // Optional Projects/Agents to render right side
  // projects?: ProjectListResponse[];
}

const MOCK_GROUPS = [
  { id: "family", name: "Famille", count: 4 },
  { id: "work", name: "Travail", count: 8 },
  { id: "friends", name: "Amis", count: 12 },
];

export function ChatInputMenu({
  children,
  participantNames = [],
  selectedParticipant,
  onSelectParticipant,
  isBroadSearch,
  onBroadSearchChange,
  selectedGroup,
  onSelectGroup,
  filterDate,
  setFilterDate,
  onReset,
  onFilesSelected,
}: ChatInputMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<MenuSection>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  // Search states
  const [accountSearch, setAccountSearch] = useState("");
  const [projectSearch, setProjectSearch] = useState("");

  const filteredParticipants = useMemo(() => {
    return participantNames.filter((p) =>
      p.toLowerCase().includes(accountSearch.toLowerCase()),
    );
  }, [participantNames, accountSearch]);

  const sortedParticipants = useMemo(() => {
    return filteredParticipants.toSorted((a: string, b: string) => {
      if (a === selectedParticipant) return -1;
      if (b === selectedParticipant) return 1;
      return a.localeCompare(b);
    });
  }, [filteredParticipants, selectedParticipant]);

  const filteredProjects = useMemo(() => {
    return projects.filter((p) =>
      p.title.toLowerCase().includes(projectSearch.toLowerCase()),
    );
  }, [projects, projectSearch]);

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      // Reset logic on close if needed, but usually we just keep state
    }
  };

  const menuItems = [
    {
      id: "upload",
      icon: Upload,
      label: "Télécharger des fichiers",
      action: () => {
        fileInputRef.current?.click();
        setOpen(false);
      },
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
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        className={cn(
          "p-0 transition-all duration-300",
          activeSection ? "w-[600px]" : "w-[240px]",
        )}
        align="start"
      >
        <div className="flex h-[400px] bg-background rounded-lg overflow-hidden">
          {/* LEFT SIDE: MENU */}
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
                          activeSection === item.id
                            ? null
                            : (item.id as MenuSection),
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
                onClick={() => {
                  onReset();
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-md text-foreground/80 hover:bg-muted hover:text-foreground transition-colors"
              >
                <RotateCcw className="h-4 w-4 opacity-70" />
                <span>Réinitialiser l'entrée</span>
              </button>
            </div>
          </div>

          {/* RIGHT SIDE: SUBMENU CONTENT */}
          {activeSection && (
            <div className="flex-1 flex flex-col min-w-0 bg-background">
              {/* DATE SECTION */}
              {activeSection === "date" && (
                <div className="flex flex-col items-center justify-center p-0">
                  <Calendar
                    mode="range"
                    selected={filterDate}
                    onSelect={setFilterDate}
                    initialFocus
                    locale={fr}
                    numberOfMonths={1}
                    className="p-4"
                  />
                  <div className="w-full px-4 text-center mt-2 pb-4">
                    {filterDate?.from ? (
                      <div className="text-sm font-medium text-primary bg-primary/10 rounded-md py-1">
                        {filterDate.to
                          ? `${format(filterDate.from, "d MMM", { locale: fr })} - ${format(filterDate.to, "d MMM yyyy", { locale: fr })}`
                          : format(filterDate.from, "d MMM yyyy", {
                              locale: fr,
                            })}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        Sélectionnez une période
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* COMPTES SECTION */}
              {activeSection === "comptes" && (
                <div className="flex flex-col h-full">
                  <div className="p-3 border-b flex flex-col gap-3">
                    <div className="relative">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Rechercher"
                        className="pl-9 h-9 border-none bg-muted/50 focus-visible:ring-0 focus-visible:bg-muted text-sm rounded-full"
                        value={accountSearch}
                        onChange={(e) => setAccountSearch(e.target.value)}
                      />
                    </div>
                    {/* Groups as Pills */}
                    <div className="w-full whitespace-nowrap pb-1 overflow-x-auto">
                      <div className="flex w-max space-x-2 px-1">
                        <button
                          type="button"
                          onClick={() => onSelectGroup("")}
                          className={cn(
                            "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                            !selectedGroup
                              ? "bg-primary text-primary-foreground"
                              : "bg-transparent text-foreground hover:bg-accent",
                          )}
                        >
                          Tous
                        </button>
                        {MOCK_GROUPS.map((group) => (
                          <button
                            type="button"
                            key={group.id}
                            onClick={() => {
                              onSelectGroup(group.id);
                              // clear participant
                              onSelectParticipant("");
                            }}
                            className={cn(
                              "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                              selectedGroup === group.id
                                ? "bg-primary text-primary-foreground"
                                : "bg-transparent text-foreground hover:bg-accent",
                            )}
                          >
                            {group.name}
                          </button>
                        ))}
                      </div>
                    </div>
                    {selectedParticipant && (
                      <div className="flex items-center gap-2 px-1">
                        <input
                          type="checkbox"
                          id="menu-broad-search"
                          checked={isBroadSearch}
                          onChange={(e) =>
                            onBroadSearchChange(e.target.checked)
                          }
                          className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label
                          htmlFor="menu-broad-search"
                          className="text-[11px] font-medium text-muted-foreground cursor-pointer select-none"
                        >
                          Inclure les mentions (recherche large)
                        </label>
                      </div>
                    )}
                  </div>

                  <ScrollArea className="flex-1">
                    <div className="p-2 space-y-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          onSelectParticipant("");
                        }}
                        className={cn(
                          "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                          selectedParticipant === "" && !selectedGroup
                            ? "bg-primary/10 text-primary font-medium"
                            : "hover:bg-accent text-foreground/80",
                        )}
                      >
                        <div className="flex items-center gap-2 flex-1">
                          <Users className="h-4 w-4" />
                          <span>Tous les participants</span>
                        </div>
                        {selectedParticipant === "" && !selectedGroup && (
                          <Check className="h-4 w-4" />
                        )}
                      </button>

                      {sortedParticipants.map((name: string) => (
                        <button
                          type="button"
                          key={name}
                          onClick={() => {
                            onSelectParticipant(
                              selectedParticipant === name ? "" : name,
                            );
                          }}
                          className={cn(
                            "flex items-center w-full px-2 py-2 text-sm rounded-md text-left transition-colors",
                            selectedParticipant === name
                              ? "bg-primary/10 text-primary font-medium"
                              : "hover:bg-accent text-foreground/80",
                          )}
                        >
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <User className="h-4 w-4 opacity-70 shrink-0" />
                            <span className="truncate">{name}</span>
                          </div>
                          {selectedParticipant === name && (
                            <Check className="h-4 w-4 shrink-0" />
                          )}
                        </button>
                      ))}

                      {filteredParticipants.length === 0 && (
                        <div className="p-8 text-center text-sm text-muted-foreground">
                          Aucun participant trouvé.
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              )}

              {/* PROJETS SECTION */}
              {activeSection === "projets" && (
                <div className="flex flex-col h-full">
                  <div className="p-3 border-b flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Rechercher</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs gap-1"
                      >
                        <Plus className="h-3 w-3" />
                        Nouveau Projet
                      </Button>
                    </div>
                    <div className="relative">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Rechercher des projets..."
                        className="pl-9 h-9 border-none bg-muted/50 focus-visible:ring-0 text-sm rounded-sm"
                        value={projectSearch}
                        onChange={(e) => setProjectSearch(e.target.value)}
                      />
                    </div>
                  </div>
                  <ScrollArea className="flex-1">
                    <div className="p-2 space-y-2">
                      {filteredProjects.map((proj) => (
                        <div
                          key={proj.id}
                          className="flex items-center gap-3 p-2 rounded-md hover:bg-accent transition-colors cursor-pointer border border-transparent hover:border-border"
                        >
                          <div className="h-10 w-10 shrink-0 rounded-md bg-muted flex items-center justify-center border">
                            <BookOpen className="h-5 w-5 text-orange-500" />
                          </div>
                          <div className="flex flex-col min-w-0 flex-1">
                            <span className="text-sm font-medium text-foreground truncate">
                              {proj.title}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              Projet
                            </span>
                          </div>
                        </div>
                      ))}
                      {filteredProjects.length === 0 && (
                        <div className="p-8 text-center text-sm text-muted-foreground">
                          Aucun projet trouvé.
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              )}

              {/* AGENTS SECTION */}
              {activeSection === "agents" && (
                <div className="flex flex-col h-full">
                  <div className="p-3 border-b flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-muted-foreground">
                        Rechercher
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs gap-1 text-foreground"
                      >
                        <Plus className="h-3 w-3" />
                        Nouvel Agent
                      </Button>
                    </div>
                  </div>
                  <ScrollArea className="flex-1">
                    <div className="p-2 space-y-2">
                      {/* Mock Agent */}
                      <div className="flex items-center gap-3 p-2 rounded-md hover:bg-accent transition-colors cursor-pointer">
                        <div className="h-10 w-10 shrink-0 rounded-md bg-blue-500 flex items-center justify-center text-white font-bold">
                          👾
                        </div>
                        <div className="flex flex-col min-w-0 flex-1">
                          <span className="text-sm font-medium text-foreground truncate">
                            Nouvel agent
                          </span>
                        </div>
                      </div>
                    </div>
                  </ScrollArea>
                </div>
              )}
            </div>
          )}
        </div>
      </PopoverContent>
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        multiple
        accept="image/*,.pdf,.txt,.doc,.docx"
        onChange={(e) => {
          if (e.target.files) {
            onFilesSelected(e.target.files);
          }
        }}
      />
    </Popover>
  );
}
