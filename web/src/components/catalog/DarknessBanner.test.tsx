import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DarknessBanner } from "./DarknessBanner";

const CHENNAI = { latitude: 13.0878, longitude: 80.2785 };
const LONDON = { latitude: 51.5, longitude: -0.13 };

describe("DarknessBanner", () => {
  it("renders nothing when it's dark", () => {
    const { container } = render(
      <DarknessBanner
        location={CHENNAI}
        evalAt={new Date("2026-10-10T16:00:00Z")}
        appliedOffsetMin={0}
        onApply={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("jumps to darkness in whole 5-minute steps", () => {
    // Daytime at 06:00 UTC; astropy has it dark from 13:34 UTC
    const onApply = vi.fn();
    render(
      <DarknessBanner
        location={CHENNAI}
        evalAt={new Date("2026-10-10T06:00:00Z")}
        appliedOffsetMin={30}
        onApply={onApply}
      />,
    );
    expect(screen.getByText(/^Daytime at/)).toBeInTheDocument();
    expect(screen.getByText(/The sky gets dark at/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show then" }));
    const jump = onApply.mock.calls[0][0] as number;
    expect(jump % 5).toBe(0);
    // 7 h 34 min after evalAt, on top of the 30 min already applied
    expect(jump).toBeGreaterThanOrEqual(30 + 7 * 60 + 30);
    expect(jump).toBeLessThanOrEqual(30 + 7 * 60 + 40);
  });

  it("says when the sky never gets fully dark", () => {
    render(
      <DarknessBanner
        location={LONDON}
        evalAt={new Date("2026-06-21T12:00:00Z")}
        appliedOffsetMin={0}
        onApply={() => {}}
      />,
    );
    expect(screen.getByText(/doesn't get fully dark tonight/)).toBeInTheDocument();
    expect(screen.getByText(/Sun 15° below the horizon/)).toBeInTheDocument();
  });
});
