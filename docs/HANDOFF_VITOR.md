# Handoff técnico — Vitor

Este documento reúne tudo o que o Vitor precisa para integrar o domínio de barbeiros, serviços e
disponibilidade ao backend atual sem duplicar ou alterar as responsabilidades de Nicolas.

## Resultado esperado

Ao final do trabalho do Vitor:

- barbeiros, serviços e a relação entre ambos existirão no banco;
- jornadas e bloqueios poderão ser persistidos;
- o sistema conseguirá consultar/exibir disponibilidade;
- `POST /api/appointments` deixará de responder `503` e usará a implementação real;
- criação e reagendamento continuarão transacionais e protegidos contra double booking;
- as 34 verificações existentes da parte de Nicolas continuarão passando;
- testes próprios do Vitor cobrirão o cálculo de disponibilidade.

## Responsabilidade do Vitor

Pertencem ao Vitor:

- `Barber` e CRUD/consulta de barbeiros;
- `Service` e CRUD/consulta de serviços;
- `BarberService`;
- `WorkingHour`;
- `BlockedPeriod`;
- geração e consulta de slots;
- implementação interna do motor de disponibilidade;
- agenda administrativa;
- implementação concreta do `AvailabilityGateway`.

Não pertencem ao Vitor:

- autenticação e sessões JWT;
- perfil de cliente;
- model e endpoints de appointments;
- cancelamento e reagendamento;
- recuperação de senha;
- Clube Nohill.

Se precisar mudar um arquivo de Nicolas para integrar, a mudança deve ser pequena e explicitamente
justificada. Não deve existir um segundo model `Appointment` nem outro fluxo de criação de reserva.

## Contrato pronto para implementação

O contrato está em `app/integrations/availability.py`:

```python
class AvailabilityGateway(Protocol):
    def check(
        self,
        *,
        barber_id: int,
        service_id: int,
        start_at: datetime,
        exclude_appointment_id: int | None = None,
    ) -> AvailabilityDecision: ...
```

A resposta deve usar exatamente um destes estados:

| Situação | Resposta |
|---|---|
| Barbeiro inexistente | `BARBER_NOT_FOUND`, sem `end_at` |
| Serviço inexistente | `SERVICE_NOT_FOUND`, sem `end_at` |
| Qualquer regra impedir a reserva | `UNAVAILABLE`, sem `end_at` |
| Reserva permitida | `AVAILABLE`, obrigatoriamente com `end_at` |

`end_at` deve:

- ser um `datetime` timezone-aware;
- estar normalizado ou ser conversível para UTC;
- ser estritamente posterior a `start_at`;
- ser calculado pela fonte oficial da duração do serviço.

Appointments transforma respostas inválidas em `502 INVALID_AVAILABILITY_RESPONSE`. Portanto,
`AVAILABLE` sem `end_at`, data naive ou duração negativa são violações do contrato.

## Semântica de `check`

O método deve validar, na ordem mais simples e legível:

1. o barbeiro existe e pode receber agendamentos;
2. o serviço existe e pode ser agendado;
3. o barbeiro executa aquele serviço;
4. a duração efetiva do serviço é conhecida;
5. o intervalo está totalmente dentro da jornada aplicável;
6. o intervalo não cruza um período bloqueado;
7. não existe appointment `scheduled` sobreposto;
8. demais regras comerciais explicitamente aprovadas.

A fórmula normal de sobreposição de intervalos é:

```text
existing.start_at < requested_end
AND
existing.end_at > requested_start
```

Não usar `<=` nessa fórmula se dois atendimentos adjacentes puderem encostar — por exemplo, um
termina às 10:00 e o próximo começa às 10:00. Se houver buffer entre atendimentos, ele precisa ser
um requisito explícito e entrar no intervalo calculado.

No reagendamento, quando `exclude_appointment_id` estiver preenchido, esse appointment deve ser
excluído da consulta de conflito. Nenhum outro appointment pode ser ignorado.

## Regra transacional obrigatória

`AppointmentService` já faz o seguinte antes de chamar o gateway:

