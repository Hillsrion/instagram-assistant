import { API_BASE } from "./base";

export interface Agent {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export async function getAgents(): Promise<Agent[]> {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  return res.json();
}
