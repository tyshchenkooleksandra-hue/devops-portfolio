# Спільні налаштування: `.editorconfig` і `.gitignore`

Відповідальна: @AlexandraTyshchenko

## `.editorconfig`

[EditorConfig](https://editorconfig.org) задає однакові правила форматування для всіх редакторів
команди. VS Code читає його лише з розширенням `editorconfig.editorconfig`, JetBrains — вбудовано.

### Секція `[*]` — для всіх файлів

| Ключ | Значення | Чому саме так |
|---|---|---|
| `root` | `true` | Не шукати `.editorconfig` у батьківських теках: правила проєкту не залежать від того, де лежить клон |
| `charset` | `utf-8` | Українські коментарі й `README` без «кракозябр» у будь-якій ОС |
| `end_of_line` | `lf` | Скрипти виконуються в Linux-контейнерах і CI; `CRLF` ламає shebang (`/bin/bash^M`) |
| `insert_final_newline` | `true` | POSIX-визначення рядка; без нього `cat` склеює файли, а diff показує `\ No newline at end of file` |
| `trim_trailing_whitespace` | `true` | Пробіли в кінці рядка — шум у diff і причина фіктивних конфліктів |
| `indent_style`, `indent_size` | `space`, `2` | Типова глибина для YAML, JSON, Compose і GitHub Actions — основних конфігів курсу |

### Перевизначення за типом файла

| Секція | Що змінено | Чому |
|---|---|---|
| `[*.{yml,yaml,json}]` | `indent_size = 2` явно | Для YAML відступ — частина синтаксису: зміна базового `[*]` не повинна мовчки змінювати структуру workflow і Compose-файлів |
| `[*.py]` | `indent_size = 4`, `max_line_length = 100` | PEP 8 вимагає 4 пробіли; 100 замість 79 — компроміс, який використовують black/ruff-конфіги більшості проєктів |
| `[*.sh]` | `indent_size = 2` | Google Shell Style Guide — найпоширеніший стиль bash |
| `[*.go]`, `[Makefile]` | `indent_style = tab` | `gofmt` форматує табами; `make` **вимагає** таб перед командою, з пробілами — помилка `missing separator` |
| `[*.md]` | `trim_trailing_whitespace = false` | Два пробіли в кінці рядка Markdown — примусовий перенос, їх обрізання змінює вигляд документа |
| `[*.{bat,cmd,ps1}]` | `end_of_line = crlf` | `cmd.exe` некоректно обробляє мітки й `goto` у файлах з `LF` |

## `.gitignore`

Згенеровано сервісом [gitignore.io](https://www.toptal.com/developers/gitignore), а не написано вручну:

```bash
curl -sL "https://www.toptal.com/developers/gitignore/api/linux,macos,windows,python,node,go,visualstudiocode,jetbrains+all,dotenv" -o .gitignore
```

| Шаблон | Навіщо |
|---|---|
| `linux`, `macos`, `windows` | Службові файли ОС (`.DS_Store`, `Thumbs.db`) — у команді різні системи |
| `python`, `node`, `go` | Мови консольних утиліт курсу: `__pycache__/`, `node_modules/`, зібрані `*.exe` |
| `visualstudiocode`, `jetbrains+all` | Локальні налаштування редакторів |
| `dotenv` | `.env` із секретами ніколи не потрапляє в репозиторій |

### Власна секція

Генератор не покриває дві речі, потрібні консольним утилітам курсу, — їх додано вручну в кінці файла:

| Правило | Чому |
|---|---|
| `*.tar`, `*.tar.gz`, `*.tgz`, `*.zip` | Архіви збірок і резервних копій. Їх немає в жодному з обраних шаблонів |
| `/bin/`, `/build/` | Зібрані бінарники на Linux/macOS **без розширення** — шаблон `go` ловить лише `*.exe`. Тому ігноруємо теки збірки, а утиліту збираємо в `bin/` (`dist/` уже є в шаблоні `python`) |

### Перевірка

Тестова тека з архівом, `.env`, `__pycache__/` і бінарником, зібраним у `bin/`:

```text
$ git status --short -uall
                                  # порожньо — нічого зайвого
$ git check-ignore -v test-ignore/backup.tar.gz test-ignore/.env test-ignore/__pycache__/m.cpython-314.pyc bin/tool
.gitignore:522:*.tar.gz      test-ignore/backup.tar.gz
.gitignore:5:.env            test-ignore/.env
.gitignore:306:__pycache__/  test-ignore/__pycache__/m.cpython-314.pyc
.gitignore:527:/bin/         bin/tool
```

`git check-ignore -v` показує, **яке саме правило** спрацювало, — так видно, що файл ігнорується не випадково.

> Обмеження: бінарник, зібраний просто в корінь (`gcc tool.c -o tool`), не ігнорується — ім'я без
> розширення неможливо відрізнити від звичайного файла. Тому збірка в `bin/` — частина конвенції.
