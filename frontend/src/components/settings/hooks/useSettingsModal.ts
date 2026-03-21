import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { Settings } from "@/lib/settings-schema";
import { useSettingsStore } from "@/lib/settings-store";

export function useSettingsModal(
  open: boolean,
  onOpenChange: (open: boolean) => void,
) {
  const [activeTab, setActiveTab] = useState("general");
  const {
    settings,
    setSettings: updateStoreSettings,
    fetchSettings,
  } = useSettingsStore();
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [availableTones, setAvailableTones] = useState<string[]>([]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional
  useEffect(() => {
    if (open) {
      setInitialLoading(true);
      fetchSettings().finally(() => setInitialLoading(false));
      fetchTones();
    }
  }, [open, fetchSettings]);

  const fetchTones = async () => {
    try {
      const response = await fetch("/api/settings/tones");
      if (response.ok) {
        const data = await response.json();
        setAvailableTones(data);
      }
    } catch (error) {
      console.error("Failed to fetch tones:", error);
    }
  };

  const handleSave = async (values: Settings) => {
    setLoading(true);
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        updateStoreSettings(values);
        toast.success("Réglages enregistrés avec succès");
        onOpenChange(false);
      } else {
        throw new Error("Failed to save settings");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Échec de l'enregistrement des réglages");
    } finally {
      setLoading(false);
    }
  };

  return {
    activeTab,
    setActiveTab,
    settings,
    loading,
    initialLoading,
    availableTones,
    handleSave,
  };
}
