# MeuConvite

Plataforma SaaS de convites digitais para casamentos em Moçambique
(`meuconvite.co.mz`): cerimónia religiosa, cerimónia civil, recepção, copo de
água, lobolo, xiguiane e quaisquer outros eventos personalizados.

- **Interface**: português
- **Código, nomes técnicos e comentários**: inglês
- **Stack**: Python 3.12 · Django 5.2 · Django Templates · Bootstrap 5 · HTMX
- **Base de dados**: SQLite (desenvolvimento) · MySQL/MariaDB ou PostgreSQL (produção, escolhido por variável de ambiente)

---

## Estado do projeto

| Fase | Conteúdo | Estado |
| ---- | -------- | ------ |
| 1 | Configurações, utilizador personalizado, autenticação, casamentos, equipa, eventos, locais, programa, painel básico | **Concluída** |
| 2 | Convidados, famílias, importação Excel, convites individuais, página do convite, RSVP | Por iniciar |
| 3 | QR Codes, check-in, mesas, permissões avançadas, relatórios | Por iniciar |
| 4 | Templates visuais, animações, emails, WhatsApp, planos, administração da plataforma | Por iniciar |
| 5 | Testes completos, hardening, otimização, deploy, documentação final | Por iniciar |

---

## Instalação (desenvolvimento)

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Se ainda não existir um `.env` (não vem no repositório):

```bash
copy .env.example .env
```

> Se já tiver um `.env` com credenciais reais, **não execute o comando acima** —
> substituiria o ficheiro.

Em desenvolvimento o `.env` é opcional: as predefinições usam SQLite, `DEBUG=True`
e envio de emails para a consola. Mesmo com um `.env` de produção presente, o
ambiente local continua em SQLite (ver *Configuração da base de dados*).

```bash
python manage.py migrate
```

```bash
python manage.py createsuperuser
```

```bash
python manage.py runserver
```

A aplicação fica disponível em <http://127.0.0.1:8000/>.

### Dados de demonstração

```bash
python manage.py seed_demo
```

Cria um casamento fictício com noivos, wedding planner, seis eventos
(incluindo lobolo e xiguiane), três locais e o programa do dia. Nenhum dado
pessoal real é utilizado. Defina `DEMO_USER_PASSWORD` antes de executar se
quiser iniciar sessão com as contas criadas; caso contrário é gerada uma
palavra-passe aleatória que não é escrita em lado nenhum.

Para substituir os dados de demonstração existentes:

```bash
python manage.py seed_demo --reset
```

### Testes

```bash
python manage.py test
```

105 testes na fase 1, com destaque para `weddings/tests/test_isolation.py`, que
verifica o isolamento de dados entre casamentos.

---

## Arquitetura

```text
config/            configurações (base/development/production), URLs, WSGI/ASGI
core/              modelos abstratos, validadores, utilitários, rate limiting, seed_demo
accounts/          utilizador personalizado (login por email), perfil, adaptador allauth
audit/             registo de auditoria das ações críticas
weddings/          casamento (fronteira de isolamento), equipa e permissões
events/            eventos, locais e programa do dia
templates/         Django Templates (interface em português)
static/            CSS e JavaScript próprios
```

Aplicações previstas para as fases seguintes: `guests`, `invitations`, `rsvps`,
`seating`, `checkin`, `templates_manager`, `notifications`, `subscriptions`,
`reports`.

### Padrões de código

- **Views finas.** A lógica de escrita vive em `services.py`; as consultas
  complexas em `selectors.py`.
- **Isolamento por casamento.** Nenhuma view consulta `Wedding.objects` diretamente:
  usa-se `Wedding.objects.for_user(user)` através de
  `weddings.permissions.require_wedding()`, que injecta `request.wedding` e
  `request.membership`. Um casamento sem acesso responde **404** (nunca 403),
  para não confirmar a existência do registo.
- **Permissões por objeto.** `WeddingMember` guarda funções *e* permissões
  individuais (`can_manage_guests`, `can_check_in`, …). As funções servem de
  modelo inicial e podem ser ajustadas caso a caso.
