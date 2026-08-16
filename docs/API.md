# API de Nicolas

Base URL: `/api`. Requests JSON devem usar `Content-Type: application/json`. Sucessos usam
`{"data": ...}`; erros usam `{"error": {"code": "...", "message": "..."}}` e podem incluir
`details` de validação. Datas são ISO 8601 e normalizadas para UTC.

Endpoints protegidos recebem `Authorization: Bearer <access_token>`.

## Auth

### `POST /auth/register`

Sem autenticação. Limite: 5/minuto por IP.

```json
{
  "name": "Nicolas Silva",
  "email": "nicolas@example.com",
  "phone": "+5511999999999",
  "password": "uma-senha-com-10-ou-mais"
}
```

Retorna `201` com cliente sem hash de senha. Erros: `409 EMAIL_ALREADY_REGISTERED`,
`422 VALIDATION_ERROR`, `429 RATE_LIMIT_EXCEEDED`.

### `POST /auth/login`

Sem autenticação. Body: `email`, `password`. Retorna `200` com `customer`, `access_token` e
`refresh_token`. Conta inexistente e senha incorreta retornam a mesma resposta
`401 INVALID_CREDENTIALS`. Também pode retornar `422` e `429`.

### `POST /auth/refresh`

Requer refresh token no header. Retorna `200` com um novo par de tokens e invalida atomicamente o
refresh anterior. Erros: `401 TOKEN_EXPIRED`, `INVALID_TOKEN` ou `TOKEN_REVOKED`.

### `POST /auth/logout`

Aceita access ou refresh token. Retorna `204` e revoga toda a sessão correspondente.

### `POST /auth/change-password`

Requer access token. Body:

```json
{"current_password": "senha-atual", "new_password": "nova-senha-segura"}
```

Retorna `204` e revoga todas as sessões do cliente. Erros: `401 INVALID_CREDENTIALS`,
`409 PASSWORD_UNCHANGED`, `422`, `429`.

### `POST /auth/forgot-password`

Sem autenticação. Body: `{"email": "nicolas@example.com"}`. Sempre retorna `200` com texto neutro,
exista ou não a conta. Limite: 3/hora. Para contas existentes, envia link pelo SMTP configurado.

### `POST /auth/reset-password`

Sem autenticação. Body: `token`, `new_password`. Retorna `204`. Token inválido, expirado ou já
usado retorna `401`. A operação invalida todas as sessões existentes.

## Customer

### `GET /customers/me`

Requer access token. Retorna `200` com `id`, `name`, `email`, `phone`, `created_at`, `updated_at`.

### `PATCH /customers/me`

Requer access token. Aceita somente `name`, `email` e `phone`; todos são opcionais. Retorna `200`.
Campo desconhecido retorna `422`; e-mail já usado retorna `409 EMAIL_ALREADY_REGISTERED`.

## Appointments

O backend retorna `503 INTEGRATION_UNAVAILABLE` enquanto o gateway real de Availability não for
registrado.

### `POST /appointments`

Requer access token.

```json
{
  "barber_id": 10,
  "service_id": 20,
  "start_at": "2026-08-20T14:00:00-03:00"
}
```

Retorna `201` com o agendamento. Erros: `404 BARBER_NOT_FOUND`/`SERVICE_NOT_FOUND`,
`409 TIME_SLOT_UNAVAILABLE`, `422 INVALID_DATETIME`/`VALIDATION_ERROR`, `502` para violação do
contrato pelo gateway e `503` sem integração.

### `GET /appointments/me`

Requer access token. Query opcional: `status=scheduled|cancelled`, `page` (default 1) e `per_page`
(default 20, máximo 100). Retorna `200` com `items`, `page`, `per_page`, `total`.

### `GET /appointments/{id}`

Requer access token e propriedade do recurso. Retorna `200`; ID inexistente ou de outro cliente
retorna o mesmo `404 APPOINTMENT_NOT_FOUND`.

### `PATCH /appointments/{id}/cancel`

Requer access token e propriedade. Sem body. Retorna `200` com status `cancelled`; repetição ou
estado não cancelável retorna `409 INVALID_APPOINTMENT_STATE`. O registro não é apagado.

Não foi inventado prazo comercial de cancelamento. Quando a Nohill defini-lo, a regra deve entrar
no service e receber testes.

### `PATCH /appointments/{id}/reschedule`

Requer access token e propriedade. Body:

```json
{"start_at": "2026-08-21T15:30:00-03:00"}
```

Retorna `200`. Revalida Availability dentro da transação. Pode retornar os mesmos erros da criação,
além de `409 INVALID_APPOINTMENT_STATE` e `409 APPOINTMENT_CHANGED` em corrida concorrente.

