# Соседние сервисы за этим Caddy

Порты 80/443 на VPS занимает Caddy из этого compose, поэтому другие сервисы
публикуются через него: свой домен — свой файл `<имя>.caddy` в этой папке.

Контейнер сервиса подключается к общей сети `web` (в его compose:
`networks: web: external: true`), и Caddy обращается к нему по имени контейнера.

Пример `kitchenowl.caddy`:

```
kitchen-example.duckdns.org {
	encode gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy kitchenowl:8080
}
```

После добавления или правки файла: `docker compose restart caddy`.
Сами `*.caddy` в git не хранятся — домены у каждого сервера свои.
