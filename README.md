# MeuConvite

Plataforma SaaS de convites digitais para **qualquer tipo de evento** em
Moçambique (`meuconvite.co.mz`): casamentos, lobolo, aniversários, batismos,
formaturas, chá de bebé, eventos corporativos — cada tipo com os seus campos,
momentos e programa.

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

```bash
pip install -r requirements-dev.txt
```

Se ainda não existir um `.env` (não vem no repositório):

```bash
copy .env.example .env
```

> Se já tiver um `.env` com credenciais reais, **não execute o comando acima** —
> substituiria o ficheiro.

O desenvolvimento corre contra a **mesma base de dados de produção**, através de
um túnel SSH. Numa janela:

```bash
python scripts/dev_tunnel.py
```

E noutra:

```bash
python manage.py runserver
```

Os **testes nunca tocam nessa base**: correm sempre em SQLite em memória
(ver `config/settings/development.py`).

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
templates_manager/ catálogo dos templates visuais de convite
subscriptions/     planos, limites, pagamentos por M-Pesa
scripts/           túnel de desenvolvimento, deploy e backup
templates/         Django Templates (interface em português)
static/            CSS e JavaScript próprios
```

Aplicações previstas para as fases seguintes: `guests`, `invitations`, `rsvps`,
`seating`, `checkin`, `notifications`, `subscriptions`, `reports`.

### Tipos de evento

`events.EventCategory` descreve cada tipo de evento e é **gerido pela equipa
MeuConvite na administração** — acrescentar um tipo novo não exige código. Cada
tipo define:

- se há um ou dois protagonistas, e como se chamam (`Nome da noiva`/`Nome do
  noivo`, `Nome do aniversariante`, `Família anfitriã`…);
- os **campos próprios** pedidos ao criar o evento (`field_schema`, em JSON);
- os **momentos** e o **programa** criados automaticamente (`default_moments`,
  `default_schedule`), para o evento não nascer vazio;
- a frase usada no convite.

```bash
python manage.py seed_event_categories
```

Cria os oito tipos iniciais: casamento, lobolo, aniversário, batismo,
formatura, chá de bebé, evento corporativo e "outro evento".

### Campos definidos por dados

`core/schema.py` é o mecanismo comum a dois sítios onde os campos não são
conhecidos à partida: os campos próprios de cada tipo de evento e os campos que
o utilizador acrescenta ao **programa** do seu evento
(`Wedding.schedule_field_schema`). Valida o esquema, constrói os campos de
formulário (`extra__<chave>`) e recolhe os valores para JSON. Tipos suportados:
texto, texto longo, número, data, hora, ligação, lista de opções e sim/não.

### Subscrições e pagamentos

| Pacote | Convidados | Preço indicativo |
| ------ | ---------: | ---------------: |
| Gratuito | 20 | — |
| Essencial 50 | 50 | 750 MZN |
| Celebração 100 | 100 | 1 500 MZN |
| Premium 200 | 200 | 2 500 MZN |
| Grande Evento 500 | 500 | 4 500 MZN |

```bash
python manage.py seed_plans
```

> Os preços são um ponto de partida e devem ser confirmados na administração.
> `seed_plans` **não** altera preços de pacotes existentes sem `--update-prices`.

O circuito de pagamento é manual e propositadamente simples: o utilizador pede
o pacote, a plataforma gera uma referência (`MC-XXXXXX`), ele paga por **M-Pesa
para 840297715** e envia o comprovativo por **WhatsApp** (botão com a mensagem
já preenchida). A equipa confirma em *Administração → Pagamentos* e o pacote é
activado por `subscriptions.services.confirm_payment`.

`subscriptions.services.limits(wedding)` é o único ponto de verdade sobre
limites; `check_can_add_guests(wedding, n)` é o ponto único de verificação, que
a aplicação `guests` (fase 2) passará a chamar.

### Templates de convite

O catálogo está na base de dados (`templates_manager.InvitationTemplate`) e é
gerido em **Administração → Templates**. Cada template define layout, paleta,
tipografia, tipos de evento aplicáveis e um cover vertical em imagem. Na página
**Os meus eventos**, escolher um tipo troca imediatamente o carrossel de
templates; escolher um cartão abre o formulário de criação com o tipo e o
template já seleccionados. O ecrã **Aspecto** permite trocar o template depois,
sem perder os dados do evento. `templates_manager/registry.py` continua a ser o
ponto único de consulta e validação do catálogo.

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

> **Dívida técnica assumida:** o modelo do evento chama-se ainda `Wedding` em
> Python (e a aplicação `weddings/`), por a plataforma ter começado dedicada a
> casamentos. A interface já diz "evento" em todo o lado e os campos são
> genéricos (`primary_name`, `secondary_name`). O renomear das classes fica para
> um passo próprio, para não misturar uma mudança mecânica grande com trabalho
> funcional.

| Modelo | Aplicação | Notas |
| ------ | --------- | ----- |
| `User` | accounts | UUID, login por email, sem username |
| `EventCategory` | events | tipo de evento, com campos e momentos próprios |
| `Wedding` | weddings | o evento: slug + `public_token`, tipo, `extra_data`, estado, cores |
| `Plan` · `Subscription` · `Payment` | subscriptions | pacotes, limites e pagamentos M-Pesa |
| `WeddingMember` | weddings | função + 7 permissões individuais, único por (casamento, utilizador) |
| `WeddingLocation` | events | endereço, mapa, coordenadas, estacionamento, transporte |
| `WeddingEvent` | events | tipo (inclui lobolo e xiguiane), data/hora, família anfitriã, traje, regras de RSVP/QR |
| `ScheduleItem` | events | programa do dia, reordenável por drag-and-drop |
| `AuditLog` | audit | append-only, com diffs em JSON |

---

## Fluxo do assistente

1. **Noivos** — nomes e data (`/casamentos/novo/`); endereço e restantes detalhes são acrescentados depois
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

**Desenvolvimento e produção partilham a mesma base de dados.** Como o MariaDB
do cPanel só aceita ligações a partir do próprio servidor, o ambiente local
liga-se por um túnel SSH (`scripts/dev_tunnel.py`), que abre
`127.0.0.1:3307 → servidor 127.0.0.1:3306`. As variáveis `DEV_DB_HOST` e
`DEV_DB_PORT` do `.env` apontam para essa ponta local; no servidor são ignoradas.

> ⚠️ Trabalhar contra a base de produção significa que **qualquer alteração é
> imediatamente real**. Por isso: os testes correm sempre em SQLite em memória,
> o `runserver` avisa em cada arranque a que base está ligado, e nenhuma
> migração é executada pelo script de deploy — `migrate` é sempre um passo
> deliberado (`DEPLOYMENT.md` §14).

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

**Em produção desde 29/07/2026:** <https://meuconvite.co.mz/>
(cPanel + Passenger, Python 3.12.13, MariaDB 11.4.12 em utf8mb4).

Ver `DEPLOYMENT.md` — o §18 tem o registo do primeiro deploy e o que ficou
pendente; o §14 tem o procedimento de atualização.

> `manage.py` lê o `.env` **antes** de escolher o módulo de settings e imprime
> em `stderr` qual está a usar (`[meuconvite] settings: …`). No servidor o `.env`
> define `DJANGO_SETTINGS_MODULE=config.settings.production`; localmente essa
> linha está comentada, pelo que o ambiente local usa SQLite.
