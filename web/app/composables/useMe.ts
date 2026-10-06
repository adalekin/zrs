/** The signed-in person, their roles and the lists of the installation (GET /v1/me). */
export function useMe() {
  return useState<Me | null>('me', () => null)
}
