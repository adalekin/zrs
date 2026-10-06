import { toast } from 'vue-sonner'

/**
 * Shows why a call to the server failed: the text of the interface for the error code,
 * else the message of the server, else a general one.
 */
export function useFailureToast() {
  const { t, te } = useI18n()

  return (error: unknown) => {
    const key = `error.code.${errorCode(error)}`
    if (te(key)) {
      toast.error(t(key))
      return
    }
    toast.error(errorDetail(error) ?? t('common.failed'))
  }
}
