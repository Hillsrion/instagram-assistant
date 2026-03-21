import type { Settings } from "../settings-schema";
import { API_BASE } from "./base";

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function getTones(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/settings/tones`);
  if (!res.ok) throw new Error("Failed to fetch tones");
  return res.json();
}

export async function updateSettings(settings: Settings): Promise<void> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error("Failed to update settings");
}
