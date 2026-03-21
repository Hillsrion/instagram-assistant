import {
  type FieldDefinition,
  FormRenderer,
} from "@/components/ui/form/form-renderer";
import { type Settings, SettingsSchema } from "@/lib/settings-schema";

interface GeneralTabProps {
  settings: Settings;
  onSave: (values: Settings) => Promise<void>;
  loading: boolean;
}

export function GeneralTab({ settings, onSave, loading }: GeneralTabProps) {
  const generalFields: FieldDefinition[] = [
    {
      name: "developerMode",
      label: "Mode développeur",
      description:
        "Active les outils de diagnostic et les logs détaillés dans l'interface pour le débogage.",
      type: "switch",
    },
  ];

  return (
    <div className="mt-0 space-y-10">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-slate-900 transition-all">
          Options basiques
        </h2>
        <p className="text-sm text-muted-foreground mb-8">
          Configurez les paramètres globaux de l'application.
        </p>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <FormRenderer
            schema={SettingsSchema}
            defaultValues={settings}
            onSubmit={onSave}
            fields={generalFields}
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
}
