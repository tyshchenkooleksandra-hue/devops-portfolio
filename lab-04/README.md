# Лабораторна робота 4 — Безперервна інтеграція

Чужий застосунок для списків побажань (бекенд на FastAPI, фронтенд на Vue), який я запустила локально й обгорнула конвеєром, що не дає злити зламаний код.

| Репозиторій | Що це | Докази |
|---|---|---|
| [wishlist-api](https://github.com/tyshchenkooleksandra-hue/wishlist-api) | форк бекенду: FastAPI, Postgres, Redis | [`docs/checks.md`](https://github.com/tyshchenkooleksandra-hue/wishlist-api/blob/main/docs/checks.md) |
| [wishlist-ui](https://github.com/tyshchenkooleksandra-hue/wishlist-ui) | форк фронтенду: Vue 3, Vite, TypeScript | [`docs/checks.md`](https://github.com/tyshchenkooleksandra-hue/wishlist-ui/blob/main/docs/checks.md) |

Оригінали: [nromanen/withlist-api](https://github.com/nromanen/withlist-api), [nromanen/wishlist-ui](https://github.com/nromanen/wishlist-ui).

## Мій внесок

Роботу виконано соло, за погодженням із викладачем. Я підняла обидва застосунки локально й написала для кожного конвеєр GitHub Actions; тепер злити код у `main` можна лише після зелених перевірок.

Проєкт не запускався «з коробки», тож спершу довелося виправити кілька проблем ([wishlist-api #1](https://github.com/tyshchenkooleksandra-hue/wishlist-api/pull/1), [wishlist-ui #1](https://github.com/tyshchenkooleksandra-hue/wishlist-ui/pull/1)):

- `sslmode=require` у коді не давав підключитися до локального Postgres без SSL;
- параметр `ssl_cert_reqs` ламав Redis на звичайному `redis://`, а голий `except` у `/health` це приховував;
- таблиці створювалися під час імпорту модуля, тому будь-який тест вимагав живу базу;
- у `.env.example` не було `ALGORITHM`, без якого вхід падав;
- скрипт `npm run lint` викликав ESLint, якого не було ні в залежностях, ні в конфігурації.

У [wishlist-api #2](https://github.com/tyshchenkooleksandra-hue/wishlist-api/pull/2) і [wishlist-ui #2](https://github.com/tyshchenkooleksandra-hue/wishlist-ui/pull/2) я показала блокування злиття на свідомо зламаному коді. Ці PR заодно несуть справжні правки: виправлення кешу, через який новий список не показувався до 5 хвилин, і заголовок сторінки.

## Запуск локально

Потрібні: Git, Docker із Compose v2, Python 3.11 ([uv](https://docs.astral.sh/uv/) поставить його сам), Node.js 24. Команди для PowerShell на Windows. На Linux/macOS замість `Copy-Item` — `cp`, замість `.venv\Scripts\python` — `.venv/bin/python`.

Python саме **3.11**: закріплений `psycopg2-binary==2.9.7` не має готових збірок для новіших версій.

### 1. Бекенд

```bash
git clone https://github.com/tyshchenkooleksandra-hue/wishlist-api.git
cd wishlist-api
docker compose up -d postgres redis
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\python -m pytest -q
.venv\Scripts\python run.py
```

Тести: `4 passed`. Сервер лишається працювати, документація — на <http://localhost:8000/docs>.

Якщо `docker compose up` обривається з `tls: bad record MAC`, це збій мережі під час завантаження образу: повторіть команду, за потреби вимкнувши VPN.

### 2. Фронтенд (у новому терміналі)

```bash
git clone https://github.com/tyshchenkooleksandra-hue/wishlist-ui.git
cd wishlist-ui
npm ci
Copy-Item .env.example .env
npm run dev
```

### 3. Перевірка

1. Відкрити <http://localhost:5173>, натиснути **Register**, створити користувача.
2. Увійти, у **My Wishlists** створити список.
3. Список з'явиться на сторінці. Перевірити, що він справді в базі:

```bash
cd wishlist-api
docker compose exec postgres psql -U username -d wishlist_db -c "select id, title from wishlists;"
```

Зупинити: `Ctrl+C` у терміналах застосунків, потім `docker compose down` у теці `wishlist-api`.

## Конвеєри

| Вимога | Як зроблено |
|---|---|
| Закріплені версії | `ubuntu-24.04`, `actions/checkout@v7.0.1`, образи `postgres:15-alpine`, `redis:7-alpine`, версії інструментів у `requirements-dev.txt` |
| Порядок | лінтер → тести (API); лінтер → типи → збірка (UI), через `needs` |
| Кеш | `cache: pip` і `cache: npm` у `setup-python` і `setup-node` |
| Зрозумілі імена | `Lint (ruff)`, `Tests (Python 3.11)`, `Types (vue-tsc)` |
| Тригери | лише `pull_request` і `push` у `main` |
| Готовність баз | `--health-cmd` у сервісах: кроки не стартують, поки база не приймає з'єднання |
| Тести | один на `/health` (звернення до бази в ньому заборонене), інші пишуть і читають Postgres та Redis |

Ruleset в обох форках: обов'язковий PR, перевірки зі списку, гілка актуальна щодо `main`, скидання застарілих схвалень, заборона force-push і видалення, порожній список обходу. Обов'язкових схвалень немає: я працюю сама, а автор не може схвалити власний PR.

## Бонуси

| Бонус | Результат |
|---|---|
| Матриця версій | Python 3.10 і 3.11, `fail-fast: false`; кожен варіант — окрема обов'язкова перевірка |
| Нічний аудит | `audit.yml`, щоночі о 03:00 UTC: `pip-audit` знайшов 44 вразливості в 12 пакетах, `npm audit` — 25. Прогони червоні, але PR не блокують: у цього воркфлоу немає тригера `pull_request` |
| Звіт про покриття | артефакти `coverage-python-3.10` і `coverage-python-3.11`, крок виконується з `if: always()`, тобто й тоді, коли тести впали |

## Що я дізналася

- Обов'язкові перевірки можна вибрати лише після першого прогону: список будується з імен, які GitHub уже бачив.
- Кеш прискорює не все. UI: 106 → 50 с, бо найдовше було `npm ci`. API: 61 → 53 с, бо час іде на запуск контейнерів.
- Якщо лінтер упав, job матриці пропускається ще до розгортання й показується з іменем `Tests (Python ${{ matrix.python-version }})`. Обов'язкові `Tests (Python 3.10)` і `3.11` лишаються в стані очікування, тож злиття все одно заблоковане.
