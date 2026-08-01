# Deploy — MeuConvite

Alojamento partilhado **cPanel** com *Setup Python App* (Passenger).
Pressupostos: **sem acesso root**, **sem Docker**, domínio `meuconvite.co.mz`.

> Nenhum passo deste guia apaga dados. Onde existe risco, está assinalado
> explicitamente e indicado o backup a fazer antes.

---

## 0. Ambiente confirmado (29/07/2026)

Inspeção feita por SSH ao servidor, apenas com comandos de leitura:

| Item | Valor confirmado |
| ---- | ---------------- |
| Host | ver `.env` e gestor de passwords da equipa |
| Sistema | CloudLinux 8 (LVE) · LiteSpeed + **Passenger** |
| **Base de dados** | **MariaDB 11.4.12** (`/var/lib/mysql/mysql.sock`) |
| Base de dados da aplicação | `<DB_NAME>` — existe, **vazia** (0 tabelas) |
| Utilizador da base | `<DB_USER>` — `ALL PRIVILEGES` sobre essa base |
| ⚠️ Charset da base | **`latin1` / `latin1_swedish_ci`** — tem de ser convertido (§0.1) |
| Python disponível | 3.10.20 · 3.11.15 · **3.12.13** · 3.13.14 (via Setup Python App) |
| Python do sistema | 3.6.8 — **não usar** (Django 5.2 exige ≥ 3.10) |
| PostgreSQL | Cliente 10.23 instalado e a conta tem bases PostgreSQL de **outros** projetos. **Não é usado pelo MeuConvite.** |
| Redis | Não disponível → sem Celery; tarefas por cron |
| Domínio `meuconvite.co.mz` | **Ainda não existe na conta** (§9.0) |
| Domínios existentes | `digitalhorizon.co.mz` (principal), `labxpertsolutions.co.mz`, `salamainvestimentos.co.mz` |

> Os túneis SSH para a porta `5432` que constam das notas de acesso servem os
> projetos *clinicplus* e *ocapitao*, que usam PostgreSQL. O MeuConvite liga-se
> ao **MariaDB por socket local**, não precisa de túnel.

### 0.1 Converter a base de dados para utf8mb4 (obrigatório, antes do `migrate`)

A base foi criada em `latin1`. Nomes moçambicanos com acentos (Natércia,
Cossa, Nhantumbo), hashtags com emoji e mensagens dos convidados ficariam
corrompidos ou rejeitados. Como a base **está vazia**, a conversão é imediata e
não afeta dados nenhuns:

