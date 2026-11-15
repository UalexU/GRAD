// Prefer explicitly labeled earned totals. GPA hours and quality points are different columns.
export function earnedCredits(text) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const totals = normalized.match(/\btranscript totals\b.*\battempt hours passed hours earned hours gpa hours quality points gpa\b(.*)$/i);
  const overall = totals?.[1].match(/\boverall\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/i);
  if (overall && /^\d+(?:\.\d+)?$/.test(overall[3])) return overall[3];
  const matches = [...normalized.matchAll(/\b(?:total (?:credits|hours|units) earned|total earned (?:credits|hours|units))\s*[:=]?\s*(\d+(?:\.\d+)?)(?![\d.])/gi)];
  const totalsFound = [...new Set(matches.map(match => Number(match[1])))];
  return totalsFound.length === 1 ? String(totalsFound[0]) : null;
}
