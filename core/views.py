from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET


LEGAL_PAGES = {
    "privacy": {
        "eyebrow": "Privacidade",
        "title": "Política de privacidade",
        "summary": "Explicamos com transparência que dados o MeuConvite utiliza, porquê e como pode exercer os seus direitos.",
        "sections": [
            ("Quem trata os dados", ["O MeuConvite trata os dados necessários para prestar e proteger a plataforma. O organizador de cada evento decide que dados dos convidados introduz e como os utiliza na organização da celebração."], []),
            ("Dados que podemos tratar", ["Recolhemos apenas o necessário para disponibilizar as funcionalidades escolhidas."], ["Dados da conta, como nome, email e informação de acesso.", "Dados do evento e dos convidados, como nome, telefone, email, confirmação, lugares, presente escolhido e registos de check-in.", "Dados técnicos e de segurança, como endereço IP, navegador, datas de acesso e registos de erro.", "Dados de subscrição, comprovativos e referências de pagamento. Não guardamos o PIN do M-Pesa."]),
            ("Para que usamos os dados", [], ["Criar e apresentar convites individuais.", "Gerir convidados, confirmações, mesas, presentes e check-in.", "Enviar comunicações solicitadas pelo organizador em planos que incluam esse serviço.", "Processar subscrições, prestar apoio, prevenir abuso e manter a plataforma segura.", "Cumprir obrigações legais aplicáveis."]),
            ("Partilha e fornecedores", ["Não vendemos dados pessoais. Podemos partilhar o mínimo necessário com fornecedores de alojamento, email, mensagens e pagamentos, ou quando a lei o exija. O envio por SMS só é feito quando solicitado por uma conta com um plano elegível."], []),
            ("Conservação e eliminação", ["Guardamos os dados enquanto a conta ou o evento estiver activo e pelo período adicional necessário para segurança, resolução de disputas e obrigações legais. O organizador pode corrigir ou eliminar dados dos convidados na plataforma."], []),
            ("Os seus direitos", ["Pode pedir acesso, correcção ou eliminação dos seus dados, retirar um consentimento aplicável e apresentar uma questão sobre o tratamento. Se recebeu um convite, pode também contactar directamente o organizador do evento."], []),
            ("Contacto", ["Para questões de privacidade, escreva para o endereço de apoio indicado nesta página. Responderemos depois de confirmar a identidade do requerente."], []),
        ],
    },
    "terms": {
        "eyebrow": "Regras de utilização",
        "title": "Termos e condições",
        "summary": "As regras essenciais para usar o MeuConvite de forma segura e responsável.",
        "sections": [
            ("O serviço", ["O MeuConvite permite criar convites digitais e gerir eventos, convidados, confirmações, presentes, mesas e acessos. Algumas funcionalidades dependem do pacote activo."], []),
            ("Responsabilidade do organizador", [], ["Fornecer informação verdadeira e manter a conta protegida.", "Ter fundamento legítimo para inserir e contactar convidados.", "Não utilizar a plataforma para spam, fraude, conteúdo ilegal ou ofensivo.", "Rever os dados e a mensagem antes de qualquer envio pago."]),
            ("Planos e pagamentos", ["Os limites, preços e vantagens apresentados no momento da subscrição fazem parte da contratação. Um pagamento só activa o pacote depois da respectiva confirmação. Créditos de SMS consumidos não são repostos por mensagens válidas já submetidas ao fornecedor."], []),
            ("Disponibilidade e alterações", ["Trabalhamos para manter o serviço disponível e seguro, mas podem existir interrupções de manutenção ou de fornecedores externos. Podemos melhorar funcionalidades e actualizar estes termos, indicando a data da versão vigente."], []),
            ("Suspensão", ["Podemos restringir uma conta para proteger pessoas ou a plataforma em caso de abuso, risco de segurança, falta de pagamento ou violação destes termos."], []),
        ],
    },
    "cookies": {
        "eyebrow": "Preferências",
        "title": "Política de cookies",
        "summary": "Usamos tecnologia essencial para iniciar sessão, proteger formulários e manter as suas preferências.",
        "sections": [
            ("Cookies essenciais", ["São necessários para autenticação, segurança, prevenção de pedidos falsificados e funcionamento da sessão. Sem eles, partes importantes da plataforma não funcionam."], []),
            ("Preferências", ["Podemos guardar escolhas de interface para evitar que tenha de as repetir. Não utilizamos cookies para vender perfis de convidados."], []),
            ("Serviços externos", ["Alguns recursos técnicos podem ser carregados por fornecedores externos. Se forem introduzidas ferramentas opcionais de análise ou publicidade, esta política e os controlos de consentimento serão actualizados antes da sua utilização."], []),
            ("Como controlar", ["Pode apagar ou bloquear cookies nas definições do navegador. O bloqueio de cookies essenciais pode impedir o início de sessão e o envio seguro de formulários."], []),
        ],
    },
    "security": {
        "eyebrow": "Confiança",
        "title": "Segurança",
        "summary": "Protegemos convites e dados com controlos técnicos, acesso limitado e práticas de desenvolvimento seguro.",
        "sections": [
            ("Como protegemos a plataforma", [], ["Ligações HTTPS em produção.", "Palavras-passe armazenadas com hashing seguro, nunca em texto simples.", "Convites individuais com ligações não previsíveis.", "Permissões por função e separação entre eventos.", "Registos de auditoria, validação de ficheiros e protecção contra pedidos maliciosos."]),
            ("O que deve fazer", [], ["Use uma palavra-passe exclusiva e não partilhe a sua sessão.", "Confirme o destinatário antes de enviar um convite.", "Remova rapidamente membros da equipa que já não necessitam de acesso.", "Comunique actividades suspeitas ao apoio."]),
            ("Comunicar um problema", ["Se descobrir uma vulnerabilidade, não aceda a dados de terceiros. Envie uma descrição e os passos de reprodução para o contacto de apoio para podermos investigar."], []),
        ],
    },
    "contact": {
        "eyebrow": "Estamos disponíveis",
        "title": "Contacto e apoio",
        "summary": "Dúvidas sobre a conta, pagamentos, privacidade ou segurança? Fale connosco.",
        "sections": [
            ("Apoio MeuConvite", ["Envie um email com o nome da conta, o evento e uma descrição clara da questão. Não inclua palavras-passe, PINs ou códigos de acesso."], []),
            ("Questões sobre um convite", ["Se é convidado e pretende alterar uma confirmação, presente ou informação pessoal, contacte primeiro os organizadores do evento. Eles controlam a lista de convidados."], []),
            ("Tempo de resposta", ["Tratamos primeiro incidentes de segurança e indisponibilidade. As restantes questões são respondidas por ordem de chegada."], []),
        ],
    },
}


def home(request: HttpRequest) -> HttpResponse:
    """Public landing page. Authenticated users go straight to their weddings."""
    if request.user.is_authenticated:
        return redirect("weddings:list")

    from weddings.selectors import categories_with_templates

    return render(
        request,
        "core/home.html",
        {"categories": categories_with_templates()},
    )


@require_GET
def legal_page(request: HttpRequest, page: str) -> HttpResponse:
    """Public trust and legal information, kept available without an account."""
    return render(
        request,
        "core/legal_page.html",
        {"legal_page": LEGAL_PAGES[page], "legal_page_key": page},
    )


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """
    Lightweight liveness probe.

    Only reports that the process is up and the database answers; no
    version or configuration detail is exposed.
    """
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - depends on infrastructure
        return JsonResponse({"status": "degraded"}, status=503)
    return JsonResponse({"status": "ok"})