```bash
mysql -u <DB_USER> -p <DB_NAME> -e "ALTER DATABASE <DB_NAME> CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Confirmar:

```bash
mysql -u <DB_USER> -p <DB_NAME> -e "SELECT @@character_set_database, @@collation_database;"
```

Deve devolver `utf8mb4 / utf8mb4_unicode_ci`. **Só depois** executar o `migrate`
do passo 6 — as tabelas herdam o charset da base no momento em que são criadas.

> Se a base já tivesse tabelas com dados, a conversão exigiria backup prévio e
> `ALTER TABLE ... CONVERT TO CHARACTER SET utf8mb4`, tabela a tabela, com
> verificação de truncagem. Não é o caso aqui.

### 0.2 Como reconfirmar o motor no futuro

Métodos não destrutivos, caso o alojamento mude:

1. **cPanel → "MySQL® Databases"** existe no menu → o servidor oferece
   MySQL/MariaDB. Se existir **"PostgreSQL Databases"**, oferece PostgreSQL.
   Podem existir os dois.
2. **cPanel → phpMyAdmin** → a página inicial mostra
   `Servidor: Localhost via UNIX socket · Versão do servidor: 10.6.x-MariaDB`
   (ou `8.0.x MySQL`).
3. **Via SSH** (se disponível), sem escrever nada na base de dados:

   ```bash
   mysql --version
   ```

   ```bash
   psql --version
   ```

4. **A partir da própria aplicação**, depois de configurar o `.env`:

   ```bash
   python manage.py dbshell -c "SELECT VERSION();"
   ```

   ou, sem entrar na shell da base de dados:

   ```bash
   python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.get_connection_params().get('host'))"
   ```

| Cenário | `DB_ENGINE` | `DB_PORT` | Driver a instalar |
| ------- | ----------- | --------- | ----------------- |
| **MariaDB (este servidor)** | `django.db.backends.mysql` | `3306` | `mysqlclient>=2.2` |
| PostgreSQL | `django.db.backends.postgresql` | `5432` | `psycopg[binary]>=3.2` |

Se `mysqlclient` não compilar no servidor (falta de `mysql_config`), use a
alternativa pura em Python:

```bash
pip install pymysql
```

e acrescente no topo de `config/__init__.py`:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

---

## 1. Criar a aplicação Python no cPanel

**cPanel → Software → Setup Python App → Create Application**

| Campo | Valor |
| ----- | ----- |
| Python version | **3.12.13** (mesma versão do desenvolvimento; 3.13 também está disponível) |
| Application root | `meuconvite` |
| Application URL | `meuconvite.co.mz` (adicionar o domínio primeiro — §9.0) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

**Não** usar o Python do sistema (3.6.8): o Django 5.2 exige 3.10 ou superior.

Ao gravar, o cPanel cria o virtualenv e mostra o comando para o ativar:

```bash
source /home/<UTILIZADOR>/virtualenv/meuconvite/3.12/bin/activate && cd /home/<UTILIZADOR>/meuconvite
```

Guarde esse comando: é usado em todos os passos seguintes e nos cron jobs.

---

## 2. Enviar o código

Via Git (preferível):

```bash
git clone https://github.com/ORGANIZACAO/meuconvite.git /home/<UTILIZADOR>/meuconvite
```

Ou via **cPanel → File Manager**, carregando um `.zip` e extraindo em
`/home/<UTILIZADOR>/meuconvite`.

O `.gitignore` já exclui `.env`, `.venv/`, `db.sqlite3`, `media/`,
`staticfiles/`, `logs/` e backups. O `.env` é copiado à parte, por SFTP ou pelo
File Manager, **nunca** pelo repositório.

---

## 3. Instalar dependências

```bash
pip install -r requirements.txt
```

E o driver da base de dados confirmado no passo 0:

```bash
pip install mysqlclient
```

---

## 4. Base de dados

**Já existe e está pronta** (verificado a 29/07/2026):

- Base: `<DB_NAME>` (MariaDB 11.4.12), sem tabelas
- Utilizador: `<DB_USER>` com `ALL PRIVILEGES` sobre essa base
- Ligação por **socket local** (`DB_HOST=localhost`), sem exposição à Internet

Falta apenas a **conversão para utf8mb4** descrita em §0.1, antes do `migrate`.

Se for preciso criar outra base no futuro: **cPanel → MySQL® Databases** →
*Create New Database* → *Add New User* (password gerada pelo cPanel) → *Add User
To Database* → **ALL PRIVILEGES**.

As credenciais vivem apenas no `.env` (permissões `600`) e no gestor de
passwords da equipa. **Nunca** em ficheiros do repositório, em mensagens ou
nesta documentação.

---

## 5. Variáveis de ambiente

O ficheiro **`.env` já está preenchido** com os valores confirmados deste
servidor (motor, base, utilizador, host, caminhos e `SECRET_KEY` gerada). Falta
apenas preencher `EMAIL_HOST_PASSWORD` depois de criar a caixa de correio.

Duas formas de o disponibilizar no servidor, ambas suportadas:

**A. Ficheiro `.env`** na raiz da aplicação (mais simples). Envie-o por SFTP ou
File Manager — nunca por Git — e restrinja as permissões:

```bash
chmod 600 /home/<UTILIZADOR>/meuconvite/.env
```

**B. Interface do cPanel**: *Setup Python App → Environment variables*
(útil para segredos que não devem existir em ficheiro).

Gerar a `DJANGO_SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

A configuração e os valores reais estão no `.env` local do projeto ou nas
variáveis de ambiente do alojamento. `config/settings/production.py` **recusa arrancar**
sem `DJANGO_SECRET_KEY` forte e sem `DJANGO_ALLOWED_HOSTS` — é intencional.

Nota sobre desenvolvimento: o mesmo `.env` fica no projeto local sem risco,
porque `config/settings/development.py` força SQLite, `DEBUG=True` e
`localhost`, ignorando as credenciais de produção. Para trabalhar contra a base
remota através de um túnel SSH, defina `DEV_DB_FROM_ENV=True`.

