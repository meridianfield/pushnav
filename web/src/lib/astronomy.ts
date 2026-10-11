// Astronomical calculations for fixed RA/Dec objects (stars, DSOs)
// Based on standard spherical astronomy formulas

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

function clamp(x: number, a: number, b: number): number {
  return Math.min(b, Math.max(a, x));
}

function wrap360(deg: number): number {
  deg %= 360;
  return deg < 0 ? deg + 360 : deg;
}

// Convert JS Date -> Julian Day (UTC)
function julianDay(date: Date): number {
  return date.getTime() / 86400000 + 2440587.5;
}

// GMST in degrees (Meeus-style approximation)
function gmstDeg(date: Date): number {
  const jd = julianDay(date);
  const T = (jd - 2451545.0) / 36525.0;
  const gmst =
    280.46061837 +
    360.98564736629 * (jd - 2451545.0) +
    0.000387933 * T * T -
    (T * T * T) / 38710000.0;
  return wrap360(gmst);
}

// Local Sidereal Time in degrees (east-positive longitude)
function lstDeg(date: Date, lonDeg: number): number {
  return wrap360(gmstDeg(date) + lonDeg);
}

// Parse RA string like "19h 30m 43.28s" to decimal hours
export function parseRA(ra: string): number | null {
  // Try format: "19h 30m 43.28s"
  const hmsMatch = ra.match(/(\d+)h\s*(\d+)m\s*([\d.]+)s/i);
  if (hmsMatch) {
    const h = parseFloat(hmsMatch[1]);
    const m = parseFloat(hmsMatch[2]);
    const s = parseFloat(hmsMatch[3]);
    return h + m / 60 + s / 3600;
  }

  // Try format: "19:30:43.28"
  const colonMatch = ra.match(/(\d+):(\d+):([\d.]+)/);
  if (colonMatch) {
    const h = parseFloat(colonMatch[1]);
    const m = parseFloat(colonMatch[2]);
    const s = parseFloat(colonMatch[3]);
    return h + m / 60 + s / 3600;
  }

  // Try decimal hours
  const decimal = parseFloat(ra);
  if (!isNaN(decimal) && decimal >= 0 && decimal < 24) {
    return decimal;
  }

  return null;
}

// Parse Dec string like "+27° 57' 34.83\"" to decimal degrees
export function parseDec(dec: string): number | null {
  // Try format: "+27° 57' 34.83\"" or "-5° 23' 12\""
  const dmsMatch = dec.match(/([+-]?\d+)[°]\s*(\d+)['']\s*([\d.]+)[""]/);
  if (dmsMatch) {
    const sign = dmsMatch[1].startsWith("-") ? -1 : 1;
    const d = Math.abs(parseFloat(dmsMatch[1]));
    const m = parseFloat(dmsMatch[2]);
    const s = parseFloat(dmsMatch[3]);
    return sign * (d + m / 60 + s / 3600);
  }

  // Try format without seconds: "+27° 57'"
  const dmMatch = dec.match(/([+-]?\d+)[°]\s*(\d+)['']/);
  if (dmMatch) {
    const sign = dmMatch[1].startsWith("-") ? -1 : 1;
    const d = Math.abs(parseFloat(dmMatch[1]));
    const m = parseFloat(dmMatch[2]);
    return sign * (d + m / 60);
  }

  // Try decimal degrees
  const decimal = parseFloat(dec);
  if (!isNaN(decimal) && decimal >= -90 && decimal <= 90) {
    return decimal;
  }

  return null;
}

export interface AltAzResult {
  altDeg: number;
  azDeg: number;
}

// Equatorial to horizontal coordinate conversion
export function altAzFromRaDec({
  raHours,
  decDeg,
  latDeg,
  lonDeg,
  date,
}: {
  raHours: number;
  decDeg: number;
  latDeg: number;
  lonDeg: number;
  date: Date;
}): AltAzResult {
  const raDeg = raHours * 15.0;
  const dec = decDeg * DEG2RAD;
  const lat = latDeg * DEG2RAD;

  const lst = lstDeg(date, lonDeg) * DEG2RAD;
  const ha = wrap360(lst * RAD2DEG - raDeg) * DEG2RAD;

  // altitude
  const sinAlt =
    Math.sin(dec) * Math.sin(lat) + Math.cos(dec) * Math.cos(lat) * Math.cos(ha);
  const alt = Math.asin(clamp(sinAlt, -1, 1));

  // azimuth (from north, eastward):
  // tan(az) = -sin(ha) cos(dec) / (sin(dec) cos(lat) - cos(dec) sin(lat) cos(ha))
  const y = -Math.sin(ha) * Math.cos(dec);
  const x = Math.sin(dec) * Math.cos(lat) - Math.cos(dec) * Math.sin(lat) * Math.cos(ha);
  const az = Math.atan2(y, x);
  const azDeg = wrap360(az * RAD2DEG);

  return { altDeg: alt * RAD2DEG, azDeg };
}

