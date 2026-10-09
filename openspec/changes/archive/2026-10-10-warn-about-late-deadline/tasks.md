# Tasks

## 1. Сервер: настройки

- [x] 1.1 Настройки `TIMEZONE` и `PAYMENT_DAY_ENDS_AT` в `Settings`, поле `payment_day` в ответе `GET /v1/me`. Тесты в `tests/test_settings.py` и `tests/test_people.py`: время с поясом; настройка не задана; неверное время; неизвестный пояс; ответ о человеке отдаёт время и пояс. Проверка: `uv run pytest tests/test_settings.py tests/test_people.py`.
- [x] 1.2 Примеры настроек в корневом `compose.yaml`, `deploy/compose.yaml`, значениях чарта и README. Проверка: `docker compose config`, `helm lint deploy/helm/zrs -f deploy/helm/zrs/ci/example-values.yaml`.

## 2. Веб-интерфейс

- [x] 2.1 Класс `PaymentDay` с тестом в `web/tests/payment-day.test.ts`: дедлайн сегодня до и после времени; дедлайн вчера и завтра; момент, который в поясе установки уже следующий день. Проверка: `bun run test`.
- [x] 2.2 Предупреждение под полем дедлайна в форме запроса, подписи в обеих локалях. Проверка: `bun run typecheck`; на локальном стенде с окончанием платёжного дня раньше текущего времени форма предупреждает о сегодняшнем дедлайне, и запрос подаётся.

## 3. Сквозная проверка

- [x] 3.1 На корневом `compose.yaml`: предупреждение о вчерашнем дедлайне есть при любом времени окончания платёжного дня, о завтрашнем нет.
- [x] 3.2 `uv run pytest`, `bun run typecheck`, `bun run test`, `helm lint` и `openspec validate --all --strict` проходят.
