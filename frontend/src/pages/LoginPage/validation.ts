const USERNAME_PATTERN = /^[A-Za-z0-9_-]+$/

export function isValidRegistrationUsername(username: string): boolean {
  return USERNAME_PATTERN.test(username.trim())
}
