import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Wizard } from "./Wizard";
import type { EnginePayload } from "@/lib/types";

const base: EnginePayload = {
  state: "SETUP", failures: 0,
  pointing: { valid: false, ra_deg: 0, dec_deg: 0, roll_deg: 0, matches: 0, prob: 1, solve_age_s: null },
  nav: null,
  origin_x: 640, origin_y: 360, image_w: 1280, image_h: 720,
  finder_rotation: 0, fov_h_deg: 8.86,
  has_calibration: false, image_size: null,
  controls: [], sync: { in_progress: false, candidates: [], selected_idx: null, error: null },
  stellarium: { active: false, address: null }, lx200: { active: false, address: null },
  webserver: { url: null }, audio_enabled: true,
  camera: { connected: false, all_centroids: null, matched_centroids: null },
  dev_mode: false, min_matches: 8, max_prob: 0.2, sample_active: null,
};

describe("Wizard", () => {
  it("renders the setup step in SETUP state", () => {
    render(<Wizard state={{ ...base, state: "SETUP" }} />);
    expect(
      screen.getByText(/Make sure you can see stars/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^next$/i }),
    ).toBeInTheDocument();
  });

  it("renders the sync step in SYNC state", () => {
    render(<Wizard state={{ ...base, state: "SYNC" }} />);
    expect(
      screen.getByText(/Pick any bright star/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^next$/i }),
    ).toBeInTheDocument();
  });

  it("renders LOCK badge when tracking is valid", () => {
    const s = { ...base, state: "TRACKING" as const,
      pointing: { ...base.pointing, valid: true, solve_age_s: 0.2 } };
    render(<Wizard state={s} />);
    expect(screen.getByText(/LOCK/)).toBeInTheDocument();
  });
});
