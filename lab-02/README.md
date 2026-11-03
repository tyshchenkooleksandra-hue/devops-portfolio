# Лабораторна робота 2 — Командна робота з Git

**Командний репозиторій:** <https://github.com/tyshchenkooleksandra-hue/team-devops-handbook>

Довідник забрано у цей репозиторій через `git subtree` — тека [`handbook/`](../handbook/).

## Склад команди

Команда з одного учасника — за погодженням із викладачем. Щоб правила, які вимагають другої
людини, працювали по-справжньому, а не декоративно, використано два мої акаунти:

| Акаунт | Роль у роботі |
|---|---|
| [@tyshchenkooleksandra-hue](https://github.com/tyshchenkooleksandra-hue) (A) | власниця репозиторію; розділи «Конвенції гілок і комітів», «Шаблон README», «Розбір конфлікту» |
| [@AlexandraTyshchenko](https://github.com/AlexandraTyshchenko) (B) | collaborator; розділи «Спільні налаштування», «Чек-лист рецензування», бонус |

GitHub не дозволяє автору схвалити власний PR, тому без другого акаунта ruleset із завдання
(1 схвалення + рецензія власника коду + заборона обходу) заблокував би будь-яке злиття.
Кожен акаунт працював у власній локальній копії з локальними `user.name`/`user.email`
(глобальні налаштування Git не змінювалися).

---

## Завдання 1. Команда й правила репозиторію

Ruleset `protect-main` для `main`:

| Правило | Значення |
|---|---|
| Обов'язковий pull request | ✅ |
| Кількість схвалень | 1 (двоє в команді) |
| Скидання застарілих схвалень при нових комітах | ✅ |
| Обов'язкова рецензія від власників коду | ✅ |
| Заборона force-push і видалення гілки | ✅ |
| **Заборона обходу правил адміністратором** | ✅ bypass list порожній |
| Додатково | схвалення останнього пушу, закриті обговорення, лінійна історія (лише squash), обов'язкова перевірка `pr-title` |

```text
$ gh api repos/tyshchenkooleksandra-hue/team-devops-handbook/rulesets/26492456 \
    --jq '"enforcement: "+.enforcement+", bypass_actors: "+(.bypass_actors|tostring)+", current_user_can_bypass: "+.current_user_can_bypass'
enforcement: active, bypass_actors: [], current_user_can_bypass: never
```

Скріншоти — у [`assets/`](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/tree/main/assets),
склад команди — у [README довідника](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook#склад-команди).

**CODEOWNERS.** Кожен файл у `docs/` має відповідальну (перша в рядку). Другий акаунт указано
в кожному рядку, бо якщо єдиний власник файла — автор PR, вимога «рецензія власника коду» стає
нездійсненною. Рецензентів призначає система: наприклад, у PR #2 (автор B) GitHub сам запросив
рецензію A.

**Чому заборона обходу тепер не шкодить.** У ЛР1 соло вона блокувала мене саму: схвалити було
нікому. Тут завжди є другий акаунт, тож правило стає справжнім — навіть власниця репозиторію
не може злити PR без схвалення, зеленої перевірки й закритих обговорень.

## Завдання 2. Власні розділи довідника

| Розділ | Відповідальна | PR | Як перевірено |
|---|---|---|---|
| [Конвенції гілок і комітів](../handbook/docs/branching.md) | A | [#5](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/5) | хук на 5 типах повідомлень; приклади правильних/неправильних |
| [Шаблон README](../handbook/docs/readme-template.md) | A | [#6](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/6) | README для `curl` за шаблоном; порівняння з розділами `man curl` знайшло 4 відсутні розділи (вхід/вихід, змінні оточення, файли, версія) |
| [Спільні налаштування](../handbook/docs/editor-config.md) | B | [#2](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/2) | `.gitignore`: архів, `.env`, `__pycache__/`, бінарник → `git status` чистий, `git check-ignore -v` показує правило; `.editorconfig`: 7 типів файлів із різними налаштуваннями |
| [Чек-лист рецензування](../handbook/docs/code-review.md) | B | [#4](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/4) | кожен пункт — «так/ні»; суб'єктивні пункти замінено на перевірювані |

## Завдання 3. Процес pull request

Усі зміни — через PR із гілок `feature/<ім'я>-<тема>`. У кожному PR — змістовне зауваження,
правки — **окремим комітом**, обговорення закриває **автор**.

| PR | Автор → рецензент | Зауваження по суті | Як закрито |
|---|---|---|---|
| [#1](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/1) | A → B | README не каже, як забрати довідник у свій репозиторій, а способи дають різний результат | додано розділ про `git subtree` з порівнянням |
| [#2](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/2) | B → A | `.gitignore` не проходить перевірку з умови: `*.tar.gz` і бінарник не ігноруються (вивід `git status`) | власна секція; правило «не ігнорувати тестову теку» відкинуто як підгонка |
| [#3](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/3) | A → B | «правильне» вирішення конфлікту саме загубило ключ `[*.{yml,yaml,json}]` | секцію повернуто, пояснено в обох документах |
| [#4](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/4) | B → A | 2 пункти чек-листа («обробка помилок нормальна», «код добре читається») не мають відповіді «так/ні» | замінено на перевірювані |
| [#5](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/5) | A → B | хук блокує `git merge` / `revert` / `fixup!` — перевірено на повідомленнях Git | автоматичні повідомлення пропускаються |
| [#6](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/6) | A → B | шаблон вимагає коди виходу, а приклад показує лише «найчастіші» | правило: власна утиліта документує всі коди |
| [#7](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/7) | B → A | хук і CI перевіряють різне (велика літера); формат не описаний у довіднику | одне правило в хуку й CI, розділи в `branching.md` |
| [#8](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/pull/8) | A → B | скріншот публічної сторінки не показує bypass list | **аргументовано відхилено**: вивід API перевірюваний і не застаріває |

## Завдання 4. Конфлікт злиття

Розбір — [`docs/conflict.md`](../handbook/docs/conflict.md). Обидві версії `.editorconfig` написано
незалежно; PR #2 злився першим, PR #3 отримав конфлікт `add/add`.

- **Помилкове вирішення** («Accept Both Changes»): файл валідний, але рядок `indent_size = 2` із
  секції `[*]` після склеювання опинився під заголовком `[*.sh]`. Фактичні налаштування
  (бібліотека `editorconfig`) — усі файли без власної секції отримали відступ 4 замість 2.
- **Правильне**: узгоджена версія, задокументована в `docs/editor-config.md`, + збережена корисна
  секція з другої половини.

## Завдання 5. Історія і хук

Робочі коміти (`wip editorconfig`, `fix`, `try again docs` у PR #2) зведено squash-злиттям.

```text
$ git log --oneline main
bfebca2 docs: скріншоти ruleset і перевірка заборони обходу (#8)
97df70e ci: перевірка заголовка PR і генерація списку змін (#7)
7290ff2 docs: шаблон README для консольних утиліт, перевірка на curl (#6)
87d847a feat(hook): конвенції гілок і комітів, хук commit-msg (#5)
b8138a2 docs: чек-лист рецензування для консольних утиліт (#4)
eef90e7 feat: власна версія .editorconfig і розбір конфлікту (#3)
e8d7d26 docs: спільні .editorconfig і .gitignore з поясненням (#2)
165b3a4 docs: склад команди, CODEOWNERS і шаблон PR (#1)
5b95f71 Initial commit
```

**Хук** — [`.githooks/commit-msg`](../handbook/.githooks/commit-msg): перевіряє формат Conventional
Commits. Встановлення: `git config core.hooksPath .githooks` — у кожному новому клоні, бо
`.git/hooks` і `.git/config` не версіонуються.

```text
update                          -> exit 1   (відхилено)
docs: додати розділ             -> exit 0
docs: Додати розділ             -> exit 1   (опис з великої літери)
Merge branch 'main' into x      -> exit 0   (повідомлення Git пропускаються)
```

## Завдання 6. Локальне ім'я і remote

```text
PS …\devops-labs> Rename-Item team-devops-handbook handbook-oleksandra
PS …\devops-labs> cd handbook-oleksandra
PS …\handbook-oleksandra> git remote -v
origin  git@github.com:tyshchenkooleksandra-hue/team-devops-handbook.git (fetch)
origin  git@github.com:tyshchenkooleksandra-hue/team-devops-handbook.git (push)
PS …\handbook-oleksandra> git push -u origin feature/oleksandra-ruleset-assets
To github.com:tyshchenkooleksandra-hue/team-devops-handbook.git
 * [new branch]      feature/oleksandra-ruleset-assets -> feature/oleksandra-ruleset-assets
```

**Яку хибну уяву це знімає:** ім'я локальної теки ніяк не пов'язане з репозиторієм на GitHub.
Адреса віддаленого репозиторію зберігається в `.git/config` (`remote.origin.url`) усередині
теки — перейменування чи переміщення теки її не змінює, і push працює як раніше. Так само назва
репозиторію на GitHub не зобов'язана збігатися з назвою теки клону.

Під час вправи трапилася реальна проблема: `Rename-Item` падав із «being used by another
process». Тримав теку не редактор, а завислий `ssh.exe` від старого `git push`, що чекав
парольну фразу в забутій вкладці терміналу, — після завершення процесу перейменування пройшло.

---

## Бонус. Конвенції комітів

| Вимога | Як виконано |
|---|---|
| Формат описано з прикладами | [`docs/branching.md`](../handbook/docs/branching.md): таблиця правильних і неправильних повідомлень із поясненням |
| Перевірка автоматична | workflow [`commit-conventions`](https://github.com/tyshchenkooleksandra-hue/team-devops-handbook/actions/workflows/commit-conventions.yml) перевіряє заголовок PR; перевірка **обов'язкова** в ruleset — червона блокує злиття |
| Список змін з історії | `git-cliff` за [`cliff.toml`](../handbook/cliff.toml) після кожного злиття в `main` |

Перевіряється **заголовок PR**, а не кожен коміт: після squash саме він стає комітом у `main`.

```text
Заголовок «Update stuff»  → ✗ pr-title: No release type found in pull request title "Update stuff"
Заголовок «ci: перевірка заголовка PR і генерація списку змін» → ✓ pr-title
```

Згенерований список змін (Actions → `commit-conventions` → Summary):

```markdown
### Нове
- власна версія .editorconfig і розбір конфлікту (#3)
- **hook:** конвенції гілок і комітів, хук commit-msg (#5)
### Документація
- склад команди, CODEOWNERS і шаблон PR (#1)
- спільні .editorconfig і .gitignore з поясненням (#2)
- чек-лист рецензування для консольних утиліт (#4)
- шаблон README для консольних утиліт, перевірка на curl (#6)
### Конвеєр і збірка
- перевірка заголовка PR і генерація списку змін (#7)
```
