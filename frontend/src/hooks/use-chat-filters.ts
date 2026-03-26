import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { DateRange } from "react-day-picker";
import { getOllamaModels, getParticipants } from "@/lib/api";
import { useSettingsStore } from "@/lib/settings-store";

interface UseChatFiltersOptions {
  initialParticipant?: string;
  initialGroup?: string;
  initialBroad?: boolean;
  initialMode?: "fast" | "reflexion";
}

export function useChatFilters(options: UseChatFiltersOptions = {}) {
  // Load available models
  const { data: modelsData } = useQuery({
    queryKey: ["ollama-models"],
    queryFn: () => getOllamaModels(),
    refetchOnWindowFocus: false,
  });

  // Load participants for filter
  const { data: participantsData } = useQuery({
    queryKey: ["participants"],
    queryFn: () => getParticipants(),
    refetchOnWindowFocus: false,
  });

  const { settings, fetchSettings } = useSettingsStore();
  const developerMode = settings.developerMode;

  // Initial fetch of settings if needed
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const participantNames = useMemo(() => {
    const names = participantsData?.map((p) => p.name) || [];
    return names.filter((p) => {
      const lowerP = p.toLowerCase();
      const lowerOwn = settings.ownUsername.toLowerCase();
      return (
        lowerP !== "me" &&
        lowerP !== "user" &&
        (!lowerOwn || lowerP !== lowerOwn)
      );
    });
  }, [participantsData, settings.ownUsername]);

  // Filters State
  const [filterParticipant, setFilterParticipant] = useState<string>(
    options.initialParticipant || "",
  );
  const [filterGroup, setFilterGroup] = useState<string>(
    options.initialGroup || "",
  );
  const [filterBroad, setFilterBroad] = useState<boolean>(
    !!options.initialBroad,
  );
  const [filterDate, setFilterDate] = useState<DateRange | undefined>(
    undefined,
  );

  // Model & Mode State
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedMode, setSelectedMode] = useState<"fast" | "reflexion">(
    options.initialMode || "fast",
  );

  // Set default model when models are loaded
  useEffect(() => {
    if (modelsData?.default_model && !selectedModel) {
      setSelectedModel(modelsData.default_model);
    }
  }, [modelsData, selectedModel]);

  return {
    modelsData,
    participantNames,
    filterParticipant,
    setFilterParticipant,
    filterGroup,
    setFilterGroup,
    filterBroad,
    setFilterBroad,
    filterDate,
    setFilterDate,
    selectedModel,
    setSelectedModel,
    selectedMode,
    setSelectedMode,
    developerMode,
  };
}
