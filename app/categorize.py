from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Rule, Transaction

# (nombre, tipo, icono, color, patrones)
DEFAULT_CATEGORIES: list[tuple[str, str, str, str, list[str]]] = [
    ("Supermercado", "expense", "🛒", "#4f9d69", ["mercadona", "carrefour", "lidl", "aldi", "alcampo", "dia ", "eroski", "consum", "hipercor", "ahorramas", "bonpreu", "froiz", "gadis"]),
    ("Restaurantes", "expense", "🍽", "#d9822b", ["restaurante", "bar ", "cafe", "cafeteria", "glovo", "just eat", "uber eats", "deliveroo", "telepizza", "burger king", "mcdonald", "starbucks"]),
    ("Transporte", "expense", "🚗", "#3b7dd8", ["uber", "cabify", "bolt", "renfe", "metro", "emt ", "alsa", "repsol", "cepsa", "galp", "shell", "bp ", "parking", "autopista", "ryanair", "vueling", "iberia"]),
    ("Vivienda", "expense", "🏠", "#8e6bd1", ["alquiler", "hipoteca", "comunidad", "ikea", "leroy merlin"]),
    ("Suministros", "expense", "💡", "#c9a227", ["iberdrola", "endesa", "naturgy", "holaluz", "totalenergies", "canal de isabel", "aguas", "movistar", "vodafone", "orange", "digi", "masmovil", "pepephone", "jazztel", "o2 "]),
    ("Suscripciones", "expense", "🔁", "#d1495b", ["netflix", "spotify", "hbo", "max.com", "disney", "prime video", "amazon prime", "apple.com/bill", "icloud", "youtube", "dazn", "chatgpt", "openai", "anthropic", "claude.ai"]),
    ("Compras", "expense", "🛍", "#e07a5f", ["amazon", "zara", "primark", "decathlon", "el corte ingles", "mediamarkt", "fnac", "aliexpress", "shein", "pull&bear", "bershka", "massimo dutti", "stradivarius", "oysho"]),
    ("Salud", "expense", "🩺", "#2a9d8f", ["farmacia", "clinica", "dentista", "sanitas", "adeslas", "dkv", "asisa", "optica", "gimnasio", "gym", "basic-fit", "altafit"]),
    ("Ocio", "expense", "🎟", "#b5179e", ["cine", "teatro", "ticketmaster", "entradas", "steam", "playstation", "nintendo", "xbox"]),
    ("Viajes", "expense", "✈️", "#118ab2", ["booking", "airbnb", "hotel", "expedia", "edreams"]),
    ("Impuestos y comisiones", "expense", "🏛", "#6c757d", ["agencia tributaria", "aeat", "comision", "impuesto", "tasa ", "ayuntamiento"]),
    ("Efectivo", "expense", "💶", "#7f8c8d", ["cajero", "retirada", "atm"]),
    ("Otros gastos", "expense", "•", "#8a8a8a", []),
    ("Nómina", "income", "💼", "#2ec4b6", ["nomina", "nómina", "salario"]),
    ("Bizum recibido", "income", "📲", "#06d6a0", []),
    ("Otros ingresos", "income", "•", "#8ac926", []),
]


def seed_categories(db: Session) -> None:
    if db.scalar(select(Category.id).limit(1)):
        return
    for name, kind, icon, color, patterns in DEFAULT_CATEGORIES:
        category = Category(name=name, kind=kind, icon=icon, color=color)
        db.add(category)
        db.flush()
        for pattern in patterns:
            db.add(Rule(pattern=pattern, category_id=category.id))
    db.commit()


class Categorizer:
    def __init__(self, db: Session):
        self.rules = db.scalars(select(Rule).order_by(Rule.priority, Rule.id)).all()
        by_name = {c.name: c.id for c in db.scalars(select(Category))}
        self.fallback_expense = by_name.get("Otros gastos")
        self.fallback_income = by_name.get("Otros ingresos")
        self.bizum_income = by_name.get("Bizum recibido")

    def categorize(self, tx: Transaction) -> int | None:
        text = f" {tx.counterparty or ''} {tx.description} ".lower()
        for rule in self.rules:
            if rule.pattern.lower() in text:
                return rule.category_id
        if tx.amount > 0:
            if "bizum" in text and self.bizum_income:
                return self.bizum_income
            return self.fallback_income
        return self.fallback_expense
