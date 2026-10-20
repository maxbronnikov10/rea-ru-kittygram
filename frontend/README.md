# Фронтенд Kittygram

SPA на React из учебного проекта Яндекс Практикума
([yandex-praktikum/kittygram_final](https://github.com/yandex-praktikum/kittygram_final),
лицензия MIT — см. `LICENSE`). Код не менялся: фронтенд обращается к API по
относительным адресам `/api/...`, поэтому работает за тем же nginx, что и бэкенд.

Сборка: `npm ci && npm run build` (Node.js 18+). В Docker сборку выполняет
`Dockerfile` этой папки.
