/**
 * Learner ID management with cookie storage
 */

const LEARNER_ID_COOKIE = "ltt_learner_id";
const COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year

/**
 * Generate a new learner ID
 */
export function generateLearnerId(): string {
  const chars = "abcdef0123456789";
  let id = "learner-";
  for (let i = 0; i < 8; i++) {
    id += chars[Math.floor(Math.random() * chars.length)];
  }
  return id;
}

/**
 * Get learner ID from cookie, or generate and store a new one
 */
export function getOrCreateLearnerId(): string {
  // Check cookie first
  const stored = getLearnerId();
  if (stored) return stored;

  // Generate new ID and store it
  const newId = generateLearnerId();
  setLearnerId(newId);
  return newId;
}

/**
 * Get learner ID from cookie
 */
export function getLearnerId(): string | null {
  if (typeof document === "undefined") return null;

  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === LEARNER_ID_COOKIE) {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * Set learner ID in cookie
 */
export function setLearnerId(id: string): void {
  if (typeof document === "undefined") return;

  document.cookie = `${LEARNER_ID_COOKIE}=${encodeURIComponent(id)}; max-age=${COOKIE_MAX_AGE}; path=/; SameSite=Lax`;
}

/**
 * Validate learner ID format
 */
export function isValidLearnerId(id: string): boolean {
  return /^learner-[a-f0-9]{6,12}$/.test(id);
}
