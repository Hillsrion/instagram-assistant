import { useForm } from "@tanstack/react-form";

import type * as v from "valibot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type FieldDefinition = {
  name: string;
  label: string;
  description?: string;
  placeholder?: string;
  type: "text" | "switch" | "textarea" | "select";
  options?: { label: string; value: string }[];
};

interface FormRendererProps {
  schema: v.BaseSchema<any, any, any>;
  defaultValues: any;
  onSubmit: (values: any) => void | Promise<void>;
  fields: FieldDefinition[];
  className?: string;
  submitLabel?: string;
  disabled?: boolean;
}

export function FormRenderer({
  schema,
  defaultValues,
  onSubmit,
  fields,
  className,
  submitLabel = "Enregistrer",
  disabled = false,
}: FormRendererProps) {
  const form = useForm({
    defaultValues,

    validators: {
      onChange: schema,
    },
    onSubmit: async ({ value }) => {
      await onSubmit(value);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
      className={cn("space-y-6", className)}
    >
      <div className="space-y-6">
        {fields.map((field) => (
          <form.Field
            key={field.name}
            name={field.name}
            children={(fieldApi) => (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-1">
                    <Label
                      htmlFor={fieldApi.name}
                      className="text-base font-semibold"
                    >
                      {field.label}
                    </Label>
                    {field.description && (
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {field.description}
                      </p>
                    )}
                  </div>
                  {field.type === "switch" && (
                    <Switch
                      id={fieldApi.name}
                      checked={fieldApi.state.value}
                      onCheckedChange={(checked) =>
                        fieldApi.handleChange(checked)
                      }
                      disabled={disabled}
                    />
                  )}
                </div>

                {field.type === "text" && (
                  <Input
                    id={fieldApi.name}
                    value={fieldApi.state.value}
                    onBlur={fieldApi.handleBlur}
                    onChange={(e) => fieldApi.handleChange(e.target.value)}
                    placeholder={field.placeholder}
                    className="rounded-xl border-slate-200 focus:border-primary focus:ring-primary"
                    disabled={disabled}
                  />
                )}

                {field.type === "textarea" && (
                  <Textarea
                    id={fieldApi.name}
                    value={fieldApi.state.value}
                    onBlur={fieldApi.handleBlur}
                    onChange={(e) => fieldApi.handleChange(e.target.value)}
                    placeholder={field.placeholder}
                    className="min-h-[120px] resize-none border-slate-200 focus:border-primary focus:ring-primary rounded-xl p-4 text-sm"
                    disabled={disabled}
                  />
                )}

                {field.type === "select" && (
                  <Select
                    value={fieldApi.state.value}
                    onValueChange={(value) => fieldApi.handleChange(value)}
                  >
                    <SelectTrigger
                      id={fieldApi.name}
                      className="rounded-xl border-slate-200 focus:border-primary focus:ring-primary"
                      disabled={disabled}
                    >
                      <SelectValue placeholder={field.placeholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {field.options?.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                {fieldApi.state.meta.errors.length > 0 && (
                  <p className="text-xs font-medium text-destructive">
                    {fieldApi.state.meta.errors.join(", ")}
                  </p>
                )}
              </div>
            )}
          />
        ))}
      </div>

      <div className="flex justify-end pt-4">
        <form.Subscribe
          selector={(state) => [state.canSubmit, state.isSubmitting]}
          children={([canSubmit, isSubmitting]) => (
            <Button
              type="submit"
              disabled={!canSubmit || isSubmitting || disabled}
              className="h-11 px-8 rounded-xl font-bold transition-all shadow-md hover:shadow-lg active:scale-95"
            >
              {isSubmitting ? "Sauvegarde..." : submitLabel}
            </Button>
          )}
        />
      </div>
    </form>
  );
}
