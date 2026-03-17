import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import * as v from "valibot";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  type FieldDefinition,
  FormRenderer,
} from "@/components/ui/form/form-renderer";
import { createProject, updateProject } from "@/lib/api";
import type { Project } from "@/lib/types";

const ProjectSchema = v.object({
  title: v.pipe(v.string(), v.minLength(1, "Le titre est requis")),
  description: v.optional(v.string()),
  tone: v.optional(v.picklist(["Professionnel", "Amical", "Concise"])),
  instructions: v.optional(v.pipe(v.string(), v.maxLength(1000))),
});

type ProjectValues = v.InferOutput<typeof ProjectSchema>;

interface NewProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewProjectModal({ open, onOpenChange }: NewProjectModalProps) {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (values: ProjectValues) => createProject(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Projet créé avec succès");
      onOpenChange(false);
    },
    onError: () => {
      toast.error("Erreur lors de la création du projet");
    },
  });

  const fields: FieldDefinition[] = [
    {
      name: "title",
      label: "Titre du projet",
      type: "text",
      placeholder: "Ex: Recherche Marketing",
    },
    {
      name: "description",
      label: "Description",
      type: "textarea",
      placeholder: "De quoi traite ce projet ?",
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Nouveau projet</DialogTitle>
          <DialogDescription>
            Créez un nouveau projet pour organiser vos conversations.
          </DialogDescription>
        </DialogHeader>
        <FormRenderer
          schema={ProjectSchema}
          defaultValues={{ title: "", description: "" }}
          onSubmit={(values) => createMutation.mutate(values as ProjectValues)}
          fields={fields}
        />
      </DialogContent>
    </Dialog>
  );
}

interface ProjectSettingsModalProps {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProjectSettingsModal({
  project,
  open,
  onOpenChange,
}: ProjectSettingsModalProps) {
  const queryClient = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: (values: ProjectValues) => updateProject(project.id, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      toast.success("Réglages du projet mis à jour");
      onOpenChange(false);
    },
  });

  const fields: FieldDefinition[] = [
    { name: "title", label: "Titre du projet", type: "text" },
    { name: "description", label: "Description", type: "textarea" },
    {
      name: "tone",
      label: "Ton de l'agent",
      type: "select",
      options: [
        { label: "Professionnel", value: "Professionnel" },
        { label: "Amical", value: "Amical" },
        { label: "Concise", value: "Concise" },
      ],
    },
    {
      name: "instructions",
      label: "Instructions spécifiques",
      type: "textarea",
      placeholder: "Instructions pour ce projet uniquement...",
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Réglages du projet</DialogTitle>
          <DialogDescription>
            Personnalisez les détails et le comportement de l'assistant pour ce
            projet.
          </DialogDescription>
        </DialogHeader>
        <FormRenderer
          schema={ProjectSchema}
          defaultValues={{
            title: project.title,
            description: project.description || "",
            tone: project.tone || "Professionnel",
            instructions: project.instructions || "",
          }}
          onSubmit={(values) => updateMutation.mutate(values as ProjectValues)}
          fields={fields}
        />
      </DialogContent>
    </Dialog>
  );
}
