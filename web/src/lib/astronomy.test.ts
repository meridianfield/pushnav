import { describe, expect, it } from "vitest";

import {
  altAzFromRaDec,
  darknessAt,
  parseDec,
  parseRA,
  riseSetTransitUtc,
  sunAltitudeDeg,
} from "./astronomy";

describe("parseRA", () => {
  it("parses h/m/s format", () => {
    expect(parseRA("05h 35m 17.3s")).toBeCloseTo(5.5881, 3);
  });
  it("parses colon format", () => {
    expect(parseRA("05:35:17.3")).toBeCloseTo(5.5881, 3);
  });
  it("returns null on garbage", () => {
    expect(parseRA("not a coordinate")).toBeNull();
  });
});

describe("parseDec", () => {
  it("parses positive d/m/s", () => {
    expect(parseDec("+27° 57' 34.83\"")).toBeCloseTo(27.9597, 3);
  });
  it("parses negative d/m/s", () => {
    expect(parseDec("-05° 23' 28\"")).toBeCloseTo(-5.3911, 3);
  });
});

describe("altAzFromRaDec", () => {
  // Polaris should sit near zenith=lat for an observer at high northern latitude.
  it("Polaris from northern Europe is near 50° altitude", () => {
    const result = altAzFromRaDec({
      raHours: 2.5303,           // Polaris J2000
      decDeg: 89.2641,
      latDeg: 50.0,
      lonDeg: 0.0,
      date: new Date("2026-05-08T22:00:00Z"),
    });
    expect(result.altDeg).toBeGreaterThan(48);
    expect(result.altDeg).toBeLessThan(52);
  });

  // Reference positions from astropy (ICRS -> AltAz, no refraction) for
  // 2026-10-10T20:00:00Z. The app uses J2000 coordinates without
  // precession, so allow 1°. The old azimuth formula was off by up to ~13°
  // at mid latitudes (it scaled by cos²(lat)).
  const REFS: [string, number, number, string, number, number, number, number][] = [
    // site, lat, lon, object, RA h, Dec °, alt °, az °
    ["Chennai", 13.0878, 80.2785, "M31", 0.7123, 41.2692, 52.26, 324.02],
    ["Chennai", 13.0878, 80.2785, "M42", 5.5881, -5.3911, 42.16, 109.88],
    ["Chennai", 13.0878, 80.2785, "Achernar", 1.6286, -57.2367, 18.72, 188.55],
    ["Chennai", 13.0878, 80.2785, "Fomalhaut", 22.9608, -29.6222, 22.07, 230.25],
    ["Denver", 39.74, -104.99, "M13", 16.6949, 36.4613, 61.49, 85.03],
    ["Denver", 39.74, -104.99, "Vega", 18.6156, 38.7837, 40.83, 68.97],
    ["London", 51.5, -0.13, "M31", 0.7123, 41.2692, 53.78, 85.29],
    ["London", 51.5, -0.13, "M13", 16.6949, 36.4613, 40.31, 280.59],
    ["London", 51.5, -0.13, "Vega", 18.6156, 38.7837, 59.65, 261.12],
    ["Sydney", -33.87, 151.21, "M42", 5.5881, -5.3911, 52.37, 313.33],
    ["Sydney", -33.87, 151.21, "Omega Cen", 13.4469, -47.4794, 23.42, 132.75],
    ["Sydney", -33.87, 151.21, "Achernar", 1.6286, -57.2367, 29.98, 218.72],
  ];
  it.each(REFS)("%s (lat %s, lon %s): %s matches astropy", (_site, lat, lon, _obj, ra, dec, alt, az) => {
    const r = altAzFromRaDec({
      raHours: ra, decDeg: dec, latDeg: lat, lonDeg: lon,
      date: new Date("2026-10-10T20:00:00Z"),
    });
    expect(Math.abs(r.altDeg - alt)).toBeLessThan(1);
    const dAz = ((r.azDeg - az + 540) % 360) - 180;
    expect(Math.abs(dAz)).toBeLessThan(1);
  });
});

const SITES: Record<string, [number, number]> = {
  Chennai: [13.0878, 80.2785],
  Denver: [39.74, -104.99],
  London: [51.5, -0.13],
  Sydney: [-33.87, 151.21],
};

