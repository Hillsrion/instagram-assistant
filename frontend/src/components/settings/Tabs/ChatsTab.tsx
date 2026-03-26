import { AlertTriangle, Download, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { deleteAllChats, exportChats } from "@/lib/api/chats";

export function ChatsTab() {
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const data = await exportChats();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `chats_export_${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Chats exportés avec succès");
    } catch (error) {
      toast.error("Erreur lors de l'exportation");
      console.error(error);
    } finally {
      setIsExporting(false);
    }
  };

  const handleDeleteAll = async () => {
    if (confirmText !== "TOUT SUPPRIMER") return;

    setIsDeleting(true);
    try {
      await deleteAllChats();
      toast.success("Tous les chats ont été supprimés");
      setDeleteDialogOpen(false);
      setConfirmText("");
      // Force refresh to update the sidebar and clear current chat
      window.location.href = "/";
    } catch (error) {
      toast.error("Erreur lors de la suppression");
      console.error(error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="mt-0 space-y-10">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-slate-900">Mes Chats</h2>
        <p className="text-sm text-muted-foreground mb-8">
          Gérez vos sessions de chat IA, exportez-les ou supprimez-les
          définitivement.
        </p>

        <div className="space-y-6">
          {/* Export Section */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold mb-2 text-slate-900">
              Exporter les données
            </h3>
            <p className="text-sm text-slate-600 mb-4">
              Téléchargez l'intégralité de vos chats au format JSON pour les
              sauvegarder ou les utiliser ailleurs.
            </p>
            <Button
              onClick={handleExport}
              disabled={isExporting}
              className="gap-2"
            >
              <Download className="w-4 h-4" />
              {isExporting ? "Exportation..." : "Exporter tous les chats"}
            </Button>
          </div>

          {/* Danger Zone Section */}
          <div className="bg-destructive/5 border border-destructive/10 rounded-2xl p-6">
            <h3 className="text-lg font-semibold text-destructive mb-2 font-display">
              Zone de danger
            </h3>
            <p className="text-sm text-destructive/80 mb-4">
              La suppression de tous vos chats est définitive et ne peut pas
              être annulée.
            </p>

            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive" className="gap-2">
                  <Trash2 className="w-4 h-4" />
                  Supprimer tous les chats
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-red-600">
                    <AlertTriangle className="w-5 h-5" />
                    Confirmation de suppression
                  </DialogTitle>
                  <DialogDescription className="pt-2 text-slate-600">
                    Cette action supprimera définitivement{" "}
                    <span className="font-bold">TOUS</span> vos chats de la base
                    de données locale. C'est irréveresible.
                  </DialogDescription>
                </DialogHeader>

                <div className="py-6 space-y-3">
                  <p className="text-sm font-medium text-slate-700">
                    Veuillez taper{" "}
                    <span className="font-bold text-red-600">
                      TOUT SUPPRIMER
                    </span>{" "}
                    pour confirmer :
                  </p>
                  <input
                    placeholder="TOUT SUPPRIMER"
                    value={confirmText}
                    onChange={(e) =>
                      setConfirmText(e.target.value.toUpperCase())
                    }
                    className="w-full h-10 px-3 bg-white border border-destructive/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-destructive/50 font-mono"
                  />
                </div>

                <DialogFooter className="gap-2 sm:gap-0">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setDeleteDialogOpen(false);
                      setConfirmText("");
                    }}
                    className="hover:bg-slate-100"
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleDeleteAll}
                    disabled={confirmText !== "TOUT SUPPRIMER" || isDeleting}
                  >
                    {isDeleting ? "Suppression..." : "Tout supprimer"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>
    </div>
  );
}
