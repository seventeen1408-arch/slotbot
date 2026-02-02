# 🔐 PRO S2S Postback System - Полное руководство

**Версия:** 1.0.0  
**Статус:** Production-ready  
**Безопасность:** Enterprise-level  

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Архитектура](#архитектура)
3. [Безопасность](#безопасность)
4. [Установка](#установка)
5. [Конфигурация](#конфигурация)
6. [API Endpoints](#api-endpoints)
7. [Примеры](#примеры)
8. [Мониторинг](#мониторинг)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Обзор

**PRO S2S Postback System** - это enterprise-level система обработки событий от партнеров (казино, букмекеры и т.д.) с полной безопасностью.

### Возможности

- ✅ **HMAC-SHA256** верификация подписей
- ✅ **Replay Attack Prevention** (идентификация дублей)
- ✅ **IP Whitelist** (только разрешенные IP)
- ✅ **Rate Limiting** (защита от DDoS)
- ✅ **Timestamp Validation** (проверка времени)
- ✅ **Pydantic Валидация** (проверка данных)
- ✅ **Audit Logging** (полная история)
- ✅ **Encryption at Rest** (шифрование в БД)

### Поддерживаемые события

| Событие | Описание | Действие |
|---------|---------|---------|
| `register` | Регистрация в казино | Отправить приветствие |
| `first_deposit` | Первый депозит | Выдать VIP на 48 часов |
| `deposit` | Повторный депозит | Обновить статистику |
| `withdrawal` | Вывод средств | Логировать событие |
| `win` | Выигрыш | Логировать событие |

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│ Казино (1Win, Stake, Roobet и т.д.)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ POST /api/postback/{partner_name}
                     │ (с подписью HMAC-SHA256)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Endpoint (postback_pro.py)                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 1. Получить данные                                      │ │
│ │ 2. Проверить IP адрес (IP Whitelist)                    │ │
│ │ 3. Проверить Rate Limit                                 │ │
│ │ 4. Валидировать данные (Pydantic)                       │ │
│ │ 5. Проверить timestamp                                  │ │
│ │ 6. Проверить подпись (HMAC-SHA256)                      │ │
│ │ 7. Проверить дубль (Idempotency)                        │ │
│ │ 8. Обработать событие                                   │ │
│ │ 9. Логировать аудит                                     │ │
│ └─────────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ PostbackProService (postback_pro_service.py)                │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Обработка событий:                                      │ │
│ │ - Registration → Отправить приветствие                  │ │
│ │ - First Deposit → Выдать VIP                            │ │
│ │ - Deposit → Обновить статистику                         │ │
│ │ - Withdrawal → Логировать                               │ │
│ │ - Win → Логировать                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    ┌────────┐  ┌────────┐  ┌──────────┐
    │ БД     │  │Telegram│  │ Логи    │
    │        │  │ Бот    │  │ Аудита  │
    └────────┘  └────────┘  └──────────┘
```

---

## 🔐 Безопасность

### 1. HMAC-SHA256 Верификация

**Как это работает:**

```python
# На стороне казино (1Win)
secret_key = "my-secret-key-12345"
data = {"click_id": "550e8400...", "event": "register", "timestamp": 1234567890}
sorted_data = sorted(data.items())
data_string = "&".join([f"{k}={v}" for k, v in sorted_data])
signature = hmac.new(secret_key.encode(), data_string.encode(), hashlib.sha256).hexdigest()

# Отправить: POST /api/postback/1win?click_id=...&event=...&signature=...

# На стороне бота
# Проверить что подпись совпадает
```

**Защита от:**
- ✅ Подделки данных
- ✅ Timing attacks (благодаря `compare_digest`)

### 2. Replay Attack Prevention (Idempotency)

**Как это работает:**

```
Казино отправляет: event_id=550e8400-e29b-41d4-a716-446655440000

Бот:
1. Проверить в БД: есть ли уже этот event_id?
2. Если есть → вернуть "already processed"
3. Если нет → обработать и сохранить event_id
```

**Защита от:**
- ✅ Повторной обработки одного события
- ✅ Выдачи VIP дважды
- ✅ Двойного начисления денег

### 3. IP Whitelist

**Конфигурация:**

```python
IP_WHITELIST = {
    "1win": ["1.2.3.4", "5.6.7.8"],
    "stake": ["10.11.12.13"],
    "roobet": ["14.15.16.17"],
}
```

**Проверка:**

```
Получен запрос с IP: 192.168.1.1
Партнер: 1win
Разрешенные IP: ["1.2.3.4", "5.6.7.8"]
Результат: ❌ Отклонить
```

**Защита от:**
- ✅ Запросов с неправильных IP
- ✅ Спуфинга IP адреса

### 4. Rate Limiting

**Конфигурация:**

```python
RATE_LIMIT_WINDOW = 60  # 1 минута
RATE_LIMIT_MAX_REQUESTS = 100  # 100 запросов в минуту
```

**Проверка:**

```
Партнер: 1win
IP: 1.2.3.4
Запросов в этой минуте: 95
Лимит: 100
Результат: ✅ Разрешить

Запросов в этой минуте: 101
Результат: ❌ Отклонить (Rate limit exceeded)
```

**Защита от:**
- ✅ DDoS атак
- ✅ Спама постбеков
- ✅ Перегрузки сервера

### 5. Timestamp Validation

**Конфигурация:**

```python
MAX_EVENT_AGE_SECONDS = 300  # 5 минут
```

**Проверка:**

```
Текущее время: 1000
Timestamp события: 850
Возраст: 150 секунд
Максимум: 300 секунд
Результат: ✅ Разрешить

Timestamp события: 600
Возраст: 400 секунд
Результат: ❌ Отклонить (Event too old)
```

**Защита от:**
- ✅ Старых перехваченных событий
- ✅ Часовых сдвигов на сервере

### 6. Audit Logging

**Все операции логируются:**

```sql
INSERT INTO postback_audit_logs (
    timestamp,
    partner_name,
    event_id,
    ip_address,
    action,
    status,
    details,
    user_id
)
```

**Примеры действий:**
- `received` - событие получено
- `verified` - подпись проверена
- `processed` - событие обработано
- `failed` - ошибка обработки
- `duplicate` - дублирующееся событие

**Использование:**
- Отладка проблем
- Соответствие требованиям
- Судебные доказательства

---

## 📦 Установка

### 1. Применить миграцию БД

```bash
cd /home/ubuntu/gambling_bot_production

# Применить SQL миграцию
mysql -u root -p your_database < migrations/postback_pro_migration.sql
```

### 2. Обновить main.py

```python
from app.services.postback_pro_service import PostbackProService
from app.handlers.postback_pro import router as postback_router, init_postback_router

# В функции create_app():

# Инициализировать PostbackProService
postback_service = PostbackProService(bot)

# Инициализировать router
init_postback_router(postback_service, bot)

# Зарегистрировать router
app.include_router(postback_router)
```

### 3. Обновить .env

```bash
# Secret keys для партнеров
POSTBACK_SECRET_1WIN=your-secret-key-from-1win
POSTBACK_SECRET_STAKE=your-secret-key-from-stake
POSTBACK_SECRET_ROOBET=your-secret-key-from-roobet

# Encryption key (для будущих расширений)
ENCRYPTION_KEY=your-encryption-key-32-chars
```

### 4. Перезагрузить бота

```bash
python main.py
```

---

## ⚙️ Конфигурация

### IP Whitelist

**Файл:** `app/services/postback_pro_service.py`

```python
IP_WHITELIST = {
    "1win": ["1.2.3.4", "5.6.7.8"],
    "stake": ["10.11.12.13"],
    "roobet": ["14.15.16.17"],
}
```

### Rate Limiting

**Файл:** `app/services/postback_pro_service.py`

```python
RATE_LIMIT_WINDOW = 60  # 1 минута
RATE_LIMIT_MAX_REQUESTS = 100  # 100 запросов в минуту
```

### VIP Duration

**Файл:** `app/services/postback_pro_service.py`

```python
VIP_DURATION_HOURS = 48  # 48 часов при первом депозите
```

---

## 🔌 API Endpoints

### 1. POST /api/postback/{partner_name}

**Основной endpoint для приема постбеков.**

**Параметры:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `click_id` | string (UUID) | ✅ | Уникальный ID клика |
| `event` | string | ✅ | Тип события (register, first_deposit, deposit, withdrawal, win) |
| `timestamp` | integer | ✅ | Unix timestamp события |
| `signature` | string | ✅ | HMAC-SHA256 подпись |
| `amount` | float | ❌ | Сумма (для депозитов/выводов) |
| `currency` | string | ❌ | Валюта (USD, EUR, RUB) |

**Пример запроса:**

```bash
curl -X POST "http://localhost:3000/api/postback/1win" \
  -H "Content-Type: application/json" \
  -d '{
    "click_id": "550e8400-e29b-41d4-a716-446655440000",
    "event": "register",
    "timestamp": 1234567890,
    "signature": "abc123def456...",
    "amount": 100,
    "currency": "USD"
  }'
```

**Ответ (успех):**

```json
{
  "status": "success",
  "message": "Registration processed",
  "partner": "1win"
}
```

**Ответ (ошибка):**

```json
{
  "detail": "Invalid signature"
}
```

### 2. GET /api/postback/health

**Проверка здоровья сервиса.**

```bash
curl -X GET "http://localhost:3000/api/postback/health"
```

**Ответ:**

```json
{
  "status": "healthy",
  "service": "PostbackProService",
  "version": "1.0.0"
}
```

### 3. POST /api/postback/test

**Тестирование постбеков (для разработки).**

```bash
curl -X POST "http://localhost:3000/api/postback/test?partner_name=1win&event=register"
```

**Параметры:**

| Параметр | Описание |
|----------|---------|
| `partner_name` | Имя партнера (1win, stake, roobet) |
| `event` | Тип события |
| `click_id` | Click ID (опционально, используется фиксированный) |
| `amount` | Сумма (для депозитов) |

### 4. GET /api/postback/audit

**Получить логи аудита.**

```bash
curl -X GET "http://localhost:3000/api/postback/audit?partner_name=1win&limit=50"
```

**Параметры:**

| Параметр | Описание |
|----------|---------|
| `partner_name` | Фильтр по партнеру |
| `limit` | Максимум записей (по умолчанию 100) |
| `offset` | Смещение |

### 5. GET /api/postback/stats

**Получить статистику постбеков.**

```bash
curl -X GET "http://localhost:3000/api/postback/stats?partner_name=1win&days=7"
```

**Параметры:**

| Параметр | Описание |
|----------|---------|
| `partner_name` | Фильтр по партнеру |
| `days` | Количество дней (по умолчанию 7) |

---

## 📝 Примеры

### Пример 1: Регистрация пользователя

**Шаг 1: Пользователь нажимает кнопку "🎰 Перейти в казино"**

```python
# В боте
click_id = str(uuid.uuid4())  # 550e8400-e29b-41d4-a716-446655440000
casino_url = f"https://1win.com?subid={click_id}"

# Сохранить в БД
await db.create_click_tracking(user_id, click_id, "1win")

# Отправить ссылку
await bot.send_message(user_id, f"[Перейти в казино]({casino_url})")
```

**Шаг 2: Пользователь регистрируется в казино**

```
1Win видит: subid=550e8400-e29b-41d4-a716-446655440000
1Win отправляет постбек:
POST /api/postback/1win
{
  "click_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "register",
  "timestamp": 1234567890,
  "signature": "abc123def456..."
}
```

**Шаг 3: Бот обрабатывает постбек**

```
1. Проверить IP ✅
2. Проверить Rate Limit ✅
3. Валидировать данные ✅
4. Проверить timestamp ✅
5. Проверить подпись ✅
6. Проверить дубль ✅
7. Найти пользователя по click_id ✅
8. Отправить сообщение:
   "✅ Аккаунт создан!
    Теперь ты можешь тестировать наши сигналы. 📊
    Сделай первый депозит и получи VIP доступ! 🔥"
9. Логировать аудит ✅
```

### Пример 2: Первый депозит

**Постбек от казино:**

```json
{
  "click_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "first_deposit",
  "amount": 100,
  "currency": "USD",
  "timestamp": 1234567900,
  "signature": "def456abc123..."
}
```

**Действия бота:**

```
1. Проверить все защиты ✅
2. Найти пользователя по click_id ✅
3. Выдать VIP на 48 часов ✅
4. Обновить статистику ✅
5. Отправить сообщение:
   "🔥 Депозит получен!
    Сумма: 100 USD
    🎉 VIP доступ активирован на 48 часов!
    Теперь ты получаешь эксклюзивные сигналы и приоритетную поддержку! 💎"
6. Логировать аудит ✅
```

### Пример 3: Повторный депозит

**Постбек от казино:**

```json
{
  "click_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "deposit",
  "amount": 50,
  "currency": "USD",
  "timestamp": 1234568000,
  "signature": "ghi789def456..."
}
```

**Действия бота:**

```
1. Проверить все защиты ✅
2. Найти пользователя по click_id ✅
3. Обновить lifetime_value (+50) ✅
4. Увеличить deposits_count ✅
5. Отправить сообщение:
   "💰 Депозит получен!
    Сумма: 50 USD
    Спасибо за доверие! Следи за нашими сигналами! 📊"
6. Логировать аудит ✅
```

---

## 📊 Мониторинг

### Просмотр логов аудита

```bash
# Все логи
curl -X GET "http://localhost:3000/api/postback/audit?limit=100"

# Логи конкретного партнера
curl -X GET "http://localhost:3000/api/postback/audit?partner_name=1win&limit=50"

# Поиск ошибок
curl -X GET "http://localhost:3000/api/postback/audit?limit=100" | grep '"status": "failed"'
```

### Статистика

```bash
# Статистика за последние 7 дней
curl -X GET "http://localhost:3000/api/postback/stats?days=7"

# Статистика конкретного партнера
curl -X GET "http://localhost:3000/api/postback/stats?partner_name=1win&days=30"
```

### Запросы к БД

```sql
-- Все постбеки за последний час
SELECT * FROM postback_logs 
WHERE processed_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY processed_at DESC;

-- Ошибки обработки
SELECT * FROM postback_audit_logs 
WHERE status = 'failed'
ORDER BY timestamp DESC;

-- Статистика по партнерам
SELECT partner_name, COUNT(*) as total_events, COUNT(DISTINCT user_id) as unique_users
FROM postback_logs
WHERE processed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY partner_name;

-- Дублирующиеся события
SELECT event_id, COUNT(*) as count
FROM postback_logs
GROUP BY event_id
HAVING count > 1;
```

---

## 🔧 Troubleshooting

### Проблема: "Invalid signature"

**Причины:**
1. Secret key не совпадает
2. Данные изменены при передаче
3. Неправильный порядок параметров

**Решение:**
1. Проверить secret key в конфиге
2. Проверить что данные не изменяются
3. Убедиться что параметры отсортированы

### Проблема: "IP not allowed"

**Причины:**
1. IP адрес казино не в whitelist
2. Казино использует другой IP

**Решение:**
1. Добавить IP в `IP_WHITELIST`
2. Проверить IP адрес казино в документации

### Проблема: "Rate limit exceeded"

**Причины:**
1. Слишком много запросов в минуту
2. DDoS атака

**Решение:**
1. Увеличить `RATE_LIMIT_MAX_REQUESTS` если нужно
2. Проверить логи аудита на аномалии

### Проблема: "Event too old"

**Причины:**
1. Часовой сдвиг на сервере казино
2. Задержка при отправке постбека

**Решение:**
1. Синхронизировать время на сервере
2. Увеличить `MAX_EVENT_AGE_SECONDS` если нужно

### Проблема: "Duplicate event"

**Причины:**
1. Казино отправил постбек дважды
2. Сетевая ошибка привела к повтору

**Решение:**
1. Это нормально! Система защищена от дублей
2. Проверить логи аудита для подтверждения

---

## 📈 Production Checklist

Перед развертыванием в production:

- [ ] Применена миграция БД
- [ ] Обновлен main.py
- [ ] Обновлены secret keys в .env
- [ ] Обновлены IP адреса в IP_WHITELIST
- [ ] Протестированы все endpoints
- [ ] Проверены логи аудита
- [ ] Настроен мониторинг
- [ ] Настроена резервная копия БД
- [ ] Протестирована обработка ошибок
- [ ] Документация обновлена

---

## 🚀 Развертывание

### Docker

```dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

```bash
docker build -t gambling-bot .
docker run -d --name gambling-bot \
  -e DATABASE_URL="mysql://..." \
  -e POSTBACK_SECRET_1WIN="..." \
  -e POSTBACK_SECRET_STAKE="..." \
  -p 3000:3000 \
  gambling-bot
```

### Systemd Service

```ini
[Unit]
Description=Gambling Bot with PRO Postback System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gambling_bot_production
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 📞 Поддержка

**Проблемы?** Проверьте:

1. Логи аудита: `/api/postback/audit`
2. Статистику: `/api/postback/stats`
3. Здоровье сервиса: `/api/postback/health`
4. Логи приложения: `logs/app.log`

---

**Готово к production! 🚀**
