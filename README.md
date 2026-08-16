# Nohill Club — Backend

Backend do sistema personalizado da **Nohill Club**, desenvolvido em **Python com Flask**.

O projeto centraliza as principais operações da barbearia, como autenticação de clientes, serviços, barbeiros, disponibilidade de horários, agendamentos, cancelamentos, reagendamentos e assinaturas do clube.

## Tecnologias

* Python
* Flask
* SQLAlchemy
* Alembic / Flask-Migrate
* PostgreSQL
* Pytest
* API REST

## Funcionalidades

* Cadastro e autenticação de clientes
* Gerenciamento de perfil
* Cadastro de barbeiros e serviços
* Controle de horários e disponibilidade
* Criação de agendamentos
* Cancelamento e reagendamento
* Prevenção de conflitos de horários
* Planos e assinaturas do Nohill Club
* Validação e tratamento de erros
* Controle de acesso e segurança
* Testes automatizados

## Arquitetura

O backend utiliza uma arquitetura **monolítica modular**, separando as regras por domínio:

```text
app/
├── auth/
├── customers/
├── barbers/
├── services/
├── availability/
├── appointments/
└── subscriptions/
```

O foco do projeto é manter o código simples, seguro e de fácil manutenção, seguindo princípios de **Clean Code**, separação de responsabilidades e boas práticas de desenvolvimento backend.

## Executando o projeto

```bash
git clone <url-do-repositorio>
cd <nome-do-projeto>

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
flask db upgrade
flask run
```

No Windows:

```bash
.venv\Scripts\activate
```

## Testes

```bash
pytest
```

## Configuração

As configurações sensíveis são definidas por variáveis de ambiente.

Use o arquivo:

```text
.env.example
```

como referência para configurar o ambiente local.

---

Desenvolvido para a **Nohill Club**.