---

## 6. Migrations

> **Pré-requisito:** a conversão para utf8mb4 da §0.1 tem de estar feita. As
> tabelas herdam o charset da base no momento em que são criadas.

Verificar primeiro o que vai ser aplicado:

```bash
python manage.py showmigrations
```

```bash
python manage.py migrate
```

`migrate` cria e altera tabelas. Numa base de dados já em produção, **faça
backup antes** (passo 12) e leia a secção *Atualizações*.

---

## 7. Ficheiros estáticos

```bash
python manage.py collectstatic --noinput
```

Duas configurações possíveis:

- **WhiteNoise** (`USE_WHITENOISE=True`, predefinição): a própria aplicação
  serve `/static/`. Não é preciso configurar mais nada.
- **Servidor web**: `USE_WHITENOISE=False` e criar em
  `~/public_html/.htaccess` um alias para `staticfiles/`. Mais rápido, exige
  que o `STATIC_ROOT` esteja dentro de uma pasta servida pelo Apache/LiteSpeed.

---

## 8. Ficheiros de media (uploads)

```bash
mkdir -p /home/UTILIZADOR/meuconvite/media
```

```bash
chmod 755 /home/UTILIZADOR/meuconvite/media
```

Os uploads (capas, fotografias, música) são gravados aqui. **Não** devem ficar
dentro de `public_html` sem regras de acesso: fotografias de convidados são
dados pessoais. Servir através da aplicação ou de um alias dedicado.

O `STORAGES["default"]` está isolado em `config/settings/base.py` — a migração
futura para S3/Azure Blob altera apenas essa entrada.

---

## 9. Domínio e HTTPS

### 9.0 O domínio ainda não existe nesta conta

A conta tem `digitalhorizon.co.mz` (principal), `labxpertsolutions.co.mz` e
`salamainvestimentos.co.mz`. **`meuconvite.co.mz` não está configurado.** Antes
de tudo o resto:

1. Registar o domínio `meuconvite.co.mz` (registrar `.co.mz`, se ainda não estiver).
2. Apontar os *nameservers* (ou um registo A) para **`<IP_DO_SERVIDOR>`**.
3. **cPanel → Domains → Create A New Domain**: `meuconvite.co.mz`, com document
   root próprio (por exemplo `/home/<UTILIZADOR>/meuconvite.co.mz`).
4. Esperar a propagação de DNS antes de emitir o certificado SSL.

Enquanto o domínio não estiver pronto, é possível testar num subdomínio da conta
(por exemplo `mc.digitalhorizon.co.mz`), acrescentando-o a
`DJANGO_ALLOWED_HOSTS` e a `DJANGO_CSRF_TRUSTED_ORIGINS`.

### 9.1 Configuração

1. **cPanel → Domains**: apontar `meuconvite.co.mz` para a pasta da aplicação.
2. **cPanel → SSL/TLS Status**: emitir certificado *Let's Encrypt* para o
   domínio e para `www`.
3. **Force HTTPS Redirect** ativado.
4. Só depois de confirmar que o HTTPS funciona, ativar HSTS:

   ```env
   SECURE_HSTS_SECONDS=2592000
   SECURE_HSTS_INCLUDE_SUBDOMAINS=True
   ```

   Comece com 30 dias. HSTS não é reversível de imediato para quem já visitou o
   site — só aumente para um ano quando tudo estiver estável.

---

## 10. Superutilizador

```bash
python manage.py createsuperuser
```

A password é pedida interativamente e nunca aparece nos logs. O acesso à
administração fica em `/django-admin/` (alterável com `DJANGO_ADMIN_URL`).

---

## 11. Cron jobs

**cPanel → Advanced → Cron Jobs.** Não existe Celery neste alojamento: as
tarefas periódicas correm por cron, com comandos Django e filas em base de
dados (fases 3 e 4).

Sessões expiradas — semanalmente:

```bash
source /home/UTILIZADOR/virtualenv/meuconvite/3.12/bin/activate && cd /home/UTILIZADOR/meuconvite && python manage.py clearsessions >> logs/cron.log 2>&1
```

Backup da base de dados — diariamente às 02h00 (ver passo 12).

Fila de emails e lembretes (fase 4):

