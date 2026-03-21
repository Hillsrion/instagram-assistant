import { Import, Instagram, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AccountsTab() {
  return (
    <div className="mt-0 space-y-10">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-slate-900">
          Gestion des comptes
        </h2>
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
                <p className="text-xs text-muted-foreground">
                  Indexé le 15 mars 2024 • 2,450 messages
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="text-slate-400 hover:text-destructive transition-colors"
            >
              <Trash2 className="w-5 h-5" />
            </Button>
          </div>

          <div className="p-6 bg-slate-50/30">
            <Button
              variant="outline"
              className="w-full h-12 gap-2 border-dashed border-slate-300 hover:border-primary hover:text-primary hover:bg-white transition-all rounded-xl"
            >
              <Import className="w-4 h-4" />
              Importer de nouvelles conversations
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
