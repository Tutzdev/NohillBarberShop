# Nohill Club — backend

Backend Flask exclusivo da Nohill Club. O projeto é um monólito modular, sem multi-tenancy e
sem abstrações de SaaS. Esta implementação cobre apenas a responsabilidade de Nicolas: core,
autenticação, cliente/perfil e agendamentos.

## Estado e decisões

O diretório original estava vazio. Por isso, não havia contrato de frontend nem código do Vitor
para integrar. O módulo de appointments depende de `AvailabilityGateway`, localizado em
`app/integrations/availability.py`. O gateway padrão falha com `503`; ele nunca presume que um
horário está livre. Vitor deve fornecer uma implementação e registrá-la em:

```python
app.extensions["availability_gateway"] = RealAvailabilityGateway()
```

O Clube/assinaturas não foi modelado porque não existem requisitos sobre planos, benefícios,
ativação ou cobrança. Criar tabelas e transições agora inventaria regra comercial. Essa decisão
fica registrada como pendência, não como funcionalidade silenciosamente incompleta.

O handoff completo do domínio de Vitor está em `docs/HANDOFF_VITOR.md`.

## Executar localmente

Requer Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app run.py db upgrade
python run.py
```

`requirements.txt` é o snapshot exato validado pela equipe. `pyproject.toml` continua sendo a
fonte das dependências diretas e de suas faixas aceitas. Ao adicionar ou atualizar uma dependência,
os dois arquivos devem ser revisados juntos e a bateria de testes deve ser executada antes de
publicar o novo snapshot.

Saúde: `GET http://localhost:5000/api/health`.

## Qualidade

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m flask --app run.py db check
```

`db.create_all()` aparece somente nas fixtures isoladas. Evolução real do schema usa Alembic.

## Configuração e produção

Variáveis estão descritas em `.env.example`. Produção falha no startup se secrets, banco,
rate-limit compartilhado ou SMTP estiverem ausentes. PostgreSQL é obrigatório em produção porque
o fluxo de agendamento utiliza `pg_advisory_xact_lock` por barbeiro.

Redis é usado somente como contador compartilhado do rate limiter quando há mais de um worker ou
instância. Não é cache de domínio, fila nem requisito do desenvolvimento local. Essa dependência
evita que um atacante multiplique o limite pelo número de processos da aplicação.

Antes de iniciar uma versão nova em produção, execute `flask --app wsgi.py db upgrade` como uma
etapa única de release. Depois, inicie `gunicorn wsgi:app`. Não execute migrations simultaneamente
em todos os workers.

O container não embute secrets. Passe-os pelo gerenciador de segredos do ambiente. Configure
`CORS_ORIGINS` com as origens exatas do frontend e um storage compartilhado compatível com a
biblioteca `limits` em `RATELIMIT_STORAGE_URI`.

## Segurança

- Senhas usam Argon2id com salt gerado pela biblioteca e nunca são serializadas.
- JWTs ficam no header `Authorization`, não em cookies; por isso CSRF de cookie não se aplica.
- Access tokens são curtos. Refresh tokens rotacionam atomicamente e pertencem a uma sessão
  revogável; logout e troca de senha invalidam a sessão no banco.
- Recuperação de senha usa token imprevisível, de uso único e com expiração. Só SHA-256 do token
  fica no banco; SMTP recebe o valor bruto apenas para entrega.
- Queries de recursos privados sempre incluem `customer_id`, evitando IDOR e também evitando
  confirmar que um ID de outro cliente existe.
- Schemas rejeitam campos desconhecidos, impedindo mass assignment.
- Login, cadastro e recuperação de senha possuem rate limit.
- Respostas 500 são sanitizadas e recebem request ID; logs não incluem body, token ou senha.
- Headers defensivos e CORS restrito são aplicados globalmente.

## Datas, transações e double booking

A API exige ISO 8601 com offset. O domínio normaliza tudo para UTC e responde com sufixo `Z`.
Horário de Brasília deve ser enviado, por exemplo, como `2026-08-20T14:00:00-03:00`.

Em PostgreSQL, criação e reagendamento:

1. adquirem lock transacional por barbeiro;
2. consultam Availability dentro da mesma transação;
3. gravam e fazem um único commit;
4. transformam colisões em `409 TIME_SLOT_UNAVAILABLE`.

O lock serializa decisões para o mesmo barbeiro. O gateway real deve consultar dados autoritativos
no banco, na mesma sessão/transação, e não uma cache potencialmente obsoleta. A constraint parcial
`(barber_id, start_at) WHERE status = 'scheduled'` é uma segunda barreira para inícios idênticos.
O término vem obrigatoriamente do gateway de Vitor; appointments não calcula duração.

O model também usa versionamento otimista. Cancelamentos e reagendamentos concorrentes do mesmo
registro geram conflito em vez de sobrescrever silenciosamente uma alteração mais recente.

## Estrutura

```text
app/
  auth/            cadastro, login, sessão, refresh e recuperação de senha
  customers/       perfil do próprio cliente
  appointments/    casos de uso e persistência de agendamentos
  integrations/    contratos com Availability e SMTP
  common/          erros, respostas, tempo e logging
  config/          factory, extensões e ambientes
migrations/        evolução do banco
tests/             testes de comportamento e integração HTTP
docs/API.md        contrato dos endpoints
```

## O que Nicolas deve aprender com esta base

Application Factory permite criar aplicações com configurações independentes nos testes e evita
amarrar extensões a uma instância global. Routes traduzem HTTP; services coordenam casos de uso;
models preservam o formato persistido. Essa separação mantém cada mudança no lugar de seu motivo.

Hash não é criptografia: não deve ser reversível. Argon2id é deliberadamente lento e usa salt para
reduzir o valor de tabelas pré-computadas em caso de vazamento. JWT, por outro lado, é uma
credencial assinada; sua assinatura não oferece logout. A sessão persistida é o que torna revogação
e rotação reais.

A checagem “está disponível?” seguida de insert é uma operação composta. Sem lock ou constraint,
dois requests podem observar o mesmo estado. Pensar como desenvolvedor experiente significa
procurar invariantes que o banco também consiga defender, delimitar a transação e testar o caminho
de conflito — não confiar apenas na ordem aparente do código Python.
