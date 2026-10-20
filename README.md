# Kittygram

Сервис для владельцев котиков: пользователь регистрируется, добавляет своих
питомцев с фото и достижениями и смотрит котиков других пользователей.
Бэкенд — REST API на Django REST Framework, фронтенд — SPA на React
(из учебного проекта Яндекс Практикума), всё вместе запускается в Docker
или разворачивается на сервере связкой nginx + gunicorn + systemd.

В проект добавлено расширение **«Кото-дуэли»**: хозяин бросает вызов чужому
котику, остальные пользователи вслепую голосуют, а по итогам меняется
рейтинг Эло котиков. Описание — в разделе [Кото-дуэли](#кото-дуэли).

## Стек

Python 3.12, Django 5.2, Django REST Framework 3.18, Djoser (регистрация и
токены), django-filter, drf-spectacular (Swagger/ReDoc), PostgreSQL 16,
gunicorn, nginx, Docker Compose, React 17, pytest.

## Структура репозитория

```
backend/            Django-проект
  kittygram_backend/  настройки и маршруты
  cats/               котики и достижения
  duels/              расширение «Кото-дуэли»
  tests/              тесты API (pytest)
  Dockerfile, entrypoint.sh
frontend/           SPA на React и его Dockerfile
nginx/              конфигурация шлюза для Docker
deploy/             деплой без Docker: deploy.sh, unit systemd, конфиг nginx
docs/postman/       коллекция Postman
docker-compose.yml
.env.example        образец переменных окружения
```

## Запуск в Docker

Нужны Docker и Docker Compose.

```bash
git clone https://github.com/<ваш-логин>/kittygram.git
cd kittygram
cp .env.example .env          # задать SECRET_KEY и POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

Сайт откроется на http://localhost:9000, документация API — на
http://localhost:9000/api/docs/ (Swagger) и http://localhost:9000/api/redoc/.

Что происходит при старте: контейнер `db` поднимает PostgreSQL; `backend`
ждёт готовности базы, выполняет миграции, собирает статику Django в общий
том и запускает gunicorn; `frontend` собирает SPA и копирует его в тот же
том; `gateway` (nginx) раздаёт статику и проксирует `/api/` и `/admin/` в
бэкенд.

Демо-данные для показа (5 пользователей, 6 котиков, 4 дуэли):

```bash
docker compose exec backend python manage.py seed_demo
```

Остановить: `docker compose down` (данные останутся в томах),
`docker compose down -v` — с удалением данных.

## Локальный запуск без Docker

```bash
cd kittygram
cp .env.example .env
# в .env закомментировать POSTGRES_DB — тогда будет SQLite,
# и поставить DEBUG=True
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r backend/requirements-dev.txt
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API: http://127.0.0.1:8000/api/, Swagger: http://127.0.0.1:8000/api/docs/.

Фронтенд отдельно (нужен Node.js 18+): в `frontend/src/utils/constants.js`
указать `URL = "http://127.0.0.1:8000"`, затем `npm ci && npm start` в
папке `frontend`. Адрес http://localhost:3000 уже разрешён в
`CORS_ALLOWED_ORIGINS`.

Тесты и линтер:

```bash
cd backend
pytest
flake8 .
```

## Переменные окружения

| Переменная | Назначение | Пример |
|---|---|---|
| `SECRET_KEY` | секретный ключ Django | длинная случайная строка |
| `DEBUG` | режим отладки | `False` |
| `ALLOWED_HOSTS` | допустимые хосты через запятую | `localhost,127.0.0.1,backend` |
| `CSRF_TRUSTED_ORIGINS` | доверенные источники для форм (админка) | `http://localhost:9000` |
| `CORS_ALLOWED_ORIGINS` | источники для запуска SPA отдельно | `http://localhost:3000` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | база PostgreSQL; без `POSTGRES_DB` используется SQLite | `kittygram` |
| `DB_HOST`, `DB_PORT` | адрес базы: `db` в Docker, `localhost` на сервере | `db`, `5432` |
| `GATEWAY_PORT` | порт сайта в Docker | `9000` |
| `THROTTLE_ANON`, `THROTTLE_USER`, `THROTTLE_DUEL_VOTES` | лимиты запросов | `200/hour` |
| `DUEL_ELO_K`, `DUEL_MAX_OPEN_PER_CAT` | коэффициент Эло, лимит открытых дуэлей котика | `32`, `3` |
| `STATIC_ROOT`, `MEDIA_ROOT` | необязательно: куда собирать статику и класть фото | — |

## API

Все запросы, кроме регистрации, получения токена и таблицы лидеров, требуют
заголовок `Authorization: Token <токен>`.

| Метод и адрес | Что делает |
|---|---|
| `POST /api/users/` | регистрация |
| `POST /api/token/login/`, `POST /api/token/logout/` | получить / удалить токен |
| `GET /api/users/me/` | текущий пользователь |
| `GET, POST /api/cats/` | список котиков (пагинация, фильтры, поиск, сортировка), добавить котика |
| `GET, PUT, PATCH, DELETE /api/cats/{id}/` | карточка котика; менять и удалять может только хозяин |
| `GET, POST /api/achievements/` | достижения; менять и удалять — только администратор |
| `GET /api/docs/`, `GET /api/redoc/`, `GET /api/schema/` | документация OpenAPI |

Параметры списка котиков: `page`, `page_size` (до 50), `color`,
`birth_year_min`, `birth_year_max`, `owner`, `achievement`, `mine`,
`search` (по кличке), `ordering` (`name`, `birth_year`, `-birth_year`, …).

Примеры (curl и httpie):

```bash
# регистрация и токен
curl -X POST http://localhost:9000/api/users/ -H "Content-Type: application/json" \
     -d '{"username": "anna", "password": "Kittygram-2026"}'
curl -X POST http://localhost:9000/api/token/login/ -H "Content-Type: application/json" \
     -d '{"username": "anna", "password": "Kittygram-2026"}'

# добавить котика (цвет передаётся в HEX, в ответе — название)
http POST :9000/api/cats/ "Authorization:Token $TOKEN" \
     name=Барсик color="#FFFFFF" birth_year:=2019

# белые котики, сначала младшие
http :9000/api/cats/ color==white ordering==-birth_year "Authorization:Token $TOKEN"
```

## Кото-дуэли

Хозяин вызывает своим котиком на дуэль котика другого пользователя.
Если соперник принимает вызов, начинается голосование (от 1 до 72 часов).
Голосовать могут все, кроме хозяев участников, по одному голосу за дуэль.
Счёт до конца голосования скрыт — видно только число проголосовавших, чтобы
ранние голоса не влияли на поздние. После окончания любой пользователь
подводит итоги, и рейтинг котиков пересчитывается по формуле Эло, где
результат — доля голосов: победа 9:1 приносит больше очков, чем 6:4, а
победа над сильным соперником — больше, чем над слабым. Дуэль без голосов
не засчитывается.

| Метод и адрес | Кто может | Что делает |
|---|---|---|
| `GET /api/duels/` | авторизованный | лента дуэлей: `status`, `cat`, `mine`, `incoming`, `created_after`, `created_before`, `ordering`, пагинация `limit`/`offset` |
| `POST /api/duels/` | хозяин котика-участника | бросить вызов |
| `GET /api/duels/{id}/` | авторизованный | дуэль, число голосов и свой голос |
| `POST /api/duels/{id}/accept/` | хозяин соперника | принять вызов — старт голосования |
| `POST /api/duels/{id}/decline/` | хозяин соперника | отклонить вызов |
| `POST /api/duels/{id}/cancel/` | автор вызова | отменить, пока вызов не принят |
| `POST /api/duels/{id}/vote/` | не хозяин участников | голос `{"cat": id}` |
| `POST /api/duels/{id}/finish/` | авторизованный после окончания голосования, администратор — в любой момент | подвести итоги |
| `GET /api/duels/{id}/results/` | авторизованный | счёт и изменение рейтинга (после итогов) |
| `GET /api/ratings/` | любой, без токена | таблица лидеров: `min_duels`, `owner`, `ordering`, `page` |
| `GET /api/ratings/{cat_id}/` | любой, без токена | рейтинг и статистика котика |

Проверки: вызывать можно только своим котиком и только чужого; между двумя
котиками не может быть двух незавершённых дуэлей; у котика не больше трёх
незавершённых дуэлей; длительность голосования 1–72 часа; один голос на
пользователя (ограничение и в базе); голосовать можно только в активной
дуэли до окончания времени.

Пример сценария:

```bash
http POST :9000/api/duels/ "Authorization:Token $ANNA" challenger:=1 opponent:=3 voting_hours:=24
http POST :9000/api/duels/1/accept/ "Authorization:Token $BORIS"
http POST :9000/api/duels/1/vote/ "Authorization:Token $VERA" cat:=1
http POST :9000/api/duels/1/finish/ "Authorization:Token $ANNA"   # после окончания голосования
http :9000/api/duels/1/results/ "Authorization:Token $ANNA"
http :9000/api/ratings/
```

Истёкшие дуэли можно завершать по расписанию командой
`python manage.py finish_duels` (например, из cron раз в 10 минут).

## Postman

Коллекция `docs/postman/kittygram.postman_collection.json` проверяет базовый
API и полный сценарий дуэли (регистрация участников, вызов, ответ,
голосование, итоги, ошибки 400/403). Импортируйте её в Postman, задайте
переменные `base_url` (по умолчанию `http://localhost:9000`),
`admin_username` и `admin_password` (суперпользователь нужен, чтобы подвести
итоги, не дожидаясь конца голосования) и запустите через Run collection.
Из консоли: `npx newman run docs/postman/kittygram.postman_collection.json`.

## Деплой на сервер (nginx + gunicorn + systemd)

Сервер с Ubuntu 22.04/24.04, пользователь с sudo, Node.js 18+ для сборки
фронтенда (в Ubuntu 24.04 ставится из apt).

```bash
git clone https://github.com/<ваш-логин>/kittygram.git
cd kittygram
cp .env.example .env    # DB_HOST=localhost, ALLOWED_HOSTS=<IP сервера>, свой SECRET_KEY
SERVER_NAME=<IP или домен> bash deploy/deploy.sh
```

Скрипт ставит пакеты, создаёт базу и пользователя PostgreSQL, создаёт
виртуальное окружение, выполняет миграции и `collectstatic`, собирает
фронтенд и кладёт его вместе со статикой в `/var/www/kittygram`,
устанавливает сервис `gunicorn_kittygram` (gunicorn на 127.0.0.1:8000)
и сайт nginx. Повторный запуск обновляет проект после `git pull`.

Проверка:

```bash
sudo systemctl status gunicorn_kittygram
sudo nginx -t
curl -I http://<IP сервера>/
curl http://<IP сервера>/api/ratings/
```

## Автор

Бронников Максим Романович, группа ПИ2у/23Б, РЭУ им. Г. В. Плеханова.
