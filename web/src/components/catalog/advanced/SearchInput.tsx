import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function SearchInput({ value, onChange, placeholder }: Props) {
  return (
    <div className="relative">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "Search NGC / IC / Messier / star name…"}
        className="pr-8"
      />
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="absolute top-1/2 right-1 -translate-y-1/2"
        >
          <X className="w-3 h-3" />
        </Button>
      )}
    </div>
  );
}
