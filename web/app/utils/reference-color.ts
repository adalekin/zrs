// The palette of the reference lists. Class names are written out in full:
// Tailwind collects them by reading the source and misses a name put together at run time.

/** The fill of the tag that shows a coloured value in the list of requests and in a request. */
export const REFERENCE_FILLS: Record<ReferenceColor, string> = {
  red: 'bg-red-100 text-red-900',
  orange: 'bg-orange-100 text-orange-900',
  // The amber shades: the yellow ones leave the name too faint to read.
  yellow: 'bg-amber-100 text-amber-900',
  green: 'bg-green-100 text-green-900',
  teal: 'bg-teal-100 text-teal-900',
  blue: 'bg-blue-100 text-blue-900',
  violet: 'bg-violet-100 text-violet-900',
  pink: 'bg-pink-100 text-pink-900',
}

/** The circle a colour is chosen by. */
export const REFERENCE_SWATCHES: Record<ReferenceColor, string> = {
  red: 'bg-red-400',
  orange: 'bg-orange-400',
  yellow: 'bg-amber-400',
  green: 'bg-green-400',
  teal: 'bg-teal-400',
  blue: 'bg-blue-400',
  violet: 'bg-violet-400',
  pink: 'bg-pink-400',
}
