import type { ShallowRef } from 'vue'

/**
 * Loads data from the server once the component is in the browser, and again on
 * `reload`. Nothing is cached between visits: a page always shows what the server
 * holds now. An answer that arrives after a newer call was made is dropped.
 */
export function useLoad<T>(load: () => Promise<T>) {
  const data: ShallowRef<T | undefined> = shallowRef()
  const error = shallowRef<unknown>()
  let latest = 0

  async function reload() {
    const call = ++latest
    try {
      const result = await load()
      if (call === latest) {
        data.value = result
        error.value = undefined
      }
    }
    catch (failure) {
      if (call === latest) {
        error.value = failure
      }
    }
  }

  onMounted(reload)
  return { data, error, reload }
}
