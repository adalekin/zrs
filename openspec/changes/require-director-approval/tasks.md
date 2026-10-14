# Tasks

## 1. Сервер

- [x] 1.1 Убрать `Action.ESCALATE` из `entity/enums.py`; в `service/transitions.py` утверждение модератора ведёт из `new` в `escalated`, отдельной строки передачи нет. Проверка: `uv run pytest tests/test_transitions.py`.
- [x] 1.2 Решения в Telegram без передачи: `DECISIONS` в `service/telegram_decisions.py`; ответ бота о решении по итоговому статусу (`done_escalated`, `done_approved`, `done_returned`, `done_rejected` в `service/notices.py`, обе локали); «Автор получит сообщение» не говорится о запросе, ушедшем финансовому директору; нажатие кнопки ушедшего действия отвечает «Кнопка больше не действует». Проверка: `uv run pytest tests/test_telegram_decisions.py`.

## 2. Веб-интерфейс

- [x] 2.1 Действие `escalate` убрано из типа `Action` и подписей обеих локалей. Проверка: `bun run typecheck`, `bun run test`.

## 3. Тесты и документация

- [x] 3.1 Тесты сервера переписаны на маршрут «модератор утверждает, финансовый директор одобряет»: `test_transitions.py` (матрица действий и `drive`), `test_journal.py`, `test_queue.py`, `test_request_payer.py`, `test_request_rejection.py`, `test_request_totals.py`, `test_visibility_and_lists.py`, `test_notifications.py`, `test_telegram_decisions.py` (у модератора три кнопки). Проверка: `uv run pytest` зелёный целиком.
- [x] 3.2 Диаграмма пути запроса и таблица ролей в `README.md`: утверждение модератора ведёт в «Отмодерировано».

## 4. Сквозная проверка

- [ ] 4.1 На корневом `compose.yaml`: автор подаёт запрос, модератор утверждает, запрос ждёт финансового директора, финансовый директор одобряет, исполнитель отмечает оплату.
- [x] 4.2 `uv run pytest`, `bun run typecheck`, `bun run test` и `openspec validate --all --strict` проходят.