- **Transações** em todas as operações compostas (`@transaction.atomic`).
- **UUID** como chave primária de todas as entidades públicas e **tokens seguros**
  (`secrets.token_urlsafe`) nas ligações públicas.
- **Auditoria** em criação, alteração, eliminação, publicação, login e gestão de
  equipa. O payload nunca inclui passwords, tokens ou emails completos.
- **Validação no backend** independentemente da validação do navegador.
- `TextChoices`, `select_related`/`prefetch_related`, índices e constraints na
  base de dados.

### Modelos da fase 1

| Modelo | Aplicação | Notas |
| ------ | --------- | ----- |
| `User` | accounts | UUID, login por email, sem username |
| `Wedding` | weddings | slug único + `public_token`, estado, cores, template, prazos |
| `WeddingMember` | weddings | função + 7 permissões individuais, único por (casamento, utilizador) |
| `WeddingLocation` | events | endereço, mapa, coordenadas, estacionamento, transporte |
| `WeddingEvent` | events | tipo (inclui lobolo e xiguiane), data/hora, família anfitriã, traje, regras de RSVP/QR |
| `ScheduleItem` | events | programa do dia, reordenável por drag-and-drop |
| `AuditLog` | audit | append-only, com diffs em JSON |

---

## Fluxo do assistente

1. **Noivos** — nomes, data, cidade e país (`/casamentos/novo/`)
2. **Eventos** — cerimónias, recepção, lobolo, xiguiane, eventos personalizados
3. **Locais** — endereço, mapa e instruções
4. **Programa** — itens com hora, reorganizáveis por drag-and-drop
5. **Aspecto** — template, cores, capa e música (templates completos na fase 4)
6. **Convidados** — fase 2
7. **Publicar** — validação da checklist e ativação das páginas públicas

O painel de cada casamento (`/casamentos/<uuid>/`) mostra o que já está feito e
o que falta.

---

## Configuração da base de dados

**Motor de produção confirmado: MariaDB 11.4.12** (verificado por SSH no
servidor cPanel a 29/07/2026). A base `<DB_NAME>` existe e está vazia.
Detalhes completos do ambiente em `DEPLOYMENT.md` §0.

O motor é escolhido por variável de ambiente, sem alterações no código:

```env
# MariaDB / MySQL (este servidor)
DB_ENGINE=django.db.backends.mysql
DB_PORT=3306

# PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_PORT=5432
```

Instale apenas o driver correspondente (`mysqlclient` ou `psycopg[binary]`) —
ambos estão comentados no `requirements.txt`.

> ⚠️ A base remota foi criada em `latin1`. **Antes do primeiro `migrate`** tem de
> ser convertida para `utf8mb4` (`DEPLOYMENT.md` §0.1), caso contrário nomes com
> acentos e emoji ficam corrompidos. Como a base está vazia, a conversão não
> afeta dados nenhuns.

**Desenvolvimento local usa sempre SQLite**, mesmo com o `.env` de produção
presente: `config/settings/development.py` ignora as credenciais remotas. Para
trabalhar contra a base remota através de um túnel SSH, defina
`DEV_DB_FROM_ENV=True`.

### Ficheiros de ambiente

| Ficheiro | Conteúdo | Versionado |
| -------- | -------- | ---------- |
| `.env` | valores reais (credenciais) | **Não** — no `.gitignore` |
| `.env.example` | estrutura documentada, sem valores | Sim |

---

## Segurança

Ver `SECURITY.md`. Em resumo: credenciais apenas em `.env`, hashing padrão do
Django, CSRF, cookies seguros em produção, validação de uploads (extensão,
tamanho e assinatura real do ficheiro), rate limiting nas páginas públicas,
tokens seguros, permissões por objeto e auditoria.

## Deploy

Ver `DEPLOYMENT.md` (cPanel + Passenger, sem acesso root e sem Docker).
