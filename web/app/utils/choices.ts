/** The choices of a list, with the value the request already holds kept among them. */
export function withCurrent<T extends { id: number }>(items: T[], current: T | null | undefined): T[] {
  return current && !items.some(item => item.id === current.id) ? [current, ...items] : items
}
