import {
  Database,
  MessageSquare,
  Palette,
  Settings as SettingsIcon,
  Shield,
  Users,
} from "lucide-react";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";

export function SettingsSidebar() {
  return (
    <TabsList className="flex flex-col w-64 h-full bg-slate-50/50 border-r p-5 justify-start items-stretch gap-1 rounded-none">
      <div className="flex items-center gap-2 px-3 py-4 mb-2">
        <SettingsIcon className="w-5 h-5 text-primary" />
        <span className="text-xl font-bold text-slate-800">Réglages</span>
      </div>

      <TabsTrigger
        value="general"
        className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
      >
        <Shield className="w-4 h-4" />
        <span className="font-medium">Options basiques</span>
      </TabsTrigger>
      <TabsTrigger
        value="agent"
        className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
      >
        <MessageSquare className="w-4 h-4" />
        <span className="font-medium">Contrôle de l'agent</span>
      </TabsTrigger>
      <TabsTrigger
        value="accounts"
        className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
      >
        <Users className="w-4 h-4" />
        <span className="font-medium">Gestion des comptes</span>
      </TabsTrigger>
      <TabsTrigger
        value="conversations"
        className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
      >
        <Database className="w-4 h-4" />
        <span className="font-medium">Conversations</span>
      </TabsTrigger>
      <TabsTrigger
        value="preferences"
        className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
      >
        <Palette className="w-4 h-4" />
        <span className="font-medium">Préférences</span>
      </TabsTrigger>
    </TabsList>
  );
}