```bash
source /home/UTILIZADOR/virtualenv/meuconvite/3.12/bin/activate && cd /home/UTILIZADOR/meuconvite && python manage.py send_pending_notifications >> logs/cron.log 2>&1
```

---

## 12. Backups

**Base de dados**, diariamente:

```bash
mysqldump -u UTILIZADOR_mc -p"$DB_PASSWORD" UTILIZADOR_meuconvite | gzip > /home/UTILIZADOR/backups/meuconvite_$(date +\%F).sql.gz
```

Coloque a password numa variável de ambiente do cron (`DB_PASSWORD`), nunca
diretamente na linha do comando — no `ps` ela ficaria visível.

**Media**, semanalmente:

```bash
tar czf /home/UTILIZADOR/backups/media_$(date +\%F).tar.gz -C /home/UTILIZADOR/meuconvite media
```

Retenção sugerida: 14 cópias diárias + 8 semanais, guardadas também fora do
servidor. **Teste o restauro pelo menos uma vez por trimestre** — um backup
nunca testado não é um backup.

---

## 13. Logs

- Aplicação: `logs/meuconvite.log` (rotativo, 5 MB × 5)
- Erros Passenger: `~/logs/` ou *cPanel → Errors*
- Auditoria funcional: tabela `audit_auditlog` (nunca é apagada pela aplicação)

Os logs não registam passwords, tokens nem emails completos.

---

## 14. Procedimento de atualização

```bash
python manage.py check --deploy
```

1. Backup da base de dados **e** do `media/` (passo 12).
2. `git pull` (ou upload dos ficheiros).
3. `pip install -r requirements.txt`
4. `python manage.py showmigrations` — reveja as migrations pendentes.
5. `python manage.py migrate`
6. `python manage.py collectstatic --noinput`
7. Reiniciar a aplicação: *Setup Python App → Restart*, ou

   ```bash
   touch tmp/restart.txt
   ```

8. Verificar `https://meuconvite.co.mz/estado/` (deve responder `{"status": "ok"}`).

**Antes de qualquer migration destrutiva** (remoção de campo ou tabela), o
impacto tem de ser descrito e aprovado. Migrations que apagam dados não são
aplicadas em produção sem backup verificado imediatamente antes.

---

## 15. Rollback

1. Voltar à versão anterior do código:

   ```bash
   git checkout <tag-ou-commit-anterior>
   ```

2. Se a atualização incluiu migrations **reversíveis**:

   ```bash
   python manage.py migrate <app> <numero_da_migration_anterior>
   ```

3. Se incluiu migrations **irreversíveis** ou destrutivas: restaurar o backup

   ```bash
   gunzip < /home/UTILIZADOR/backups/meuconvite_AAAA-MM-DD.sql.gz | mysql -u UTILIZADOR_mc -p UTILIZADOR_meuconvite
   ```

   Este comando **substitui** o conteúdo atual da base de dados. Só deve ser
   executado com o site em manutenção e depois de confirmar a data do ficheiro.
4. `collectstatic` + restart.

---

## 16. Checklist de produção

- [ ] `DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` única, nunca em repositório
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` preenchidos
- [ ] HTTPS ativo, redireccionamento forçado, cookies `Secure`
- [ ] `python manage.py check --deploy` sem avisos críticos
- [ ] Base de dados criada, com utilizador dedicado e password forte
- [ ] `migrate` aplicado; `showmigrations` sem pendentes
- [ ] `collectstatic` executado
- [ ] `media/` fora do acesso público direto
- [ ] Email de saída testado (registo + recuperação de password)
- [ ] Superutilizador criado
- [ ] Cron de sessões e de backup ativos
- [ ] Backup testado com restauro real
- [ ] `/estado/` responde `ok`
- [ ] Logs a escrever e a rodar
- [ ] `.env` com permissões `600`

---

## 17. Registo do ambiente

| Item | Valor confirmado | Data |
| ---- | ---------------- | ---- |
| Motor da base de dados | **MariaDB** (MySQL protocol) | 29/07/2026 |
| Versão do motor | 11.4.12-MariaDB-cll-lve | 29/07/2026 |
| Base de dados | `<DB_NAME>` (vazia, charset a converter) | 29/07/2026 |
| Ligação | socket local `/var/lib/mysql/mysql.sock`, `DB_HOST=localhost` | 29/07/2026 |
| Versão do Python a usar | 3.12.13 (`/opt/alt/python312`) | 29/07/2026 |
| Servidor de aplicação | LiteSpeed + Passenger (`passenger_active: true`) | 29/07/2026 |
| Caminho do virtualenv | `/home/<UTILIZADOR>/virtualenv/meuconvite/3.12/` (a criar) | — |
| Redis disponível | **Não** | 29/07/2026 |
| Processos persistentes (Celery) | **Não** — usar cron + comandos Django | 29/07/2026 |
| Domínio `meuconvite.co.mz` | **Por configurar** (§9.0) | 29/07/2026 |
| SSH | `<HOST_CPANEL>`, porta e utilizador conforme o `.env` / gestor de passwords | 29/07/2026 |

---

## 18. Registo do primeiro deploy (29/07/2026)

Executado por SSH. Estado final: **aplicação em produção e a responder em
`https://meuconvite.co.mz/`**.