```text
advisory lock transacional por barber_id
    -> gateway.check(...)
    -> INSERT ou UPDATE do appointment
    -> COMMIT
```

A implementação do Vitor deve:

- usar a mesma `db.session` do Flask-SQLAlchemy;
- consultar o banco dentro da transação que já está aberta;
- não chamar `commit()`;
- não chamar `rollback()`;
- não abrir outra session/connection para a validação;
- não usar cache como fonte final da decisão;
- não capturar e esconder erros de banco.

No PostgreSQL, o segundo request para o mesmo barbeiro espera o primeiro terminar. Depois do lock,
o gateway precisa fazer uma nova consulta autoritativa; não pode reutilizar uma disponibilidade
calculada antes do lock.

A lista pública de slots é apenas informativa. Mesmo que o frontend tenha acabado de consultar um
slot, `check` precisa validar novamente durante a criação/reagendamento.

## Modelagem mínima a confirmar

Uma modelagem proporcional provavelmente precisará de:

```text
Barber
    id
    name
    active

Service
    id
    name
    duration_minutes
    price, se preço já for requisito
    active

BarberService
    barber_id
    service_id
    campos específicos somente se houver variação real por barbeiro

WorkingHour
    barber_id
    weekday
    start_time
    end_time

BlockedPeriod
    barber_id
    start_at
    end_at
    reason, somente se necessário para administração
```

Não copiar essa lista cegamente. Antes, confirmar onde fica a duração efetiva: em `Service` ou em
`BarberService`. Deve haver apenas uma fonte oficial para o gateway.

Constraints e índices recomendados:

- duração maior que zero;
- `end_time > start_time` e `end_at > start_at`;
- `weekday` entre 0 e 6, com convenção documentada;
- unique composto em `BarberService(barber_id, service_id)`;
- índices em foreign keys e intervalos consultados;
- `Numeric/Decimal` para dinheiro, nunca `float`;
- política clara para registros ativos/inativos versus exclusão física.

Evitar deletar barbeiro ou serviço que já possua histórico. Inativação costuma preservar melhor os
appointments, mas essa escolha precisa ser confirmada com a Nohill.

## Timezone

Appointments entrega `start_at` normalizado para UTC.

- Períodos absolutos, como `BlockedPeriod`, devem ser persistidos em UTC com timezone.
- Jornada semanal recorrente pode usar `time` local e `weekday`.
- Ao comparar jornada com appointment, converter usando `America/Sao_Paulo` via `zoneinfo`.
- Não usar `datetime.now()` nem misturar datetime naive com timezone-aware.
- Horário de verão histórico deve ser tratado pela timezone, nunca por offset fixo `-03:00`.

## Migrations e integração dos models

O Vitor deve criar uma nova revision Alembic; não editar a migration inicial de Nicolas depois que
ela já foi compartilhada/aplicada.

Ordem dentro da nova migration:

1. criar tabelas de barbeiros e serviços;
2. criar tabelas de associação, jornadas e bloqueios;
3. criar índices e constraints;
4. adicionar foreign key de `appointments.barber_id` para a tabela real de barbeiros;
5. adicionar foreign key de `appointments.service_id` para a tabela real de serviços.

As colunas `appointments.barber_id` e `appointments.service_id` já existem como `Integer` e possuem
índice. Não criar colunas duplicadas.

Todos os models devem ser importados em `app/models.py`, pois esse arquivo alimenta a descoberta do
Alembic. Depois executar:

```powershell
python -m flask --app run.py db migrate -m "add availability domain"
python -m flask --app run.py db upgrade
python -m flask --app run.py db check
```

Revisar manualmente a migration gerada antes de aplicá-la.

## Registro da implementação

Depois de criar, por exemplo, `SqlAlchemyAvailabilityGateway`, registrar uma instância na factory:

```python
app.extensions["availability_gateway"] = SqlAlchemyAvailabilityGateway()
```

O registro deve acontecer depois de `db.init_app(app)`. O gateway não deve criar extensões globais
novas nem importar a instância concreta dentro de appointments.

Os testes de Nicolas substituem essa extensão por fake, portanto a implementação concreta deve
continuar intercambiável por esse único ponto.

