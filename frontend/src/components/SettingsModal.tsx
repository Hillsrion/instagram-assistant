import { useState } from "react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Settings,
  Shield,
  MessageSquare,
  Users,
  Palette,
  Import,
  Trash2,
  Instagram,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState("general");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] p-0 overflow-hidden flex flex-col gap-0 border-none shadow-2xl">
        <div className="flex-1 overflow-hidden flex">
          <Tabs
            defaultValue="general"
            orientation="vertical"
            className="flex w-full h-full"
            value={activeTab}
            onValueChange={setActiveTab}
          >
            {/* Sidebar Tabs */}
            <TabsList className="flex flex-col w-64 h-full bg-slate-50/50 border-r p-5 justify-start items-stretch gap-1 rounded-none">
              <div className="flex items-center gap-2 px-3 py-4 mb-2">
                <Settings className="w-5 h-5 text-primary" />
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
                value="preferences"
                className="justify-start gap-3 px-4 py-2.5 data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all rounded-lg"
              >
                <Palette className="w-4 h-4" />
                <span className="font-medium">Préférences</span>
              </TabsTrigger>
            </TabsList>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-10">
              <TabsContent value="general" className="mt-0 space-y-10">
                <div>
                  <h2 className="text-2xl font-bold mb-2 text-slate-900 transition-all">Options basiques</h2>
                  <p className="text-sm text-muted-foreground mb-8">
                    Configurez les paramètres globaux de l'application.
                  </p>
                  
                  <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-8 shadow-sm">
                    <div className="flex items-center justify-between gap-8">
                      <div className="space-y-1">
                        <Label className="text-base font-semibold">Mode développeur</Label>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          Active les outils de diagnostic et les logs détaillés dans l'interface pour le débogage.
                        </p>
                      </div>
                      <Switch />
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="agent" className="mt-0 space-y-10">
                <div>
                  <h2 className="text-2xl font-bold mb-2 text-slate-900">Contrôle de l'agent</h2>
                  <p className="text-sm text-muted-foreground mb-8">
                    Personnalisez le comportement et les réponses de votre assistant.
                  </p>

                  <div className="space-y-10">
                    <div className="space-y-4">
                      <Label className="text-sm font-bold uppercase tracking-wider opacity-70">Ton de l'agent</Label>
                      <div className="grid grid-cols-3 gap-3">
                        {["Professionnel", "Amical", "Concise"].map((tone) => (
                          <Button
                            key={tone}
                            variant="outline"
                            className="justify-center h-11 border-slate-200 hover:border-primary hover:text-primary transition-colors font-medium rounded-xl"
                          >
                            {tone}
                          </Button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <Label className="text-sm font-bold uppercase tracking-wider opacity-70">Instructions globales</Label>
                      <Textarea
                        placeholder="Ex: Réponds toujours de manière polie et utilise le vouvoiement..."
                        className="min-h-[180px] resize-none border-slate-200 focus:border-primary focus:ring-primary rounded-xl p-4 text-sm"
                      />
                      <p className="text-xs text-muted-foreground italic">
                        Ces instructions seront injectées dans le système pour influencer chaque réponse de l'agent.
                      </p>
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="accounts" className="mt-0 space-y-10">
                <div>
                  <h2 className="text-2xl font-bold mb-2 text-slate-900">Gestion des comptes</h2>
                  <p className="text-sm text-muted-foreground mb-8">
                    Gérez les sources de données et les comptes liés à votre assistant.
                  </p>

                  <div className="bg-white border border-slate-200 rounded-2xl divide-y divide-slate-100 overflow-hidden shadow-sm">
                    <div className="p-6 flex items-center justify-between hover:bg-slate-50/50 transition-colors">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 border border-slate-100">
                          <Instagram className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800">Compte principal</p>
                          <p className="text-xs text-muted-foreground">Indexé le 15 mars 2024 • 2,450 messages</p>
                        </div>
                      </div>
                      <Button variant="ghost" size="icon" className="text-slate-400 hover:text-destructive transition-colors">
                        <Trash2 className="w-5 h-5" />
                      </Button>
                    </div>

                    <div className="p-6 bg-slate-50/30">
                      <Button variant="outline" className="w-full h-12 gap-2 border-dashed border-slate-300 hover:border-primary hover:text-primary hover:bg-white transition-all rounded-xl">
                        <Import className="w-4 h-4" />
                        Importer de nouvelles conversations
                      </Button>
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="preferences" className="mt-0 space-y-10">
                <div>
                  <h2 className="text-2xl font-bold mb-2 text-slate-900">Préférences</h2>
                  <p className="text-sm text-muted-foreground mb-8">
                    Ajustez l'apparence visuelle pour une expérience personnalisée.
                  </p>

                  <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-8 shadow-sm">
                    <div className="space-y-5">
                      <Label className="text-sm font-bold uppercase tracking-wider opacity-70">Thème de l'interface</Label>
                      <div className="grid grid-cols-3 gap-4">
                        {["Clair", "Sombre", "Système"].map((theme) => (
                          <div
                            key={theme}
                            className="flex flex-col gap-3 cursor-pointer group"
                          >
                            <div className={cn(
                              "aspect-video rounded-xl border-2 flex items-center justify-center transition-all bg-slate-50 group-hover:scale-[1.02]",
                              theme === "Clair" ? "bg-white border-primary ring-2 ring-primary/10" : "bg-slate-900 border-transparent shadow-md group-hover:border-slate-300"
                            )}>
                              <div className={cn(
                                "w-14 h-2 rounded-full",
                                theme === "Clair" ? "bg-slate-200" : "bg-slate-700"
                              )} />
                            </div>
                            <span className="text-xs text-center font-bold text-slate-600 capitalize group-hover:text-primary transition-colors">{theme}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}
