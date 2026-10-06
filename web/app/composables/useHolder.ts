/** Says in the words of the interface which party has a request now. */
export function useHolder() {
  const { t } = useI18n()

  return (request: ExpenseRequest): { text: string, mine: boolean } | undefined => {
    const holder = holderOf(request.status)
    if (!holder) {
      return undefined
    }
    // The author and the moderator are people of the request, the other two parties are roles.
    const person = holder === 'author' ? request.author : holder === 'moderator' ? request.moderator : undefined
    return { text: t(`holder.${holder}`, { name: person?.name }), mine: false }
  }
}
