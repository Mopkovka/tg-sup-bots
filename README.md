# Memory VPN Support Bot

Телеграм-бот поддержки на aiogram 3. Клиенты пишут боту, каждое обращение пересылается в служебную группу, операторы отвечают реплаем на сообщение тикета, и бот отправляет ответ клиенту.

## Возможности

- Выбор темы кнопками или свободное сообщение (без выбора тема считается «Другое»).
- Все сообщения клиента пишутся в один открытый тикет, пока его не закроет оператор или сам клиент.
- Ответ оператора на любое сообщение тикета уходит клиенту.
- Закрытие тикета оператором командой `/close` ответом на сообщение тикета. Закрытие клиентом командой `/close` или кнопкой «Закрыть обращение». Оба случая видны в группе.
- История тикетов хранится в SQLite (`tickets.db`).

## Структура проекта

```
test_bot/
├── bot.py            # точка входа, запуск polling
├── config.py         # загрузка настроек из .env
├── db.py             # работа с SQLite
├── faq.py            # темы обращений и текст FAQ
├── handlers.py       # обработчики сообщений и кнопок
├── requirements.txt  # зависимости
├── .env              # токен и ID группы (не коммитится)
└── tickets.db        # создаётся автоматически при первом запуске
```

## Что понадобится

- Python 3.11 или новее (код использует `datetime.UTC` и синтаксис `str | None`, поэтому версия 3.10 и ниже не подойдёт).
- Telegram-бот и его токен. Получить можно у [@BotFather](https://t.me/BotFather) командой `/newbot`.
- Группа поддержки (супергруппа) в Telegram, в которую добавлен бот с правом отправлять и читать сообщения. Бот должен иметь доступ к сообщениям группы: в BotFather отключите Group Privacy (`/setprivacy` → `Disable`) или сделайте бота администратором группы.
- ID служебной группы. Обычно он начинается с `-100`. Узнать его можно, например, через бота [@getmyid_bot](https://t.me/getmyid_bot), добавив его в группу.
- Для локального запуска: Windows, macOS или Linux, интернет и терминал.

## Настройка файла `.env`

Создайте файл `.env` в папке проекта:

```env
BOT_TOKEN=123456789:AAExampleTokenFromBotFather
SUPPORT_CHAT_ID=-1003888015937
```

Файл `.env` не должен попадать в GitHub. Добавьте его в `.gitignore`, а также `tickets.db` и `venv/`:

```gitignore
.env
tickets.db
venv/
__pycache__/
```

## Локальный запуск

### Windows (PowerShell)

```powershell
cd test_bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

### macOS / Linux

```bash
cd test_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Если в логах появилась строка `Бот запущен. Группа поддержки: ...`, бот работает. Остановить его можно сочетанием `Ctrl+C`.

Проверка: напишите боту в личные сообщения `/start`, выберите тему, и тикет должен появиться в служебной группе.

## Запуск на VPS

Ниже пример для Ubuntu 22.04 или 24.04. Команды выполняются по SSH.

### 1. Подготовка сервера

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git
```

### 2. Загрузка проекта

Проект можно залить из GitHub:

```bash
cd ~
git clone https://github.com/<ваш-аккаунт>/<репозиторий>.git test_bot
cd test_bot
```

`.env` в репозитории нет, его нужно создать на сервере вручную:

```bash
nano .env
```

Вставьте `BOT_TOKEN` и `SUPPORT_CHAT_ID`, сохраните файл (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 3. Виртуальное окружение и зависимости

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Проверьте ручной запуск:

```bash
python bot.py
```

Если всё в порядке, остановите его (`Ctrl+C`) и перейдите к автозапуску.

### 4. Автозапуск через systemd

Бот должен работать постоянно и перезапускаться после перезагрузки сервера. Создайте сервис:

```bash
sudo nano /etc/systemd/system/support-bot.service
```

Содержимое (замените `ubuntu` на своего пользователя, если он другой):

```ini
[Unit]
Description=Memory VPN Support Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/test_bot
ExecStart=/home/ubuntu/test_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Включите и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now support-bot
```

Полезные команды:

```bash
sudo systemctl status support-bot     # статус
sudo systemctl restart support-bot    # перезапуск после изменений кода
sudo systemctl stop support-bot       # остановка
journalctl -u support-bot -f          # логи в реальном времени
```

### 5. Обновление бота

```bash
cd ~/test_bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart support-bot
```

База `tickets.db` при обновлении не затрагивается, так как она не хранится в репозитории.

### Важно для VPS

- Бот работает через long polling, поэтому открывать порты и настраивать домен и SSL не нужно. Нужен только исходящий доступ к `api.telegram.org`.
- Не запускайте бота одновременно локально и на VPS с одним токеном. Telegram отдаёт обновления только одному экземпляру, и второй будет получать ошибки конфликта.
- Регулярно копируйте `tickets.db`, это единственное место, где хранится история обращений.
- Не публикуйте `.env` и токен. Если токен попал в открытый доступ, перевыпустите его в BotFather командой `/revoke`.

## Частые проблемы

| Симптом | Причина и решение |
|---|---|
| `В файле .env не задан BOT_TOKEN` | Файл `.env` не найден или пустой. Проверьте, что он лежит рядом с `bot.py`. |
| `SUPPORT_CHAT_ID должен быть числом` | В `.env` указан не числовой ID. Для групп он отрицательный и начинается с `-100`. |
| Бот не видит сообщения в группе | Отключите Group Privacy в BotFather или сделайте бота администратором группы. |
| `Conflict: terminated by other getUpdates request` | Бот запущен в двух местах одновременно. Остановите лишний экземпляр. |
| `Сейчас не получилось передать обращение` | Бот не добавлен в группу или не имеет права писать в неё. |
