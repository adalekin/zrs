/** Says in the words of the interface which party has a request now, or who rejected it. */
export function useHolder() {
  const { t } = useI18n()

  return (request: ExpenseRequest): { text: string, mine: boolean } | undefined => {
    // The moderator who rejected is named, like the moderator a request waits for.
    if (request.status === 'rejected' && request.rejected_as) {
      return { text: t(`holder.rejected.${request.rejected_as}`, { name: request.rejected_by?.name }), mine: false }
    }
    const holder = holderOf(request.status)
    if (!holder) {
      return undefined
    }
    // The author and the moderator are people of the request, the finance director is a role,
    // and the payer is a person once somebody is assigned.
    if (holder === 'payer') {
      return { text: request.payer ? t('holder.payerNamed', { name: request.payer.name }) : t('holder.payer'), mine: false }
    }
    const person = holder === 'author' ? request.author : holder === 'moderator' ? request.moderator : undefined
    return { text: t(`holder.${holder}`, { name: person?.name }), mine: false }
  }
}