## Módulos e rotas

Uma divisão coerente, sem obrigação de criar camadas vazias, seria:

```text
app/barbers/
app/services/
app/availability/
app/working_hours/     # ou dentro de availability, se ficar mais coeso
app/blocked_periods/   # ou dentro de availability, se ficar mais coeso
```

Routes devem validar HTTP e delegar. O motor de disponibilidade não deve morar nas routes.

Ao registrar blueprints em `app/__init__.py`, preservar os endpoints existentes. Usar os mesmos
helpers de erro/resposta para manter o contrato:

```json
{
  "data": {}
}
```

```json
{
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

Não existe contrato de URLs aprovado no repositório para barbeiros, serviços ou disponibilidade.
Alinhar com o frontend antes de fixar endpoints.

## Bloqueio para agenda administrativa

O backend atual autentica somente `Customer`; não existe model/role administrativo aprovado.

Antes de expor CRUD administrativo, Nicolas e Vitor precisam definir:

- quem é o usuário administrativo;
- se admin é entidade separada ou papel de uma identidade já existente;
- quem pode cadastrar/inativar barbeiros e serviços;
- quem pode alterar jornadas e bloqueios;
- como o primeiro admin é provisionado;
- política de auditoria para mudanças de agenda.

Vitor não deve adicionar `is_admin` ao `Customer` por conta própria nem deixar endpoints de escrita
sem autorização. Enquanto esse contrato não existir, pode implementar models, services, gateway e
testes sem publicar operações administrativas inseguras.

## Requisitos de negócio que precisam de resposta

Confirmar com a Nohill antes de codificar comportamento:

1. duração é igual para todos os barbeiros?
2. preço varia por barbeiro?
3. existe intervalo/buffer entre clientes?
4. qual é a granularidade dos slots: 5, 10, 15, 30 minutos?
5. há pausa de almoço ou múltiplas janelas no mesmo dia?
6. como funcionam feriados e exceções de jornada?
7. bloqueio pode ser global ou sempre pertence a um barbeiro?
8. limites de um bloqueio são inclusivos ou exclusivos?
9. barbeiros e serviços podem ser excluídos ou somente inativados?
10. um serviço inativo continua aparecendo no histórico?
11. quem pode acessar a agenda completa dos clientes?
12. quais campos e filtros o frontend precisa na consulta de slots?

Não inventar respostas para essas perguntas.

## Testes obrigatórios do Vitor

### Models/migrations

- constraints de duração e intervalos;
- unique de barber/service;
- foreign keys de appointments;
- upgrade, downgrade e `db check`.

### Gateway

- barbeiro inexistente;
- serviço inexistente;
- barbeiro não executa serviço;
- barbeiro/serviço inativo, se esse conceito for aprovado;
- dentro e fora da jornada;
- começo e fim exatos da jornada;
- período bloqueado total e parcial;
- appointment sobreposto no começo, meio e fim;
- appointment adjacente sem sobreposição;
- somente appointments `scheduled` bloqueiam;
- `exclude_appointment_id` exclui apenas o appointment informado;
- `end_at` usa a duração oficial;
- conversão correta entre UTC e `America/Sao_Paulo`.

### Integração

- criação real de appointment disponível;
- criação real indisponível;
- reagendamento real disponível/indisponível;
- dois requests concorrentes para o mesmo barbeiro;
- rollback não deixa dados parciais;
- listagem de slots nunca substitui a revalidação transacional.

Os testes do gateway não devem testar autenticação, perfil ou regras internas de appointments.

## Critério de aceite final

Antes de entregar, Vitor deve conseguir demonstrar:

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m flask --app run.py db upgrade
python -m flask --app run.py db check
```

Além disso:

- nenhum teste existente pode regredir;
- nenhuma disponibilidade pode ser presumida quando uma dependência falhar;
- nenhum endpoint administrativo pode ficar público;
- gateway não pode executar commit;
- horários devem permanecer consistentes em UTC;
- migrations devem adicionar as FKs pendentes de appointments;
- o teste concorrente decisivo deve usar PostgreSQL, porque SQLite não testa advisory locks.

