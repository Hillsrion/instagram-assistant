import {
  type FieldDefinition,
  FormRenderer,
} from "@/components/ui/form/form-renderer";
import { type Settings, SettingsSchema } from "@/lib/settings-schema";

interface AgentTabProps {
  settings: Settings;
  onSave: (values: Settings) => Promise<void>;
  loading: boolean;
  availableTones: string[];
}

export function AgentTab({
  settings,
  onSave,
  loading,
  availableTones,
}: AgentTabProps) {
  const agentFields: FieldDefinition[] = [
    {
      name: "agentTone",
      label: "Ton de l'agent",
      description:
        "Personnalisez le comportement et les réponses de votre assistant.",
      type: "select",
      options: availableTones.map((tone: string) => ({
        label: tone,
        value: tone,
      })),
      placeholder: "Choisir un ton",
    },
    {
      name: "globalInstructions",
      label: "Instructions globales",
      description:
        "Ces instructions seront injectées dans le système pour influencer chaque réponse de l'agent.",
      type: "textarea",
      placeholder:
        "Ex: Réponds toujours de manière polie et utilise le vouvoiement...",
    },
  ];

  return (
    <div className="mt-0 space-y-10">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-slate-900">
          Contrôle de l'agent
        </h2>
        <p className="text-sm text-muted-foreground mb-8">
          Personnalisez le comportement et les réponses de votre assistant.
        </p>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <FormRenderer
            schema={SettingsSchema}
            defaultValues={settings}
            onSubmit={onSave}
            fields={agentFields}
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
}
