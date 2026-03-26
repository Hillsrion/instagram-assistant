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
      name: "ownUsername",
      label: "Votre nom d'utilisateur",
      description:
        "Votre nom d'utilisateur Instagram (ex: ismaelsebbane). Pour plusieurs comptes, séparez-les par des virgules (ex: account1, account2).",
      type: "text",
    },
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
          Configurez les paramètres globaux de l'application et vos préférences
          d'affichage.
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