describe("sunAltitudeDeg", () => {
  // astropy get_sun -> AltAz, no refraction
  const REFS: [string, string, number][] = [
    ["Chennai", "2026-10-10T06:00:00Z", 69.225],
    ["Chennai", "2026-10-10T14:00:00Z", -24.394],
    ["Denver", "2026-10-10T20:00:00Z", 40.41],
    ["London", "2026-06-21T12:00:00Z", 61.933],
    ["London", "2026-12-21T00:00:00Z", -61.934],
    ["Sydney", "2026-10-10T20:00:00Z", 7.537],
  ];
  it.each(REFS)("%s at %s matches astropy", (site, iso, alt) => {
    const [latDeg, lonDeg] = SITES[site];
    const a = sunAltitudeDeg({ latDeg, lonDeg, date: new Date(iso) });
    expect(Math.abs(a - alt)).toBeLessThan(0.5);
  });
});

describe("darknessAt", () => {
  const minutesApart = (a: Date, iso: string) =>
    Math.abs(a.getTime() - new Date(iso).getTime()) / 60_000;

  // astropy: first minute with the Sun below -18°
  const REFS: [string, string, string, string][] = [
    ["Chennai", "2026-10-10T06:00:00Z", "day", "2026-10-10T13:34:00Z"],
    ["Denver", "2026-10-10T16:00:00Z", "day", "2026-10-11T01:58:00Z"],
    ["Sydney", "2026-10-10T00:00:00Z", "day", "2026-10-10T09:31:00Z"],
    ["London", "2026-12-21T12:00:00Z", "day", "2026-12-21T17:58:00Z"],
  ];
  it.each(REFS)("%s from %s: %s, dark from %s", (site, iso, status, darkIso) => {
    const [latDeg, lonDeg] = SITES[site];
    const d = darknessAt({ latDeg, lonDeg, date: new Date(iso) });
    expect(d.status).toBe(status);
    if (!("darkFrom" in d)) throw new Error("expected darkFrom");
    expect(minutesApart(d.darkFrom, darkIso)).toBeLessThan(3);
  });

  it("is dark when the Sun is below -18°", () => {
    const [latDeg, lonDeg] = SITES.Chennai;
    expect(darknessAt({ latDeg, lonDeg, date: new Date("2026-10-10T14:00:00Z") }))
      .toEqual({ status: "dark" });
  });

  it("is twilight between sunset and darkness", () => {
    const [latDeg, lonDeg] = SITES.Chennai;
    const d = darknessAt({ latDeg, lonDeg, date: new Date("2026-10-10T13:10:00Z") });
    expect(d.status).toBe("twilight");
    if (!("darkFrom" in d)) throw new Error("expected darkFrom");
    expect(minutesApart(d.darkFrom, "2026-10-10T13:34:00Z")).toBeLessThan(3);
  });

  // London at midsummer never gets astronomically dark: astropy has the
  // Sun bottoming out at -15.07° at 00:02 UTC
  it("reports the darkest moment when it never gets dark", () => {
    const [latDeg, lonDeg] = SITES.London;
    const d = darknessAt({ latDeg, lonDeg, date: new Date("2026-06-21T12:00:00Z") });
    expect(d.status).toBe("day");
    if (!("darkest" in d)) throw new Error("expected darkest");
    expect(minutesApart(d.darkest, "2026-06-22T00:02:00Z")).toBeLessThan(10);
    expect(Math.abs(d.darkestSunAltDeg - -15.07)).toBeLessThan(0.5);
  });
});

describe("riseSetTransitUtc", () => {
  it("computes a transit and a rise for Vega at lat 13°", () => {
    const result = riseSetTransitUtc({
      raHours: 18.6156,           // Vega
      decDeg: 38.7837,
      latDeg: 13.0878,            // Chennai
      lonDeg: 80.2785,
      dateUtc: new Date("2026-05-08T00:00:00Z"),
    });
    expect(result.status).toBe("normal");
    expect(result.transit).toBeInstanceOf(Date);
    expect(result.rise).toBeInstanceOf(Date);
    expect(result.set).toBeInstanceOf(Date);
  });
  it("flags 'never_rises' for southern object at northern latitude", () => {
    const result = riseSetTransitUtc({
      raHours: 12.0,
      decDeg: -85.0,
      latDeg: 60.0,
      lonDeg: 0.0,
      dateUtc: new Date("2026-05-08T00:00:00Z"),
    });
    expect(result.status).toBe("never_rises");
    expect(result.rise).toBeNull();
  });
});
