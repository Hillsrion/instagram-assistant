import { create } from "zustand";
import { getSettings } from "./api";
import { defaultSettings, type Settings } from "./settings-schema";

interface SettingsState {
  settings: Settings;
  isLoading: boolean;
  settingsLoaded: boolean;
  setSettings: (settings: Settings) => void;
  fetchSettings: (force?: boolean) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: defaultSettings,
  isLoading: true,
  settingsLoaded: false,
  setSettings: (settings) => set({ settings, settingsLoaded: true }),
  fetchSettings: async (force = false) => {
    if (get().settingsLoaded && !force) return;
    set({ isLoading: true });
    try {
      const data = await getSettings();
      set({ settings: data, isLoading: false, settingsLoaded: true });
    } catch (error) {
      console.error("Failed to fetch settings:", error);
      set({ isLoading: false });
    }
  },
}));
