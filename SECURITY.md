# Segurança — MeuConvite

A plataforma trata dados pessoais de convidados (nome, telefone, email,
restrições alimentares, necessidades de transporte) e informação privada dos
noivos. Este documento descreve o que já está implementado, o que está previsto
para as fases seguintes e como reportar um problema.

---

## 1. Segredos e credenciais

- Nenhuma password, chave ou token existe no código ou nesta documentação.
- Tudo vem do ambiente através de `django-environ` (`.env` ou variáveis do cPanel).
- `.env` está no `.gitignore` e nunca é versionado; deve ser transferido apenas por um canal seguro.
- `config/settings/production.py` **recusa arrancar** sem `DJANGO_SECRET_KEY`
  forte e sem `DJANGO_ALLOWED_HOSTS`.
- Passwords nunca são escritas nos logs nem no registo de auditoria: o serviço
  de auditoria substitui por `***` qualquer campo cujo nome contenha
  `password`, `token`, `secret`, `api_key` ou semelhante, e mascara emails.

## 2. Autenticação

- Utilizador personalizado com **email como identificador** (sem username).
- Hashing padrão do Django (PBKDF2 com SHA-256).
- Validadores de password ativos, mínimo de 8 caracteres.
- **Verificação de email obrigatória** (`ACCOUNT_EMAIL_VERIFICATION="mandatory"`):
  sem email confirmado não há sessão iniciada.
- Recuperação de password por email, com proteção contra enumeração de contas
  (`ACCOUNT_PREVENT_ENUMERATION=True`): a resposta é igual para emails
  existentes e inexistentes.
- Rate limiting do django-allauth em login falhado, registo e recuperação de
  password (por IP e por conta).

## 3. Isolamento entre casamentos

É a propriedade mais crítica da plataforma e tem testes dedicados
(`weddings/tests/test_isolation.py`).

- Todas as views com âmbito de casamento usam `weddings.permissions.require_wedding()`,
  que obtém o casamento **exclusivamente** através de `Wedding.objects.for_user(user)`.
- Objetos filhos são sempre procurados com o casamento no filtro
  (`get_object_or_404(WeddingEvent, pk=..., wedding=wedding)`), pelo que
  combinar um id de outro casamento não dá acesso a nada.
- Os *querysets* dos formulários (locais, eventos) estão limitados ao casamento
  em causa — uma segunda camada, independente da view.
- A reordenação por drag-and-drop ignora silenciosamente ids que não pertençam
  ao casamento.
- Um casamento sem acesso responde **404**, nunca 403, para não confirmar que o
  registo existe.
- A equipa MeuConvite (`is_staff`) **não** recebe acesso implícito aos dados dos
  casamentos: o suporte passará por área administrativa própria, com auditoria
  (fase 4).

## 4. Permissões

`WeddingMember` guarda a função (proprietário, noivo/a, wedding planner,
comissão, recepção, consulta) **e** sete permissões individuais:
`can_manage_guests`, `can_manage_events`, `can_manage_seating`, `can_check_in`,
`can_view_reports`, `can_manage_design`, `can_manage_billing`.

A função define os valores iniciais; cada permissão pode ser ajustada depois.
Remover um membro **desativa** o acesso sem apagar o histórico do que fez.

## 5. Identificadores e ligações públicas

- Chave primária **UUID** em todos os modelos de domínio: nenhum id sequencial
  aparece em URLs.
- `Wedding.public_token` gerado com `secrets.token_urlsafe`.
- Os convites individuais (fase 2) usarão tokens seguros por convidado, com
  expiração e revogação; o QR Code (fase 3) transportará um token assinado, sem
  nome, telefone ou mesa em texto aberto.

## 6. Uploads

`core.validators.FileValidator` valida, no backend:

- **tamanho** (5 MB para imagens, 8 MB para áudio, 5 MB para Excel);
- **extensão** (`jpg`, `jpeg`, `png`, `webp` para imagens);
- **content type** declarado pelo navegador;
- **assinatura real do ficheiro** com Pillow (`Image.verify()`), pelo que um
  executável renomeado para `.jpg` é rejeitado.

Os caminhos de gravação derivam de UUIDs (`core/storage.py`), nunca do nome de
ficheiro enviado — não há travessia de diretórios.

## 7. Proteções web

| Proteção | Estado |
| -------- | ------ |
| CSRF em todos os formulários | Ativo (middleware + `{% csrf_token %}`) |
| Escape automático nos templates | Ativo (nenhum `\|safe` sobre conteúdo de utilizador) |
| `SECURE_CONTENT_TYPE_NOSNIFF` | Ativo |
| `X_FRAME_OPTIONS = DENY` | Ativo |
| `SECURE_REFERRER_POLICY = same-origin` | Ativo |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | Ativo em produção |
| HTTPS forçado + cookies `Secure` | Ativo em produção |
| HSTS | Configurável; ativar só depois de confirmar o HTTPS |
| Sessões `HttpOnly` + `SameSite=Lax` | Ativo |
| Rate limiting em páginas públicas | `core/ratelimit.py`, aplicado às páginas públicas à medida que são criadas |
| Validação no backend | Sempre, mesmo quando existe validação no navegador |

Ligações externas abrem com `rel="noopener noreferrer"`.

## 8. Auditoria

`audit.AuditLog` regista, sem nunca ser alterado ou apagado pela aplicação:
login, criação, alteração, eliminação, publicação, gestão de equipa e
alterações de permissões — e, nas fases seguintes, envio e revogação de
convites, confirmações, check-ins (incluindo autorizações especiais),
importações e exportações.

Cada registo guarda autor, casamento, objeto, diferenças em JSON, IP e agente.
No Django Admin o modelo é **só de leitura**.

## 9. Proteção de dados

- A plataforma trata dados pessoais de terceiros (convidados) fornecidos pelos
  noivos, que são os responsáveis pelo tratamento.
- Nada é eliminado por acidente: casamentos são **arquivados**, membros são
  **desativados**. Não existe eliminação em massa na interface.
- Política de privacidade, consentimento no formulário público de confirmação e
  procedimento de eliminação de dados a pedido: fase 4.
- Retenção e backups: ver `DEPLOYMENT.md` (secção 12).

## 10. O que ainda não está implementado

Assumido de forma explícita nesta fase:

- Autenticação em dois fatores para as contas dos noivos.
- Content Security Policy restritiva (o Bootstrap e o HTMX são carregados de CDN;
  na fase 5 passam a ser servidos localmente, o que permite uma CSP apertada).
- Área administrativa própria da plataforma com auditoria de suporte (fase 4).
- Verificação antivírus de uploads.

## 11. Reportar uma vulnerabilidade

Envie os detalhes para **seguranca@meuconvite.co.mz**, com passos de reprodução
e impacto. Pedimos que não divulgue publicamente antes de a correção estar
disponível. Resposta inicial em 72 horas úteis.