| Passo | Resultado |
| ----- | --------- |
| Base convertida para utf8mb4 | ✅ `utf8mb4 / utf8mb4_unicode_ci` (base estava vazia) |
| Aplicação Python criada | ✅ Python 3.12.13, Passenger, `app-root=meuconvite`, URI `/` |
| Código enviado | ✅ 121 ficheiros por SFTP (lista vinda de `git ls-files`) |
| `.env` | ✅ enviado com `chmod 600`, com `DJANGO_SETTINGS_MODULE` de produção activo |
| Dependências | ✅ `requirements.txt` + `mysqlclient 2.2.8` (compilou sem problemas) |
| Migrations | ✅ 19 tabelas criadas no MariaDB, todas em `utf8mb4_unicode_ci` |
| Ficheiros estáticos | ✅ 132 ficheiros, 396 pós-processados, manifesto WhiteNoise criado |
| `check --deploy` | ✅ apenas o aviso de HSTS (desactivado por decisão, §9.1) |
| HTTPS | ✅ certificado válido; `http` responde 301 para `https` |
| Email | ✅ exim local (`localhost:25`), sem credenciais para gerir |
| Superutilizador | ✅ criado com password aleatória descartada — definir pela recuperação de password |
| Cron de backup | ✅ diário às 02h30, retenção de 14 dias, primeiro backup validado |
| Cron de sessões | ✅ `clearsessions` aos domingos às 04h00 |

Verificação final das páginas:

| Página | Código |
| ------ | ------ |
| `/` | 200 |
| `/accounts/login/` · `/accounts/signup/` · `/accounts/password/reset/` | 200 |
| `/estado/` | 200 (`{"status": "ok"}`) |
| `/casamentos/` (privada) | 302 para login |
| `/painel-meuconvite/` (admin) | 302 para login |
| `/nao-existe/` | 404 |
| `/static/css/app.<hash>.css` | 200 |

Cabeçalhos confirmados: `x-frame-options: DENY`,
`x-content-type-options: nosniff`, `referrer-policy: same-origin`.

### Armadilha encontrada (e resolvida)

O `manage.py` assumia `config.settings.development`, pelo que o primeiro
`migrate` no servidor criou um `db.sqlite3` em vez de escrever no MariaDB. O
`manage.py` passou a **ler o `.env` antes de escolher o módulo de settings** e a
imprimir em `stderr` qual o módulo em uso:

```text
[meuconvite] settings: config.settings.production
```

O `db.sqlite3` acidental (apenas tabelas vazias) foi movido para
`~/backups/db.sqlite3.acidental-deploy` em vez de eliminado.

### Pendente

1. **Deliverability do email** — confirmar SPF/DKIM em *cPanel → Email
   Deliverability* para `meuconvite.co.mz`. Sem DKIM, os emails de verificação
   podem cair no spam.
2. **HSTS** — activar `SECURE_HSTS_SECONDS=2592000` depois de alguns dias
   estáveis em HTTPS (§9.1).
3. **Caixa `nao-responder@meuconvite.co.mz`** — opcional; o envio já funciona,
   mas respostas dos convidados a esse endereço não têm destino.
4. **Password do superutilizador** — definir através de "Esqueceu-se da
   palavra-passe?" ou por SSH com `manage.py changepassword`.
