# 🏗 Архитектура Мини-CRM

Техническая документация для разработчиков и AI-агентов.

## Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.12+ |
| Веб-фреймворк | Flask 3.1 |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Авторизация | Flask-Login |
| База данных | SQLite (файл `instance/crm.sqlite`) |
| Production-сервер | Gunicorn |
| Контейнеризация | Docker + Docker Compose |
| Фронтенд | Bootstrap 5.3 + Bootstrap Icons, серверный рендеринг через Jinja2 |

## База данных

### Таблица `users`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `username` | TEXT UNIQUE | Логин |
| `password_hash` | TEXT | bcrypt (Werkzeug) |
| `display_name` | TEXT | Отображаемое имя |
| `role` | TEXT | `admin` или `user` |
| `color` | TEXT | HEX-цвет бейджа автора |
| `is_active_user` | BOOLEAN | Можно ли входить |
| `created_at` | DATETIME | |

### Таблица `orders`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `customer` | TEXT | Имя клиента |
| `description` | TEXT | Описание заказа |
| `status` | TEXT | `new`, `in_progress`, `done`, `cancelled` |
| `creator_id` | FK → users.id | Кто создал |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Таблица `attachments`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `order_id` | FK → orders.id | К какому заказу (опционально) |
| `announcement_id` | FK → announcements.id | К какому объявлению (опционально) |
| `comment_id` | FK → order_comments.id | К какому комментарию заказа (опционально) |
| `announcement_comment_id` | FK → announcement_comments.id | К какому комментарию объявления (опционально) |
| `filename` | TEXT | Оригинальное имя |
| `stored_name` | TEXT | UUID-имя на диске |
| `file_size` | INTEGER | Байт |
| `mime_type` | TEXT | MIME-тип для иконок |
| `uploaded_at` | DATETIME | |

Файлы хранятся в `instance/uploads/<stored_name>`.  
При удалении заказа, объявления или комментария файл удаляется с диска.

### Таблица `order_comments`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `order_id` | FK → orders.id | К какому заказу |
| `author_id` | FK → users.id | Автор комментария |
| `body` | TEXT | Текст комментария |
| `created_at` | DATETIME | |

### Таблица `announcement_comments`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `announcement_id` | FK → announcements.id | К какому объявлению |
| `author_id` | FK → users.id | Автор комментария |
| `body` | TEXT | Текст комментария |
| `created_at` | DATETIME | |

### Таблица `order_statuses`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `slug` | TEXT UNIQUE | Ключ статуса (новый=status) |
| `label` | TEXT | Отображаемое название |
| `color` | TEXT | Bootstrap-класс бейджа |
| `sort_order` | INTEGER | Порядок в списке |
| `is_active` | BOOLEAN | Показывать ли в интерфейсе |
| `is_system` | BOOLEAN | Системный (нельзя удалить) |

### Таблица `announcements`

| Поле | Тип | Назначение |
|------|-----|-----------|
| `id` | INTEGER PK | |
| `title` | TEXT | Заголовок |
| `body` | TEXT | Содержимое (разбивается по абзацам) |
| `creator_id` | FK → users.id | Кто создал |
| `created_at` | DATETIME | |

## Маршруты

**Auth**
```
GET  /login                     # Форма входа
POST /login                     # Проверка логина/пароля
POST /logout                    # Выход
```

**Заказы**
```
GET  /                          # Таблица заказов + вкладки (tab=active|done|cancelled)
GET  /order/new                 # Форма создания
POST /order/new                 # Создать заказ
GET  /order/<id>                # Детали заказа + вложения + комментарии
POST /order/<id>/status         # Изменить статус
POST /order/<id>/comments       # Добавить комментарий к заказу
POST /order/<id>/upload         # Прикрепить файлы
POST /order/<id>/delete         # Удалить заказ
```

**Вложения**
```
GET  /attachment/<id>/download  # Скачать файл
POST /attachment/<id>/delete    # Удалить вложение
```

**Доска объявлений**
```
GET  /board                     # Список объявлений + комментарии
GET  /board/new                 # Форма создания
POST /board/new                 # Создать объявление
GET  /board/<id>/edit           # Форма редактирования
POST /board/<id>/edit           # Сохранить изменения
POST /board/<id>/comments       # Добавить комментарий к объявлению
POST /board/<id>/delete         # Удалить объявление
```

**Админка** (только для `role='admin'`)
```
GET  /admin/users               # Список пользователей
POST /admin/users               # Создать пользователя
POST /admin/users/<id>/toggle   # Заблокировать/разблокировать
POST /admin/users/<id>/reset-password  # Сменить пароль
GET  /admin/statuses            # Управление статусами заказов
POST /admin/statuses            # Создать/редактировать статус
POST /admin/statuses/<id>/delete  # Удалить статус
```

**Профиль**
```
GET  /profile                   # Форма смены пароля
POST /profile                   # Сохранить новый пароль
```

## Авторизация

На уровне `@bp.before_request` проверяется `current_user.is_authenticated`.  
Исключение — `/login` (разрешён без авторизации).  
Админские маршруты дополнительно проверяют `current_user.role == 'admin'`.

## Миграция БД

Функция `_migrate_db()` в `__init__.py` проверяет существующие таблицы  
и добавляет недостающие колонки через `ALTER TABLE`.  
Это позволяет обновлять приложение без потери данных.

## Дизайн-система (CSS)

Все цвета — в `oklch`, переменные в `:root` внутри `base.html`:

- `--bg` — фон страницы
- `--surface` — фон карточек
- `--accent` — акцентный цвет (кнопки, ссылки)
- `--border` / `--border-strong` — границы
- `--fg` / `--muted` / `--faint` — текст

Карточки: `.card-crm` (border, без тени).  
Кнопки: `.btn-crm`, `.btn-crm-primary` (accent).  
Анимации: `slideDown` (алерты), `fadeIn` (появление блоков).

## Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY run.py .
COPY app/ ./app/
RUN mkdir -p /app/instance
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "run:app"]
```

- Volume: `./data:/app/instance` — для сохранения БД и файлов
- Порт: `8080`
- Переменная: `SECRET_KEY` (обязательно сменить в `docker-compose.yml`)

## Как добавить новую фичу

1. Модель — `models.py` (наследовать от `db.Model`)
2. Маршруты — `routes.py` (blueprint `bp`)
3. Шаблон — `templates/` (наследовать от `base.html`)
4. CSS — добавить в `<style>` блока `base.html`
5. Миграция — при необходимости добавить создание таблицы или колонок в `_migrate_db()` в `__init__.py`
6. Документация — обновить `ARCHITECTURE.md` (таблицы и маршруты)