import * as v from "valibot";

export const SettingsSchema = v.object({
  developerMode: v.boolean(),
  agentTone: v.picklist(["Professionnel", "Amical", "Concise"]),
  globalInstructions: v.pipe(v.string(), v.maxLength(1000)),
  interfaceTheme: v.picklist(["Clair", "Sombre", "Système"]),
});

export type Settings = v.InferOutput<typeof SettingsSchema>;

export const defaultSettings: Settings = {
  developerMode: false,
  agentTone: "Professionnel",
  globalInstructions: "",
  interfaceTheme: "Système",
};
