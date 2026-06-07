from logger_config import logger


def sanitize_ticket(ticket):
    """
    Elimina datos personales antes de mostrarlos en el chatbot.
    """
    hidden_fields = [
        "customer_name",
        "customer_lastname",
        "employee_name",
        "employee_lastname",
        "employee_email",
        "employee_phone_number",
    ]

    safe_ticket = dict(ticket)

    for field in hidden_fields:
        safe_ticket.pop(field, None)

    return safe_ticket


def classify_issue(category, description):
    category = str(category).lower()
    description = str(description).lower()

    escalation_keywords = [
        "corte",
        "sin servicio",
        "no tener servicio",
        "luz roja",
        "fibra",
        "falta de señal",
        "sin éxito",
        "sin exito",
        "cobertura crítica",
        "cobertura critica",
    ]

    remote_keywords = [
        "velocidad",
        "intermitencia",
        "lenta",
        "lento",
        "lentitud",
        "ping",
        "reinicio",
        "router",
        "módem",
        "modem",
    ]

    if any(word in description for word in escalation_keywords):
        return "ESCALAR_TECNICO"

    if "corte" in category or "fibra" in category or "cobertura" in category:
        return "ESCALAR_TECNICO"

    if "velocidad" in category or "intermitencia" in category:
        return "DIAGNOSTICO_REMOTO"

    if any(word in description for word in remote_keywords):
        return "DIAGNOSTICO_REMOTO"

    return "REVISION_SOPORTE"


def find_ticket_by_number(tickets, ticket_number):
    for ticket in tickets:
        if str(ticket.get("ticket_number", "")).upper() == str(ticket_number).upper():
            return ticket
    return None


def generate_diagnosis(ticket):
    category = ticket.get("category", "Sin categoría")
    description = ticket.get("description", "")
    status = ticket.get("status", "Sin estado")
    ticket_number = ticket.get("ticket_number", "Sin folio")

    decision = classify_issue(category, description)

    logger.info(
        f"DIAGNOSIS | ticket={ticket_number} | category={category} | status={status} | decision={decision}"
    )

    if str(status).lower() == "cerrado":
        return {
            "ticket": ticket_number,
            "status": status,
            "category": category,
            "decision": "INFORMAR_RESOLUCION",
            "message": "Tu ticket aparece como cerrado. El caso ya fue atendido previamente.",
            "recommended_steps": [
                "Validar si el servicio se encuentra funcionando actualmente.",
                "Si el problema continúa, generar una nueva solicitud de soporte."
            ]
        }

    if decision == "DIAGNOSTICO_REMOTO":
        return {
            "ticket": ticket_number,
            "status": status,
            "category": category,
            "decision": decision,
            "message": "Detecté un posible problema de velocidad, lentitud o intermitencia. Iniciaremos diagnóstico remoto.",
            "recommended_steps": [
                "Verificar que el módem o router esté encendido.",
                "Reiniciar el equipo durante 30 segundos.",
                "Esperar a que las luces del módem estabilicen.",
                "Realizar una prueba de ping simulada.",
                "Si el problema persiste, escalar a soporte técnico."
            ]
        }

    if decision == "ESCALAR_TECNICO":
        return {
            "ticket": ticket_number,
            "status": status,
            "category": category,
            "decision": decision,
            "message": "El problema parece requerir atención técnica. Se recomienda escalar el caso a un ingeniero de soporte.",
            "recommended_steps": [
                "No repetir reinicios si ya se intentaron sin éxito.",
                "Registrar evidencia del problema.",
                "Enviar el caso a soporte técnico humano."
            ]
        }

    return {
        "ticket": ticket_number,
        "status": status,
        "category": category,
        "decision": decision,
        "message": "Tu caso será canalizado a soporte para revisión.",
        "recommended_steps": [
            "Validar datos del servicio.",
            "Canalizar el caso a un agente humano de soporte.",
            "Dar seguimiento según el tipo de solicitud."
        ]
    }
def build_escalation_payload(ticket, diagnosis):
    """
    Estructura JSON limpia para registrar la escalación como comentario técnico.
    No incluye datos personales.
    """
    return {
        "idTicket": ticket.get("idTicket"),
        "comment": (
            "Escalación automática generada por agente IA. "
            f"Ticket: {ticket.get('ticket_number')}. "
            f"Categoría: {ticket.get('category')}. "
            f"Decisión: {diagnosis.get('decision')}. "
            f"Motivo: {diagnosis.get('message')} "
            "Se recomienda asignar este caso a un ingeniero de soporte técnico humano."
        )
    }
