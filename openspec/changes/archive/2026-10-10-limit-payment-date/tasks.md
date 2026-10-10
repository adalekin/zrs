# Tasks

## 1. Сервер

- [x] 1.1 Проверка дня оплаты в `ExpenseRequestService.act` с кодами `payment_after_today` и `payment_before_request`. Тесты в `tests/test_transitions.py`: день подачи и сегодняшний день приняты; завтрашний день, день накануне подачи и год двумя цифрами отклонены с названным полем, статус не меняется. Проверка: `uv run pytest tests/test_transitions.py`.
- [x] 1.2 Календарь тестов: день подачи запросов в тестовой базе, часы тестов с оплатой будущим числом. Проверка: `uv run pytest`.

## 2. Веб-интерфейс

- [x] 2.1 Метод `PaymentDay.dayOf` с тестом в `web/tests/payment-day.test.ts`: момент, который в поясе установки уже следующий день. Проверка: `bun run test`.
- [x] 2.2 Границы поля даты в форме отметки оплаты, тексты двух отказов в обеих локалях. Проверка: `bun run typecheck`; на локальном стенде дата с годом 0026 и дата в будущем дают отказ под полем, запрос остаётся одобренным.

## 3. Сквозная проверка

- [x] 3.1 `uv run pytest`, `uv run ruff check .`, `bun run typecheck`, `bun run test` и `openspec validate --all --strict` проходят.
