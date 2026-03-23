import type { DateRange } from "react-day-picker";
import type { ChatMode } from "@/components/ModeSelector";

// Basic types based on the backend API
export interface FileAttachment {
  id: string;
  name: string;
  type: "image" | "document" | string;
  url: string;
  size?: number;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  attachments?: FileAttachment[];
  sources?: Source[];
  summary_sources?: SummarySource[];
  followups?: string[];
}

export interface Source {
  rank: number;
  chunk_id: string;
  file: string;
  participants: string[];
  date_start: string;
  date_end: string;
  score: number;
  expanded?: boolean;
  preview: string;
}

export interface SummarySource {
  type: "summary";
  level: "conversation" | "period";
  summary_id: string;
  participants: string[];
  period: string;
  score: number;
  preview: string;
}

export interface ChunkDetail {
  chunk_id: string;
  content: string;
  participants: string[];
  date_start: string;
  date_end: string;
  file_source: string;
  message_count: number;
  hypothetical_questions: string[];
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_favorite?: boolean;
  project_id?: string;
  message_count?: number;
  messages?: Message[];
}

export interface Project {
  id: string;
  title: string;
  description?: string;
  tone?: string;
  instructions?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_favorite: boolean;
  project_id?: string;
  message_count: number;
}

export interface ChatInputProps {
  onSendMessage: (
    content: string,
    options: {
      participant?: string;
      group?: string;
      broadSearch?: boolean;
      model?: string;
      mode?: string;
      agent_id?: string;
      date?: DateRange;
      attachments?: FileAttachment[];
    },
  ) => void;
  isStreaming: boolean;
  stopStream: () => void;

  selectedModel: string;
  setSelectedModel: (model: string) => void;
  selectedMode: ChatMode;
  setSelectedMode: (mode: ChatMode) => void;
  developerMode: boolean;
  modelsData?: {
    models: Array<{ name: string }>;
    default_model: string;
  };
  filterParticipant: string;
  setFilterParticipant: (p: string) => void;
  filterGroup: string;
  setFilterGroup: (g: string) => void;
  filterBroad: boolean;
  setFilterBroad: (b: boolean) => void;
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
  participantNames: string[];
  selectedAgent: string;
  setSelectedAgent: (id: string) => void;
  className?: string;
  isLoading?: boolean;
  autoFocus?: boolean;
  isHome?: boolean;
}
