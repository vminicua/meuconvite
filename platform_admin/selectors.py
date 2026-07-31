"""
Consultas da área de administração.

Todas as agregações vivem aqui para que as views fiquem legíveis e para
que os números do painel sejam calculados num sítio só — se um KPI mudar
de definição, muda aqui.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from events.models import EventCategory
from subscriptions.models import Payment, PaymentStatus, Plan, Subscription
from weddings.models import Wedding, WeddingStatus

MONTHS_PT = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def month_label(value: date) -> str:
    return f"{MONTHS_PT[value.month - 1]}/{str(value.year)[2:]}"


def kpis() -> dict:
    """Os números do topo do painel."""
    today = timezone.localdate()
    month_start = today.replace(day=1)

    events = Wedding.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status=WeddingStatus.PUBLISHED)),
        draft=Count("id", filter=Q(status=WeddingStatus.DRAFT)),
        blocked=Count("id", filter=Q(status=WeddingStatus.BLOCKED)),
        upcoming=Count("id", filter=Q(main_date__gte=today)),
        new_this_month=Count("id", filter=Q(created_at__date__gte=month_start)),
    )

    users = User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        verified=Count("id", filter=Q(is_email_verified=True)),
        staff=Count("id", filter=Q(is_staff=True)),
        new_this_month=Count("id", filter=Q(created_at__date__gte=month_start)),
    )

    payments = Payment.objects.aggregate(
        pending=Count("id", filter=Q(status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW])),
        confirmed=Count("id", filter=Q(status=PaymentStatus.CONFIRMED)),
        revenue=Sum("amount_mzn", filter=Q(status=PaymentStatus.CONFIRMED)),
        revenue_month=Sum(
            "amount_mzn",
            filter=Q(status=PaymentStatus.CONFIRMED, reviewed_at__date__gte=month_start),
        ),
    )

    paid_subscriptions = Subscription.objects.filter(plan__price_mzn__gt=0).count()
    total_subscriptions = Subscription.objects.count()

    return {
        "events": events,
        "users": users,
        "payments": {
            "pending": payments["pending"] or 0,
            "confirmed": payments["confirmed"] or 0,
            "revenue": payments["revenue"] or Decimal("0"),
            "revenue_month": payments["revenue_month"] or Decimal("0"),
        },
        "subscriptions": {
            "total": total_subscriptions,
            "paid": paid_subscriptions,
            "conversion": round(paid_subscriptions / total_subscriptions * 100)
            if total_subscriptions
            else 0,
        },
    }


def events_per_month(months: int = 6) -> dict:
    """Eventos criados por mês, para o gráfico de linhas."""
    today = timezone.localdate()
    start = (today.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)

    rows = (
        Wedding.objects.filter(created_at__date__gte=start)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    counts = {row["month"].date().replace(day=1): row["total"] for row in rows if row["month"]}

    labels, values = [], []
    cursor = start
    while cursor <= today:
        labels.append(month_label(cursor))
        values.append(counts.get(cursor, 0))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"labels": labels, "values": values}


def revenue_per_month(months: int = 6) -> dict:
    """Receita confirmada por mês, para o gráfico de barras."""
    today = timezone.localdate()
    start = (today.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)

    rows = (
        Payment.objects.filter(status=PaymentStatus.CONFIRMED, reviewed_at__date__gte=start)
        .annotate(month=TruncMonth("reviewed_at"))
        .values("month")
        .annotate(total=Sum("amount_mzn"))
        .order_by("month")
    )
    totals = {
        row["month"].date().replace(day=1): float(row["total"] or 0)
        for row in rows
        if row["month"]
    }

    labels, values = [], []
    cursor = start
    while cursor <= today:
        labels.append(month_label(cursor))
        values.append(totals.get(cursor, 0))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"labels": labels, "values": values}


def events_by_category() -> dict:
    """Distribuição dos eventos por tipo, para o gráfico circular."""
    rows = (
        EventCategory.objects.annotate(total=Count("weddings"))
        .filter(total__gt=0)
        .order_by("-total")
    )
    return {
        "labels": [row.name for row in rows],
        "values": [row.total for row in rows],
    }


def events_list(search: str = "", status: str = "", category: str = "") -> QuerySet[Wedding]:
    queryset = Wedding.objects.select_related("owner", "category").annotate(
        moment_total=Count("events", distinct=True),
        member_total=Count("members", distinct=True),
    )
    if search:
        queryset = queryset.filter(
            Q(primary_name__icontains=search)
            | Q(secondary_name__icontains=search)
            | Q(slug__icontains=search)
            | Q(city__icontains=search)
            | Q(owner__email__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category__code=category)
    return queryset.order_by("-created_at")


def users_list(search: str = "", role: str = "") -> QuerySet[User]:
    queryset = User.objects.annotate(
        events=Count("owned_weddings", distinct=True),
        memberships=Count("wedding_memberships", distinct=True),
    )
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
        )
    if role == "staff":
        queryset = queryset.filter(is_staff=True)
    elif role == "inactive":
        queryset = queryset.filter(is_active=False)
    elif role == "unverified":
        queryset = queryset.filter(is_email_verified=False)
    return queryset.order_by("-created_at")


def audit_list(action: str = "", search: str = "") -> QuerySet[AuditLog]:
    queryset = AuditLog.objects.select_related("user", "wedding")
    if action:
        queryset = queryset.filter(action=action)
    if search:
        queryset = queryset.filter(
            Q(actor_label__icontains=search)
            | Q(object_label__icontains=search)
            | Q(model_name__icontains=search)
        )
    return queryset.order_by("-created_at")


def plans_list() -> QuerySet[Plan]:
    return Plan.objects.annotate(
        subscribers=Count("subscriptions", distinct=True),
        confirmed_payments=Count(
            "payments", filter=Q(payments__status=PaymentStatus.CONFIRMED), distinct=True
        ),
    ).order_by("display_order", "max_guests")


def categories_list() -> QuerySet[EventCategory]:
    return EventCategory.objects.annotate(usage=Count("weddings")).order_by(
        "display_order", "name"
    )
