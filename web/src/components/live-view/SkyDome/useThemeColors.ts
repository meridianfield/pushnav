import { useEffect, useState } from "react";
import type { ThemeColors } from "./types";

function oklchToHex(l: number, c: number, h: number): string {
  const hRad = (h * Math.PI) / 180;
  const a = c * Math.cos(hRad);
  const b = c * Math.sin(hRad);

  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.291485548 * b;

  const lCubed = l_ * l_ * l_;
  const mCubed = m_ * m_ * m_;
  const sCubed = s_ * s_ * s_;

  let r = +4.0767416621 * lCubed - 3.3077115913 * mCubed + 0.2309699292 * sCubed;
  let g = -1.2684380046 * lCubed + 2.6097574011 * mCubed - 0.3413193965 * sCubed;
  let bVal = -0.0041960863 * lCubed - 0.7034186147 * mCubed + 1.707614701 * sCubed;

  r = Math.max(0, Math.min(1, r));
  g = Math.max(0, Math.min(1, g));
  bVal = Math.max(0, Math.min(1, bVal));

  const toSrgb = (x: number) => {
    const val = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
    return Math.round(Math.max(0, Math.min(255, val * 255)));
  };

  const rr = toSrgb(r).toString(16).padStart(2, "0");
  const gg = toSrgb(g).toString(16).padStart(2, "0");
  const bb = toSrgb(bVal).toString(16).padStart(2, "0");

  return `#${rr}${gg}${bb}`;
}

function parseOklch(colorStr: string): { l: number; c: number; h: number } | null {
  const match = colorStr.match(/oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (match) {
    return {
      l: parseFloat(match[1]),
      c: parseFloat(match[2]),
      h: parseFloat(match[3]),
    };
  }
  return null;
}

function getCssColorAsHex(varName: string): string {
  if (typeof document === "undefined") return "#888888";

  const temp = document.createElement("div");
  temp.style.color = `var(${varName})`;
  temp.style.display = "none";
  document.body.appendChild(temp);
  const computedColor = getComputedStyle(temp).color;
  document.body.removeChild(temp);

  const oklch = parseOklch(computedColor);
  if (oklch) return oklchToHex(oklch.l, oklch.c, oklch.h);

  const rgbMatch = computedColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (rgbMatch) {
    const r = parseInt(rgbMatch[1]).toString(16).padStart(2, "0");
    const g = parseInt(rgbMatch[2]).toString(16).padStart(2, "0");
    const b = parseInt(rgbMatch[3]).toString(16).padStart(2, "0");
    return `#${r}${g}${b}`;
  }

  return "#888888";
}

const DEFAULTS: ThemeColors = {
  gridLines: "#5a1a1a",
  gridLabels: "#a83a3a",
  horizon: "#a83a3a",
  ground: "#3a1010",
  pointing: "#ffd460",
  target: "#fef0f0",
  line: "#a83a3a",
};

export function useThemeColors(): ThemeColors {
  const [colors, setColors] = useState<ThemeColors>(DEFAULTS);

  useEffect(() => {
    function read(): ThemeColors {
      const mutedForeground = getCssColorAsHex("--muted-foreground");
      const foreground = getCssColorAsHex("--foreground");
      const accent = getCssColorAsHex("--accent");
      const primaryForeground = getCssColorAsHex("--primary-foreground");
      return {
        gridLines: mutedForeground,
        gridLabels: foreground,
        horizon: foreground,
        ground: accent,
        // Bright yellow-ish for the current-pointing marker so it's
        // distinguishable from the red dome / target on the red palette.
        pointing: "#ffd460",
        // Cream/pale for the target — high contrast against the red dome.
        target: primaryForeground,
        line: foreground,
      };
    }

    setColors(read());

    const observer = new MutationObserver(() => setColors(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  return colors;
}
