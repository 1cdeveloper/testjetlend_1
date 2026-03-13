## Promo Orders API

Django-проект с endpoint`ом для создания заказов с применением промокодов.

### Стек

- Python 3.10+
- Django 4.2
- Django REST framework
- PostgreSQL

### Запуск через Docker 

Требуется установленный Docker и Docker Compose.

1. Собрать и запустить сервисы:

```bash
docker-compose up --build
```

2. Приложение будет доступно по адресу `http://127.0.0.1:8000/`.

В `docker-compose.yml` поднимаются два сервиса:

- `db` — PostgreSQL 16 c БД `promo_db` и пользователем `promo_user` / `promo_password`;
- `web` — Django-приложение, которое при старте выполняет `python manage.py migrate` и затем `runserver`.

### Локальный запуск (без Docker)

Альтернативный способ — запустить проект напрямую через Python/Django.

1. Установить зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Настроить подключение к PostgreSQL в `promo_project/settings.py` (секция `DATABASES`) либо через переменные окружения:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST` (по умолчанию `localhost`)
- `POSTGRES_PORT` (по умолчанию `5432`)

3. Применить миграции:

```bash
python manage.py migrate
```

4. Создать суперпользователя (для создания пользователей и промокодов через админку):

```bash
python manage.py createsuperuser
```

5. Запустить сервер:

```bash
python manage.py runserver
```

Приложение будет доступно по адресу `http://127.0.0.1:8000/`.

### Модели

- `PromoCode`:
  - `code` — текстовый код, уникальный;
  - `discount_percent` — процент скидки (целое число);
  - `expires_at` — дата/время истечения;
  - `max_usage_count` — максимальное количество использований промокода (глобально).
- `Order`:
  - `user` — внешний ключ на `AUTH_USER_MODEL`;
  - `amount` — исходная сумма заказа;
  - `final_amount` — сумма с учетом скидки;
  - `promo_code` — опциональная ссылка на `PromoCode`.

### Endpoint создания заказа

- **URL**: `POST /api/orders/`
- **Тело запроса** (JSON):

```json
{
  "user_id": 1,
  "amount": "1000.00",
  "promo_code": "SUMMER2025"
}
```

Поле `promo_code` может отсутствовать — в этом случае заказ создается без скидки.

### Правила применения промокода

При переданном `promo_code` выполняются проверки:

- промокод существует;
- промокод не просрочен (`expires_at` > сейчас);
- общее количество заказов с этим промокодом `< max_usage_count`;
- данный пользователь еще не использовал этот промокод.

При нарушении любого из условий сервис возвращает `400 Bad Request` с описанием ошибки и заказ не создается.

При успешном применении скидки:

- скидка считается как `amount * (discount_percent / 100)` с округлением до двух знаков;
- `final_amount = amount - discount`.

### Тесты

Запуск тестов в Docker:

```bash
docker-compose exec web python manage.py test
```

