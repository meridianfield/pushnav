import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AdvancedTab } from "./AdvancedTab";

// AdvancedTab imports openngc.json + hyg-bright.json at module load, so
// these need real files. The build_catalogs step has populated them.

describe("AdvancedTab", () => {
  it("renders the empty-state hint with no query", () => {
    render(<AdvancedTab selected={null} onSelect={() => {}} />);
    expect(screen.getByText(/Type to search/i)).toBeInTheDocument();
  });

  it("filters and selects an NGC result", async () => {
    const onSelect = vi.fn();
    render(<AdvancedTab selected={null} onSelect={onSelect} />);
    const input = screen.getByPlaceholderText(/Search NGC/i);
    fireEvent.change(input, { target: { value: "M31" } });
    // Debounced 100 ms — give vitest a tick.
    await new Promise((r) => setTimeout(r, 200));
    const row = screen.getByText("NGC 224");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ source: "ngc", id: "NGC 224" }),
    );
  });
});
