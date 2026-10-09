// The palette of the reference lists. Class names are written out in full:
// Tailwind collects them by reading the source and misses a name put together at run time.
//
// The shades come from the same Tailwind ramps as the stages of a request (RequestStage), so that
// a tag of a reference value and a status badge in one row belong to one family of colours.

/** The fill of the tag that shows a coloured value in the list of requests and in a request. */
export const REFERENCE_FILLS: Record<ReferenceColor, string> = {
  red: 'bg-red-100 text-red-900',
  orange: 'bg-orange-100 text-orange-900',
  // The amber ramp: on the yellow one the name is too faint to read.
  yellow: 'bg-amber-100 text-amber-900',
  green: 'bg-green-100 text-green-900',
  teal: 'bg-teal-100 text-teal-900',
  blue: 'bg-blue-100 text-blue-900',
  violet: 'bg-violet-100 text-violet-900',
  pink: 'bg-pink-100 text-pink-900',
}

/** The circle a colour is chosen by: the stop the statuses write their names in, deep and calm. */
export const REFERENCE_SWATCHES: Record<ReferenceColor, string> = {
  red: 'bg-red-700',
  orange: 'bg-orange-700',
  // The yellow ramp one stop lighter: amber-700 is too close to the orange, yellow-700 is brown.
  yellow: 'bg-yellow-600',
  green: 'bg-green-700',
  teal: 'bg-teal-700',
  blue: 'bg-blue-700',
  violet: 'bg-violet-700',
  pink: 'bg-pink-700',
}
