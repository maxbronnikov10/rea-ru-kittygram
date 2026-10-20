"""Собирает коллекцию Postman kittygram.postman_collection.json.

Запуск: python docs/postman/build_collection.py
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name('kittygram.postman_collection.json')


def script(lines):
    return [{'listen': 'test',
             'script': {'type': 'text/javascript', 'exec': lines}}]


def status_test(code, extra=()):
    return script([
        f"pm.test('Статус {code}', () => pm.response.to.have.status({code}));",
        *extra,
    ])


def request(name, method, path, token=None, body=None, tests=None,
            description=''):
    url_raw = '{{base_url}}' + path
    path_part, _, query = path.partition('?')
    url = {'raw': url_raw, 'host': ['{{base_url}}'],
           'path': [p for p in path_part.split('/') if p]}
    if query:
        url['query'] = [dict(zip(('key', 'value'), q.split('=', 1)))
                        for q in query.split('&')]
    headers = [{'key': 'Content-Type', 'value': 'application/json'}]
    if token:
        headers.append({'key': 'Authorization',
                        'value': 'Token {{' + token + '}}'})
    item = {
        'name': name,
        'request': {'method': method, 'header': headers, 'url': url,
                    'description': description},
        'event': tests or [],
    }
    if body is not None:
        item['request']['body'] = {
            'mode': 'raw', 'raw': json.dumps(body, ensure_ascii=False,
                                             indent=2),
            'options': {'raw': {'language': 'json'}}}
    return item


LABELS = {'user_a': 'A — хозяйка Барсика', 'user_b': 'B — хозяин Мурки',
          'user_c': 'C — зритель'}


def register(user_var):
    return request(
        f'Регистрация: {LABELS[user_var]}', 'POST', '/api/users/',
        body={'username': '{{' + user_var + '}}', 'password': '{{password}}'},
        tests=status_test(201))


def login(user_var, token_var):
    return request(
        f'Токен: {LABELS[user_var]}', 'POST', '/api/token/login/',
        body={'username': '{{' + user_var + '}}', 'password': '{{password}}'},
        tests=status_test(200, [
            f"pm.collectionVariables.set('{token_var}', "
            "pm.response.json().auth_token);"]))


base = [
    register('user_a'),
    login('user_a', 'token_a'),
    request('Текущий пользователь', 'GET', '/api/users/me/', 'token_a',
            tests=status_test(200, [
                "pm.test('username совпадает', () => pm.expect("
                "pm.response.json().username).to.eql("
                "pm.collectionVariables.get('user_a')));"])),
    request('Список котиков без токена', 'GET', '/api/cats/',
            tests=status_test(401)),
    request('Добавить котика', 'POST', '/api/cats/', 'token_a',
            body={'name': 'Барсик', 'color': '#FFFFFF', 'birth_year': 2019,
                  'achievements': [{'achievement_name': 'поймал муху'}]},
            tests=status_test(201, [
                "const cat = pm.response.json();",
                "pm.collectionVariables.set('cat_a', cat.id);",
                "pm.test('Цвет сохранён названием', () => "
                "pm.expect(cat.color).to.eql('white'));"])),
    request('Котик с годом рождения в будущем', 'POST', '/api/cats/',
            'token_a', body={'name': 'Пушок', 'color': '#000000',
                             'birth_year': 2100},
            tests=status_test(400, [
                "pm.test('Ошибка в поле birth_year', () => "
                "pm.expect(pm.response.json()).to.have.property("
                "'birth_year'));"])),
    request('Список котиков с фильтром и сортировкой', 'GET',
            '/api/cats/?color=white&ordering=-birth_year&page_size=5',
            'token_a', tests=status_test(200, [
                "pm.test('Есть пагинация', () => pm.expect("
                "pm.response.json()).to.have.keys('count', 'next', "
                "'previous', 'results'));"])),
    request('Изменить своего котика', 'PATCH', '/api/cats/{{cat_a}}/',
            'token_a', body={'birth_year': 2020}, tests=status_test(200)),
    request('Достижения', 'GET', '/api/achievements/', 'token_a',
            tests=status_test(200)),
]

duels_prepare = [
    register('user_b'), login('user_b', 'token_b'),
    register('user_c'), login('user_c', 'token_c'),
    request('Котик соперника', 'POST', '/api/cats/', 'token_b',
            body={'name': 'Мурка', 'color': '#000000', 'birth_year': 2018},
            tests=status_test(201, [
                "pm.collectionVariables.set('cat_b', pm.response.json().id);"
            ])),
    request('Изменить чужого котика', 'PATCH', '/api/cats/{{cat_a}}/',
            'token_b', body={'name': 'Чужой'}, tests=status_test(403)),
    request('Токен администратора', 'POST', '/api/token/login/',
            body={'username': '{{admin_username}}',
                  'password': '{{admin_password}}'},
            tests=status_test(200, [
                "pm.collectionVariables.set('token_admin', "
                "pm.response.json().auth_token);"])),
]

duels = [
    request('Бросить вызов', 'POST', '/api/duels/', 'token_a',
            body={'challenger': '{{cat_a}}', 'opponent': '{{cat_b}}',
                  'voting_hours': 24, 'message': 'Чья шерсть пушистее?'},
            tests=status_test(201, [
                "const d = pm.response.json();",
                "pm.collectionVariables.set('duel_id', d.id);",
                "pm.test('Статус pending', () => "
                "pm.expect(d.status).to.eql('pending'));"])),
    request('Вызов своему же котику', 'POST', '/api/duels/', 'token_a',
            body={'challenger': '{{cat_a}}', 'opponent': '{{cat_a}}'},
            tests=status_test(400)),
    request('Входящие вызовы соперника', 'GET',
            '/api/duels/?incoming=true&limit=5', 'token_b',
            tests=status_test(200, [
                "pm.test('Вызов в списке', () => pm.expect("
                "pm.response.json().results.map(d => d.id)).to.include("
                "pm.collectionVariables.get('duel_id')));"])),
    request('Принять чужой вызов (не хозяин)', 'POST',
            '/api/duels/{{duel_id}}/accept/', 'token_a',
            tests=status_test(403)),
    request('Принять вызов', 'POST', '/api/duels/{{duel_id}}/accept/',
            'token_b', tests=status_test(200, [
                "pm.test('Голосование началось', () => pm.expect("
                "pm.response.json().status).to.eql('active'));"])),
    request('Голос хозяина участника', 'POST',
            '/api/duels/{{duel_id}}/vote/', 'token_a',
            body={'cat': '{{cat_b}}'}, tests=status_test(400)),
    request('Голос зрителя', 'POST', '/api/duels/{{duel_id}}/vote/',
            'token_c', body={'cat': '{{cat_a}}'}, tests=status_test(201)),
    request('Повторный голос', 'POST', '/api/duels/{{duel_id}}/vote/',
            'token_c', body={'cat': '{{cat_b}}'}, tests=status_test(400)),
    request('Итоги до завершения', 'GET', '/api/duels/{{duel_id}}/results/',
            'token_c', tests=status_test(400)),
    request('Подвести итоги до конца голосования', 'POST',
            '/api/duels/{{duel_id}}/finish/', 'token_c',
            tests=status_test(400)),
    request('Подвести итоги (администратор)', 'POST',
            '/api/duels/{{duel_id}}/finish/', 'token_admin',
            tests=status_test(200, [
                "const r = pm.response.json();",
                "pm.test('Победил котик-зачинщик', () => pm.expect("
                "r.winner).to.eql(Number(pm.collectionVariables.get("
                "'cat_a'))));",
                "pm.test('Рейтинг вырос', () => pm.expect("
                "r.result.rating.challenger.delta).to.be.above(0));"])),
    request('Итоги дуэли', 'GET', '/api/duels/{{duel_id}}/results/',
            'token_c', tests=status_test(200)),
    request('Таблица лидеров (без токена)', 'GET',
            '/api/ratings/?min_duels=1', tests=status_test(200)),
    request('Рейтинг котика', 'GET', '/api/ratings/{{cat_a}}/',
            tests=status_test(200)),
]

collection = {
    'info': {
        'name': 'Kittygram API',
        'description': 'Проверка базового API Kittygram и расширения '
                       '«Кото-дуэли». Запускать целиком (Run collection).',
        'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/'
                  'collection.json',
    },
    'event': [{'listen': 'prerequest', 'script': {
        'type': 'text/javascript',
        'exec': [
            "// Новые имена пользователей при каждом запуске коллекции",
            "if (pm.info.requestName.startsWith('Регистрация: A')",
            "    || !pm.collectionVariables.get('run_id')) {",
            "  const id = Date.now().toString(36);",
            "  pm.collectionVariables.set('run_id', id);",
            "  pm.collectionVariables.set('user_a', 'anna_' + id);",
            "  pm.collectionVariables.set('user_b', 'boris_' + id);",
            "  pm.collectionVariables.set('user_c', 'vera_' + id);",
            "}",
        ]}}],
    'item': [
        {'name': '1. Базовый API Kittygram', 'item': base},
        {'name': '2. Дуэли: подготовка', 'item': duels_prepare},
        {'name': '3. Дуэли: сценарий', 'item': duels},
    ],
    'variable': [
        {'key': 'base_url', 'value': 'http://localhost:9000'},
        {'key': 'password', 'value': 'Kittygram-2026'},
        {'key': 'admin_username', 'value': 'admin'},
        {'key': 'admin_password', 'value': 'change-me'},
        {'key': 'run_id', 'value': ''},
    ],
}

OUT.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + '\n',
               encoding='utf-8')
print(f'{OUT}: {sum(len(f["item"]) for f in collection["item"])} запросов')
