export const SIGN_IN_PATH = '/sign-in'

/** The sign-in route, told where to return the person after the sign-in. */
export function signInLocation(callbackUrl: string): string {
  return `${SIGN_IN_PATH}?${new URLSearchParams({ callbackUrl })}`
}