// Maximum altitude at upper transit
export function maxAltitudeDeg({
  decDeg,
  latDeg,
}: {
  decDeg: number;
  latDeg: number;
}): number {
  return 90 - Math.abs(latDeg - decDeg);
}

export type VisibilityStatus = "normal" | "never_rises" | "never_sets";

export interface RiseSetTransitResult {
  rise: Date | null;
  set: Date | null;
  transit: Date | null;
  status: VisibilityStatus;
}

// Rise/Set/Transit times for a given UTC date
export function riseSetTransitUtc({
  raHours,
  decDeg,
  latDeg,
  lonDeg,
  dateUtc,
  h0Deg = -0.566, // altitude threshold (includes refraction)
}: {
  raHours: number;
  decDeg: number;
  latDeg: number;
  lonDeg: number;
  dateUtc: Date;
  h0Deg?: number;
}): RiseSetTransitResult {
  // Work on the UTC day starting at 00:00:00
  const day0 = new Date(
    Date.UTC(
      dateUtc.getUTCFullYear(),
      dateUtc.getUTCMonth(),
      dateUtc.getUTCDate(),
      0,
      0,
      0
    )
  );

  const raDeg = raHours * 15.0;
  const dec = decDeg * DEG2RAD;
  const lat = latDeg * DEG2RAD;
  const h0 = h0Deg * DEG2RAD;

  // Compute hour angle at rise/set (H0)
  const cosH0 =
    (Math.sin(h0) - Math.sin(lat) * Math.sin(dec)) /
    (Math.cos(lat) * Math.cos(dec));

  // circumpolar / never rises cases
  if (cosH0 > 1) {
    // never reaches altitude h0 -> never rises
    return { rise: null, set: null, transit: null, status: "never_rises" };
  }

  const H0deg = Math.acos(clamp(cosH0, -1, 1)) * RAD2DEG;

  // Helper: convert target LST(deg) to UTC time via iteration
  function solveForLST(targetLSTdeg: number, guessDate: Date): Date {
    let t = new Date(guessDate.getTime());
    for (let i = 0; i < 5; i++) {
      const cur = lstDeg(t, lonDeg);
      let err = wrap360(targetLSTdeg - cur);
      if (err > 180) err -= 360;
      const hours = err / 15.0410686;
      t = new Date(t.getTime() + hours * 3600 * 1000);
      if (Math.abs(err) < 1e-4) break;
    }
    return t;
  }

  // LST of events
  const lstTransit = wrap360(raDeg);
  const lstRise = wrap360(raDeg - H0deg);
  const lstSet = wrap360(raDeg + H0deg);

  // Compute transit
  const transit = solveForLST(lstTransit, day0);

  let rise: Date | null = null;
  let set: Date | null = null;

  if (cosH0 >= -1 && cosH0 <= 1) {
    const hoursFromTransit = H0deg / 15.0410686;
    rise = solveForLST(
      lstRise,
      new Date(transit.getTime() - hoursFromTransit * 3600 * 1000)
    );
    set = solveForLST(
      lstSet,
      new Date(transit.getTime() + hoursFromTransit * 3600 * 1000)
    );

    // Keep events within the requested UTC day window
    const day1 = new Date(day0.getTime() + 24 * 3600 * 1000);
    if (rise < day0) rise = new Date(rise.getTime() + 24 * 3600 * 1000);
    if (rise >= day1) rise = new Date(rise.getTime() - 24 * 3600 * 1000);
    if (set < day0) set = new Date(set.getTime() + 24 * 3600 * 1000);
    if (set >= day1) set = new Date(set.getTime() - 24 * 3600 * 1000);
  }

  const status: VisibilityStatus = cosH0 < -1 ? "never_sets" : "normal";

  return { rise, set, transit, status };
}

// Format degrees as degrees with symbol
export function formatDegrees(deg: number, precision: number = 1): string {
  return `${deg.toFixed(precision)}°`;
}

// Format azimuth with cardinal direction
export function formatAzimuth(azDeg: number): string {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const index = Math.round(azDeg / 45) % 8;
  return `${azDeg.toFixed(1)}° ${directions[index]}`;
}
