"""
Textos do convite que os anfitriões podem personalizar.

Um só registo com *todas* as frases que o convidado vê no convite (títulos
de secção, botões, rótulos, mensagens de confirmação…). Cada entrada define
o texto original — que pode variar por categoria de evento ou por layout —,
onde aparece, o limite de caracteres e os marcadores ``{…}`` aceites.

Os valores personalizados ficam em ``Wedding.invitation_texts`` (um único
JSONField: ``{chave: texto}``). Em branco = texto original. As mensagens
com campo próprio (``cover_message`` e ``invitation_message``) continuam
nesses campos (``model_field``), mas os seus textos de recurso também vivem
aqui, para que os layouts não repitam frases soltas. ``welcome_message``
não tem texto de recurso: em branco, a secção simplesmente não aparece.

Nos templates:

    {% load invitation_texts %}
    {% invtext "gallery_title" %}
    {% invtext "rsvp_deadline_text" data=wedding.rsvp_deadline|date:"d/m/Y" %}
    {% invtext "open_button" as open_label %}

Nas views (texto simples, sem HTML):

    InvitationTexts(wedding).plain("gift_selected_toast", presente=gift.name)

Segurança: o texto é sempre escapado; os marcadores são substituídos por
valores também escapados. Nenhum HTML escrito pelos anfitriões chega ao
convidado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

TOKEN_RE = re.compile(r"\{([a-z_]+)\}")

# Marcadores disponíveis em qualquer texto.
GLOBAL_TOKENS: dict[str, str] = {
    "nomes": "nomes do evento (ex.: Ivone & Dário)",
    "nomes_completos": "nomes completos",
    "categoria": "tipo de evento (ex.: Casamento)",
    "frase_convite": "frase padrão do tipo de evento",
    "convidado": "nome do convidado",
}

TOKEN_HELP: dict[str, str] = {
    **GLOBAL_TOKENS,
    "data": "data limite de confirmação",
    "hora": "hora de início",
    "total": "número",
    "presente": "nome do presente",
    "organizacao": "organização anfitriã",
    "pais": "nomes dos pais",
}

CORPORATE = "evento-corporativo"

# Layouts com a estrutura clássica (ornamentos, lugares, mesa…).
CLASSIC_LAYOUTS = frozenset({
    "carta_selada", "cartao_classico", "envelope_botanico", "noivado_elegante",
})


@dataclass(frozen=True)
class TextGroup:
    code: str
    label: str
    description: str
    icon: str


@dataclass(frozen=True)
class TextKey:
    key: str
    group: str
    label: str
    # Texto original. Um ``dict`` permite variar por categoria/layout:
    # {"cat:evento-corporativo": "…", "layout:corporativo": "…", "*": "…"}.
    # Ordem de procura: categoria → layout → "*".
    default: str | dict
    max_length: int = 80
    help: str = ""
    tokens: tuple[str, ...] = ()
    # Marcadores apresentados em destaque (<strong>) quando substituídos.
    emphasis: tuple[str, ...] = ()
    multiline: bool = False
    # Onde a frase aparece. ``None`` = todos os layouts / categorias.
    layouts: frozenset | None = None
    exclude_layouts: frozenset = frozenset()
    categories: frozenset | None = None
    exclude_categories: frozenset = frozenset()
    # Frases guardadas num campo próprio do modelo (não no JSON).
    model_field: str = ""

    def applies_to(self, *, layout: str = "", category: str = "") -> bool:
        if layout:
            if self.layouts is not None and layout not in self.layouts:
                return False
            if layout in self.exclude_layouts:
                return False
        if category:
            if self.categories is not None and category not in self.categories:
                return False
            if category in self.exclude_categories:
                return False
        return True

    def default_for(self, *, layout: str = "", category: str = "") -> str:
        if isinstance(self.default, str):
            return self.default
        for selector in (f"cat:{category}", f"layout:{layout}", "*"):
            if selector in self.default:
                return self.default[selector]
        return ""

    @property
    def allowed_tokens(self) -> set[str]:
        return set(GLOBAL_TOKENS) | set(self.tokens)


GROUPS: tuple[TextGroup, ...] = (
    TextGroup("abertura", "Capa e abertura", "Antes de abrir o convite: animação, capa, botão e música.", "bi-envelope-open-heart"),
    TextGroup("convite", "Convite", "Saudação, frases principais e lugares reservados.", "bi-card-heading"),
    TextGroup("contagem", "Contagem regressiva", "Unidades por baixo dos números.", "bi-hourglass-split"),
    TextGroup("sobre", "Sobre o evento", "Secções institucionais e ligações dos detalhes.", "bi-info-circle"),
    TextGroup("historia", "A nossa história", "Secção da história, versículo ou mensagem.", "bi-book"),
    TextGroup("galeria", "Galeria", "Apresentação das fotografias.", "bi-images"),
    TextGroup("programa", "Programa", "Momentos, horários e mapas.", "bi-list-ol"),
    TextGroup("rsvp", "Confirmação de presença", "Botão, janela e respostas de confirmação.", "bi-calendar-check"),
    TextGroup("presentes", "Presentes", "Lista de presentes para o convidado escolher.", "bi-gift"),
    TextGroup("qr", "QR Code e entrada", "Credencial pessoal apresentada à entrada.", "bi-qr-code"),
    TextGroup("partilha", "Partilha da ligação", "Título e descrição mostrados quando a ligação é partilhada.", "bi-share"),
)
GROUPS_BY_CODE = {group.code: group for group in GROUPS}


_KEYS: tuple[TextKey, ...] = (
    # --- Capa e abertura ---------------------------------------------
    TextKey(
        "cover_message", "abertura", "Mensagem da capa",
        {
            "layout:carta_selada": "Uma celebração para recordar",
            "layout:cartao_classico": "Temos o prazer de convidar",
            "layout:envelope_botanico": "Junte-se a nós neste dia especial",
            "layout:noivado_elegante": "Uma promessa para toda a vida",
            "layout:evento_tematico": "Um momento especial para partilhar.",
            "layout:corporativo": "Ideias, pessoas e oportunidades no mesmo lugar.",
            "*": "Uma celebração para recordar",
        },
        max_length=200, model_field="cover_message",
    ),
    TextKey(
        "intro_eyebrow", "abertura", "Frase da animação de abertura",
        {"layout:carta_selada": "Um convite selado para si", "*": "Um convite especial para si"},
        layouts=frozenset({"carta_selada", "cartao_classico"}),
    ),
    TextKey(
        "intro_to_guest", "abertura", "Destinatário no envelope",
        "Para {convidado}", tokens=("convidado",),
        layouts=frozenset({"carta_selada", "cartao_classico"}),
    ),
    TextKey(
        "intro_no_guest", "abertura", "Envelope sem nome do convidado",
        {"layout:carta_selada": "Temos algo especial para si", "*": "É com alegria que convidamos"},
        layouts=frozenset({"carta_selada", "cartao_classico"}),
        help="Aparece quando o convite não tem um convidado identificado.",
    ),
    TextKey(
        "intro_status", "abertura", "Texto enquanto o convite abre",
        {"layout:carta_selada": "A romper o lacre…", "*": "A abrir o seu convite…"},
        layouts=frozenset({"carta_selada", "cartao_classico"}),
    ),
    TextKey(
        "cover_eyebrow", "abertura", "Etiqueta da capa",
        "{categoria}", max_length=60,
        layouts=frozenset({"carta_selada", "cartao_classico", "envelope_botanico", "evento_tematico"}),
    ),
    TextKey("cover_to_label", "abertura", "Antes do nome do convidado", "Para", max_length=40,
            layouts=frozenset({"carta_selada"})),
    TextKey("cover_from_label", "abertura", "Capa sem convidado identificado", "Convite de", max_length=40,
            layouts=frozenset({"carta_selada"})),
    TextKey(
        "corporate_cover_kicker", "abertura", "Etiqueta da capa (sem organização)",
        "Convite corporativo", max_length=60, layouts=frozenset({"corporativo"}),
        help="Usada quando a organização anfitriã não está preenchida.",
    ),
    TextKey(
        "open_button", "abertura", "Botão para abrir",
        {"layout:corporativo": "Abrir convite", "layout:evento_tematico": "Abrir convite", "*": "Abrir o convite"},
        max_length=40,
    ),
    TextKey("music_play", "abertura", "Botão da música (parada)", "Ouvir", max_length=20,
            exclude_categories=frozenset({CORPORATE})),
    TextKey("music_pause", "abertura", "Botão da música (a tocar)", "Pausar", max_length=20,
            exclude_categories=frozenset({CORPORATE})),

    # --- Convite -------------------------------------------------------
    TextKey("hero_eyebrow", "convite", "Etiqueta por cima dos nomes", "{categoria}", max_length=60,
            help="No layout corporativo, só aparece quando o formato do evento não está preenchido."),
    TextKey("greeting", "convite", "Saudação ao convidado", "Caro(a) {convidado},",
            tokens=("convidado",)),
    TextKey(
        "parents_sentence", "convite", "Frase dos pais anfitriões",
        "{pais} convidam para o casamento dos seus filhos.", max_length=200,
        tokens=("pais",), categories=frozenset({"casamento"}),
        layouts=frozenset({"carta_selada", "cartao_classico", "envelope_botanico"}),
        help="Aparece quando os pais de ambos apresentam o convite.",
    ),
    TextKey(
        "invitation_message", "convite", "Mensagem principal do convite",
        {
            "layout:evento_tematico": "{frase_convite}",
            "layout:corporativo": "Temos o prazer de o convidar para este encontro profissional.",
            "*": "{nomes_completos} {frase_convite}",
        },
        max_length=1000, multiline=True, model_field="invitation_message",
    ),
    TextKey(
        "corporate_host", "convite", "Organização anfitriã",
        "Uma iniciativa de {organizacao}", tokens=("organizacao",), emphasis=("organizacao",),
        layouts=frozenset({"corporativo"}),
    ),
    TextKey("start_time", "convite", "Hora de início", "Início: {hora}", max_length=40,
            tokens=("hora",), layouts=frozenset({"carta_selada"})),
    TextKey("seats_label", "convite", "Lugares reservados", "Lugares reservados", max_length=40,
            exclude_layouts=frozenset({"corporativo"})),
    TextKey("seating_label", "convite", "Mesa atribuída", "Mesa / cadeira", max_length=40,
            layouts=CLASSIC_LAYOUTS),

    # --- Contagem regressiva ------------------------------------------
    TextKey("countdown_days", "contagem", "Dias", "dias", max_length=15),
    TextKey("countdown_hours", "contagem", "Horas", "horas", max_length=15),
    TextKey("countdown_minutes", "contagem", "Minutos", "min", max_length=15),
    TextKey("countdown_seconds", "contagem", "Segundos", "seg", max_length=15),

    # --- Sobre o evento -----------------------------------------------
    TextKey("facts_link", "sobre", "Ligação nos detalhes",
            {"layout:corporativo": "Aceder à ligação", "*": "Abrir ligação"}, max_length=40,
            layouts=frozenset({"corporativo", "evento_tematico"})),
    TextKey("about_eyebrow", "sobre", "Etiqueta da secção do tema", "Sobre o evento", max_length=60,
            layouts=frozenset({"corporativo"})),
    TextKey("about_title", "sobre", "Título da secção do tema", "O encontro",
            layouts=frozenset({"corporativo"})),
    TextKey("partners_eyebrow", "sobre", "Etiqueta dos parceiros", "Parceiros", max_length=60,
            layouts=frozenset({"corporativo"})),
    TextKey("partners_title", "sobre", "Título dos parceiros", "Organizações participantes",
            layouts=frozenset({"corporativo"})),

    # --- A nossa história ---------------------------------------------
    TextKey("story_kicker", "historia", "Etiqueta por cima do título", "Um capítulo especial",
            max_length=60, exclude_layouts=frozenset({"corporativo"})),

    # --- Galeria ------------------------------------------------------
    TextKey("gallery_eyebrow", "galeria", "Etiqueta da galeria",
            {"cat:evento-corporativo": "O evento em imagens", "*": "A nossa história em imagens"}),
    TextKey("gallery_title", "galeria", "Título da galeria",
            {"cat:evento-corporativo": "Galeria", "*": "Memórias de nós"}),
    TextKey("gallery_intro_one", "galeria", "Texto com uma fotografia",
            "1 momento escolhido para partilhar consigo.", max_length=160),
    TextKey("gallery_intro", "galeria", "Texto com várias fotografias",
            "{total} momentos escolhidos para partilhar consigo.", max_length=160,
            tokens=("total",)),
    TextKey("gallery_button", "galeria", "Botão da galeria",
            {"cat:evento-corporativo": "Ver a galeria", "*": "Ver a nossa galeria"}, max_length=40),
    TextKey("gallery_overlay_label", "galeria", "Título da galeria aberta",
            {"cat:evento-corporativo": "Galeria", "*": "A nossa galeria"}, max_length=60),

    # --- Programa -----------------------------------------------------
    TextKey("schedule_title", "programa", "Título do programa", "Programa"),
    TextKey("map_toggle", "programa", "Botão do mapa", "Mapa", max_length=30),
    TextKey("map_open", "programa", "Ligação para o mapa", "Abrir no Google Maps", max_length=40),
    # O partial _venues.html não é usado pelos layouts actuais: um layout novo
    # que o inclua acrescenta-se aqui para a frase aparecer no editor.
    TextKey("venues_title", "programa", "Título dos locais", "Onde será",
            layouts=frozenset()),

    # --- Confirmação de presença --------------------------------------
    TextKey("rsvp_button", "rsvp", "Botão flutuante", "Confirmar presença", max_length=40),
    TextKey("rsvp_confirmed", "rsvp", "Presença já confirmada", "Presença confirmada", max_length=40),
    TextKey("rsvp_title", "rsvp", "Título da janela", "Confirmação de presença"),
    TextKey("rsvp_deadline_text", "rsvp", "Pedido com prazo",
            "Pedimos a gentileza de responder até {data}.", max_length=200,
            tokens=("data",), emphasis=("data",),
            help="Usado quando existe prazo de confirmação."),
    TextKey("rsvp_no_deadline_text", "rsvp", "Pedido sem prazo",
            "Será uma alegria celebrar consigo. Pode confirmar agora?", max_length=200),
    TextKey("rsvp_yes", "rsvp", "Botão «vou»", "Sim, vou estar presente", max_length=50),
    TextKey("rsvp_no", "rsvp", "Botão «não vou»", "Não poderei comparecer", max_length=50),
    TextKey("rsvp_declined_state", "rsvp", "Resposta negativa registada",
            "Indicou que não poderá comparecer", max_length=120),
    TextKey("rsvp_thanks_toast", "rsvp", "Aviso depois de responder",
            "A sua resposta foi registada. Obrigado!", max_length=160),

    # --- Presentes ----------------------------------------------------
    TextKey("gift_button", "presentes", "Botão flutuante", "Selecionar presente", max_length=40),
    TextKey("gift_title", "presentes", "Título da janela", "Escolha um presente"),
    TextKey("gift_intro", "presentes", "Texto da janela",
            "A sua escolha fica reservada e os anfitriões saberão com o que podem contar.",
            max_length=240),
    TextKey("gift_multiple_badge", "presentes", "Presente para várias pessoas", "Várias pessoas", max_length=30),
    TextKey("gift_choose", "presentes", "Botão para escolher", "Vou oferecer", max_length=30),
    TextKey("gift_own", "presentes", "Presente escolhido pelo convidado", "Eu levo · retirar", max_length=40),
    TextKey("gift_taken", "presentes", "Presente já escolhido", "Já escolhido", max_length=30),
    TextKey("gift_selected_toast", "presentes", "Aviso ao escolher",
            "Obrigado! Ficou registado que vai levar “{presente}”.", max_length=160,
            tokens=("presente",)),
    TextKey("gift_removed_toast", "presentes", "Aviso ao retirar",
            "Deixou de levar “{presente}”.", max_length=160, tokens=("presente",)),
    TextKey("gift_unavailable_toast", "presentes", "Aviso de presente indisponível",
            "Este presente já foi escolhido por outro convidado.", max_length=160),

    # --- QR Code ------------------------------------------------------
    TextKey("qr_eyebrow", "qr", "Etiqueta", "Entrada digital", max_length=60),
    TextKey("qr_title", "qr", "Título", "O seu QR Code"),
    TextKey("qr_guest_fallback", "qr", "Nome sem convidado identificado", "Convidado", max_length=40),
    TextKey("qr_seat_one", "qr", "Um lugar", "{total} lugar", max_length=30, tokens=("total",)),
    TextKey("qr_seats", "qr", "Vários lugares", "{total} lugares", max_length=30, tokens=("total",)),
    TextKey("qr_instructions", "qr", "Instruções",
            "Apresente este código à entrada. É pessoal e identifica os seus lugares reservados.",
            max_length=240),

    # --- Partilha da ligação ------------------------------------------
    TextKey("page_title", "partilha", "Título do separador", "{nomes} · Convite"),
    TextKey("share_title", "partilha", "Título na pré-visualização",
            "Um convite especial de {nomes}", max_length=100),
    TextKey("share_description", "partilha", "Descrição na pré-visualização",
            "Abra o seu convite personalizado e confirme a sua presença.", max_length=160),
    TextKey("share_image_to_guest", "partilha", "Destinatário na imagem",
            "Para {convidado}", max_length=40, tokens=("convidado",),
            help="Aparece em maiúsculas na imagem partilhada."),
    TextKey("share_image_callout", "partilha", "Chamada na imagem",
            "Abra o convite e confirme a sua presença", max_length=60,
            help="Aparece em maiúsculas na imagem partilhada."),
)

REGISTRY: dict[str, TextKey] = {entry.key: entry for entry in _KEYS}
assert len(REGISTRY) == len(_KEYS), "Chaves de texto duplicadas"
assert all(entry.group in GROUPS_BY_CODE for entry in _KEYS)
# Guardadas no JSON (as restantes vivem em campos próprios do modelo).
STORED_KEYS = frozenset(key for key, entry in REGISTRY.items() if not entry.model_field)


def keys_for(*, layout: str = "", category: str = "", include_model_fields: bool = False) -> list[TextKey]:
    """Chaves relevantes para um layout/categoria, pela ordem do registo."""
    return [
        entry for entry in _KEYS
        if entry.applies_to(layout=layout, category=category)
        and (include_model_fields or not entry.model_field)
    ]


def clean_value(entry: TextKey, value) -> str:
    """Normaliza um texto guardado: string, sem espaços a mais, no limite."""
    if not isinstance(value, str):
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not entry.multiline:
        value = " ".join(value.split())
    return value[: entry.max_length]


def sanitise_stored(data) -> dict[str, str]:
    """Só chaves conhecidas, só texto, nunca vazio."""
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for key, value in data.items():
        entry = REGISTRY.get(key)
        if entry is None or entry.model_field:
            continue
        text = clean_value(entry, value)
        if text:
            cleaned[key] = text
    return cleaned


def unknown_tokens(entry: TextKey, value: str) -> set[str]:
    return set(TOKEN_RE.findall(value or "")) - entry.allowed_tokens


def _substitute(text: str, values: dict[str, str], *, html: bool, emphasis=(), multiline=False) -> str:
    """Troca só os marcadores conhecidos; o resto do texto fica tal como está."""
    output = []
    position = 0
    for match in TOKEN_RE.finditer(text):
        name = match.group(1)
        if name not in values:
            continue
        literal = text[position:match.start()]
        output.append(escape(literal) if html else literal)
        value = "" if values[name] is None else str(values[name])
        if html:
            value = escape(value)
            if name in emphasis and value:
                value = f"<strong>{value}</strong>"
        output.append(value)
        position = match.end()
    tail = text[position:]
    output.append(escape(tail) if html else tail)
    result = "".join(output)
    if html and multiline:
        result = result.replace("\n", "<br>")
    return result


class InvitationTexts:
    """
    Textos resolvidos de um convite concreto (evento + layout + convidado).

    ``texts.render(chave, **valores)`` devolve HTML seguro;
    ``texts.plain(chave, **valores)`` devolve texto simples (para mensagens
    flash, imagem de partilha…). ``texts["chave"]`` equivale a ``render``
    sem valores adicionais, para uso directo em templates.
    """

    def __init__(self, wedding, layout: str = "", *, guest_name: str = "") -> None:
        self.wedding = wedding
        self.layout = layout or ""
        category = getattr(wedding, "category", None) if getattr(wedding, "category_id", None) else None
        self.category = category.code if category is not None else ""
        self.custom = sanitise_stored(getattr(wedding, "invitation_texts", None))
        self.values = {
            "nomes": wedding.display_names,
            "nomes_completos": wedding.full_names,
            "categoria": str(wedding.category_name),
            "frase_convite": (
                category.invitation_greeting if category is not None else "convida-o para"
            ),
            "convidado": guest_name or "",
        }

    # --- Resolução -----------------------------------------------------
    def default(self, key: str) -> str:
        entry = REGISTRY[key]
        return entry.default_for(layout=self.layout, category=self.category)

    def is_custom(self, key: str) -> bool:
        return bool(self.custom_value(key))

    def custom_value(self, key: str) -> str:
        entry = REGISTRY[key]
        if entry.model_field:
            return clean_value(entry, getattr(self.wedding, entry.model_field, ""))
        return self.custom.get(key, "")

    def raw(self, key: str) -> str:
        """Texto por substituir: o personalizado ou o original."""
        return self.custom_value(key) or self.default(key)

    def _values(self, extra: dict) -> dict:
        return {**self.values, **{k: v for k, v in extra.items()}}

    def render(self, key: str, **values) -> SafeString:
        entry = REGISTRY.get(key)
        if entry is None:
            return mark_safe("")
        return mark_safe(_substitute(
            self.raw(key), self._values(values), html=True,
            emphasis=entry.emphasis, multiline=entry.multiline,
        ))

    def plain(self, key: str, **values) -> str:
        if key not in REGISTRY:
            return ""
        return _substitute(self.raw(key), self._values(values), html=False)

    def preview_default(self, key: str) -> str:
        """Texto original com os marcadores do evento já preenchidos.

        O nome do convidado e os valores de cada secção ficam visíveis como
        marcadores, para o anfitrião perceber o que muda de pessoa para
        pessoa.
        """
        values = {k: v for k, v in self.values.items() if k != "convidado"}
        return _substitute(self.default(key), values, html=False)

    # --- Acesso nos templates -------------------------------------------
    def __getitem__(self, key: str) -> SafeString:
        if key not in REGISTRY:
            raise KeyError(key)
        return self.render(key)

    def __contains__(self, key) -> bool:
        return key in REGISTRY


def editor_groups(wedding, layout: str) -> list[dict]:
    """Grupos e chaves visíveis no editor para este evento/layout."""
    category = wedding.category.code if getattr(wedding, "category_id", None) else ""
    entries = keys_for(layout=layout, category=category)
    by_group: dict[str, list[TextKey]] = {}
    for entry in entries:
        by_group.setdefault(entry.group, []).append(entry)
    return [
        {"group": group, "entries": by_group[group.code]}
        for group in GROUPS if group.code in by_group
    ]
