// Returns the Date the UI should use for "now" in astronomical math.
// When the engine has PUSHNAV_TESTDATE set, this is the parsed UTC value
// it broadcasts in state.astro_now_iso. Otherwise it's the real `new Date()`.
// Wall-clock semantics (animation, solve_age_s, server cadences) are
// unaffected — those don't go through this helper.
export function astroNow(astroNowIso: string | null | undefined): Date {
  if (astroNowIso) return new Date(astroNowIso);
  return new Date();
}
