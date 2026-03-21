import { API_BASE } from "./base";

export async function getOllamaModels(): Promise<{
  models: Array<{ name: string; size: number; modified_at: string }>;
  default_model: string;
}> {
  try {
    const res = await fetch(`${API_BASE}/ollama/models`);
    if (!res.ok) throw new Error("Failed to fetch models");
    return res.json();
  } catch (error) {
    console.error("Error fetching Ollama models:", error);
    return { models: [], default_model: "" };
  }
}
