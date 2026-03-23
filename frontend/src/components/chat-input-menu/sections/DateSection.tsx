import { format } from "date-fns";
import { fr } from "date-fns/locale";
import type { DateRange } from "react-day-picker";
import { Calendar } from "@/components/ui/calendar";

interface DateSectionProps {
  filterDate?: DateRange;
  setFilterDate: (date: DateRange | undefined) => void;
}

export function DateSection({ filterDate, setFilterDate }: DateSectionProps) {
  return (
    <div className="flex flex-col items-center justify-center p-0">
      <Calendar
        mode="range"
        selected={filterDate}
        onSelect={setFilterDate}
        initialFocus
        locale={fr}
        numberOfMonths={1}
        className="p-4"
      />
      <div className="w-full px-4 text-center mt-2 pb-4">
        {filterDate?.from ? (
          <div className="text-sm font-medium text-primary bg-primary/10 rounded-md py-1">
            {filterDate.to
              ? `${format(filterDate.from, "d MMM", { locale: fr })} - ${format(filterDate.to, "d MMM yyyy", { locale: fr })}`
              : format(filterDate.from, "d MMM yyyy", { locale: fr })}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            Sélectionnez une période
          </div>
        )}
      </div>
    </div>
  );
}
