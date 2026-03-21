import {
  type FieldDefinition,
  FormRenderer,
} from "@/components/ui/form/form-renderer";
import { type Settings, SettingsSchema } from "@/lib/settings-schema";

interface PreferencesTabProps {
  settings: Settings;
  onSave: (values: Settings) => Promise<void>;
  loading: boolean;
}

export function PreferencesTab({
  settings,
  onSave,
  loading,
}: PreferencesTabProps) {
  const preferenceFields: FieldDefinition[] = [
    {
      name: "interfaceTheme",
      label: "Thème de l'interface",
      description:
        "Ajustez l'apparence visuelle pour une expérience personnalisée.",
      type: "select",
      options: [
        { label: "Clair", value: "Clair" },
        { label: "Sombre", value: "Sombre" },
        { label: "Système", value: "Système" },
      ],
      placeholder: "Choisir un thème",
    },
  ];

  return (
    <div className="mt-0 space-y-10">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-slate-900">Préférences</h2>
        <p className="text-sm text-muted-foreground mb-8">
          Ajustez l'apparence visuelle pour une expérience personnalisée.
        </p>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <FormRenderer
            schema={SettingsSchema}
            defaultValues={settings}
            onSubmit={onSave}
            fields={preferenceFields}
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
}
