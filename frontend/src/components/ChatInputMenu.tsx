import type { DateRange } from "react-day-picker";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useChatInputMenu } from "@/hooks/use-chat-input-menu";
import { cn } from "@/lib/utils";
import { ChatInputMenuSidebar } from "./chat-input-menu/ChatInputMenuSidebar";
import { AccountsSection } from "./chat-input-menu/sections/AccountsSection";
import { AgentsSection } from "./chat-input-menu/sections/AgentsSection";
import { DateSection } from "./chat-input-menu/sections/DateSection";
import { ProjectsSection } from "./chat-input-menu/sections/ProjectsSection";

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
  // Agents
  selectedAgent: string;
  onSelectAgent: (id: string) => void;
  // Action
  onReset: () => void;
  onFilesSelected: (files: FileList) => void;
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
  selectedAgent,
  onSelectAgent,
  onReset,
  onFilesSelected,
}: ChatInputMenuProps) {
  const {
    open,
    setOpen,
    activeSection,
    setActiveSection,
    fileInputRef,
    agents,
    accountSearch,
    setAccountSearch,
    projectSearch,
    setProjectSearch,
    sortedParticipants,
    filteredProjects,
    handleOpenChange,
  } = useChatInputMenu({
    participantNames,
    selectedParticipant,
  });

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
          <ChatInputMenuSidebar
            activeSection={activeSection}
            setActiveSection={setActiveSection}
            onReset={() => {
              onReset();
              setOpen(false);
            }}
            onUploadClick={() => {
              fileInputRef.current?.click();
              setOpen(false);
            }}
          />

          {activeSection && (
            <div className="flex-1 flex flex-col min-w-0 bg-background">
              {activeSection === "date" && (
                <DateSection
                  filterDate={filterDate}
                  setFilterDate={setFilterDate}
                />
              )}

              {activeSection === "comptes" && (
                <AccountsSection
                  accountSearch={accountSearch}
                  setAccountSearch={setAccountSearch}
                  selectedGroup={selectedGroup}
                  onSelectGroup={onSelectGroup}
                  selectedParticipant={selectedParticipant}
                  onSelectParticipant={onSelectParticipant}
                  isBroadSearch={isBroadSearch}
                  onBroadSearchChange={onBroadSearchChange}
                  sortedParticipants={sortedParticipants}
                  mockGroups={MOCK_GROUPS}
                />
              )}

              {activeSection === "projets" && (
                <ProjectsSection
                  projectSearch={projectSearch}
                  setProjectSearch={setProjectSearch}
                  filteredProjects={filteredProjects}
                />
              )}

              {activeSection === "agents" && (
                <AgentsSection
                  agents={agents}
                  selectedAgent={selectedAgent}
                  onSelectAgent={onSelectAgent}
                  onClose={() => setOpen(false)}
                />
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
