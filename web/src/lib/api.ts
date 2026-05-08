async function post(path: string, body?: unknown): Promise<void> {
  const init: RequestInit = { method: "POST" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const resp = await fetch(path, init);
  if (resp.status >= 400) {
    throw new Error(`POST ${path} → ${resp.status}: ${await resp.text()}`);
  }
}

export const api = {
  wizardAdvance: () => post("/api/wizard/advance"),
  syncRetry: () => post("/api/sync/retry"),
  syncSelect: (idx: number) => post("/api/sync/select", { idx }),
  useCalibration: () => post("/api/calibration/use-previous"),
  setControl: (name: string, value: number) => post("/api/control", { name, value }),
  clearGoto: () => post("/api/goto/clear"),
  setGoto: (ra_deg: number, dec_deg: number) =>
    post("/api/goto/set", { ra_deg, dec_deg }),
  setSettings: (s: {
    audio_enabled?: boolean;
    hidpi?: boolean;
    location?: { latitude: number; longitude: number } | null;
  }) => post("/api/settings", s),
  setAdvanced: (s: { min_matches?: number; max_prob?: number }) =>
    post("/api/settings", s),
  dev: {
    injectSample: (name: string | null) =>
      post("/api/dev/inject-sample", { name }),
    injectTarget: (ra_deg: number, dec_deg: number) =>
      post("/api/dev/inject-target", { ra_deg, dec_deg }),
    captureFrame: async (): Promise<{ path: string | null; error?: string }> => {
      const resp = await fetch("/api/dev/capture-frame", { method: "POST" });
      return await resp.json();
    },
  },
};
