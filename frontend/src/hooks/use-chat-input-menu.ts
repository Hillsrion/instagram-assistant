import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { getAgents } from "@/lib/api/agents";
import { getProjects } from "@/lib/api/chat-projects";

interface UseChatInputMenuProps {
  participantNames: string[];
  selectedParticipant: string;
}

export type MenuSection =
  | "date"
  | "comptes"
  | "agents"
  | "projets"
  | "outils"
  | null;

export function useChatInputMenu({
  participantNames,
  selectedParticipant,
}: UseChatInputMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<MenuSection>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: getAgents,
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
      // Logic on close if needed
    }
  };

  return {
    open,
    setOpen,
    activeSection,
    setActiveSection,
    fileInputRef,
    projects,
    agents,
    accountSearch,
    setAccountSearch,
    projectSearch,
    setProjectSearch,
    sortedParticipants,
    filteredProjects,
    handleOpenChange,
  };
}
