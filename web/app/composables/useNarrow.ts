/**
 * Whether the screen is narrower than 640 px (the `sm` breakpoint of the styles): the width of a
 * phone, where the requests have one layout and the statuses stand in a strip. Follows the width as it changes.
 * Read in the browser only: the pages render after the person is known, which happens there.
 */
export function useNarrow() {
  const query = window.matchMedia('(max-width: 639.98px)')
  const narrow = ref(query.matches)
  const follow = (event: MediaQueryListEvent) => {
    narrow.value = event.matches
  }
  query.addEventListener('change', follow)
  onBeforeUnmount(() => query.removeEventListener('change', follow))
  return narrow
}
