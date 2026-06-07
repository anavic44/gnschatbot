import os
import json
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

from gns_api import get_tickets, get_categories, post_escalation
from agent import (
    find_ticket_by_number,
    generate_diagnosis,
    build_escalation_payload,
    sanitize_ticket,
    run_ping_test,
    get_target_ip_from_ticket,
    classify_free_text_problem,
    build_ticketless_escalation_payload,
)
from logger_config import logger

load_dotenv()

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>GNS Chatbot Agent</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            padding: 40px;
        }
        .chat-container {
            max-width: 950px;
            margin: auto;
            background: #1e293b;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        }
        .badge {
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 12px;
            margin-bottom: 10px;
        }
        .bot-message, .user-message {
            padding: 16px;
            border-radius: 12px;
            margin: 12px 0;
            line-height: 1.5;
        }
        .bot-message {
            background: #020617;
            border-left: 4px solid #10b981;
        }
        .user-message {
            background: #334155;
            border-left: 4px solid #38bdf8;
        }
        input, select, textarea, button {
            padding: 12px;
            border-radius: 8px;
            border: none;
            margin-top: 10px;
            font-size: 15px;
        }
        input, select, textarea {
            width: 100%;
            box-sizing: border-box;
            background: #f8fafc;
            color: #0f172a;
        }
        textarea {
            min-height: 90px;
            resize: vertical;
        }
        button {
            background: #10b981;
            color: white;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
        }
        button:hover {
            background: #059669;
        }
        pre {
            background: #020617;
            color: #d1fae5;
            padding: 16px;
            border-radius: 10px;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .menu-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            margin-top: 15px;
            margin-bottom: 20px;
        }
        .menu-item {
            background: #0f172a;
            padding: 12px;
            border-radius: 10px;
            border-left: 4px solid #10b981;
        }
        .hint {
            color: #cbd5e1;
            font-size: 13px;
            margin-top: 4px;
        }
        .footer {
            margin-top: 25px;
            font-size: 12px;
            color: #94a3b8;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <span class="badge">Agente IA - Soporte GNS</span>
        <h1>GNS Chatbot Agent</h1>

        <div class="bot-message">
            Hola, soy el asistente virtual de GNS. Puedo ayudarte aunque no tengas número de ticket.
            Puedes escribir tu folio si lo tienes, o simplemente describir qué está pasando con tu servicio.
        </div>

        <div class="menu-grid">
            <div class="menu-item">1. Consultar estado de ticket</div>
            <div class="menu-item">2. Revisar problema de internet lento o intermitente</div>
            <div class="menu-item">3. Guía de reinicio de módem/router</div>
            <div class="menu-item">4. Ejecutar prueba de conexión desde el agente</div>
            <div class="menu-item">5. Solicitar revisión de técnico</div>
            <div class="menu-item">6. Contactar soporte para trámites o dudas</div>
        </div>

        <form method="POST" action="/chatbot">
            <label>Selecciona una opción:</label>
            <select name="option" required>
                <option value="1">1. Consultar estado de ticket</option>
                <option value="2">2. Revisar problema de internet lento o intermitente</option>
                <option value="3">3. Guía de reinicio de módem/router</option>
                <option value="4">4. Ejecutar prueba de conexión desde el agente</option>
                <option value="5">5. Solicitar revisión de técnico</option>
                <option value="6">6. Contactar soporte para trámites o dudas</option>
            </select>

            <label>Número de ticket, si lo tienes:</label>
            <input type="text" name="ticket_number" placeholder="Ejemplo: TCK794814">

            <div class="hint">
                Si no tienes ticket, deja este campo vacío y describe tu problema abajo.
            </div>

            <label>Describe tu problema:</label>
            <textarea name="description" placeholder="Ejemplo: mi internet está muy lento / tengo luz roja en el módem / no tengo servicio"></textarea>

            <button type="submit">Enviar al chatbot</button>
        </form>

        {% if conversation %}
            <h2>Conversación</h2>
            <div class="user-message">
                <strong>Usuario:</strong><br>
                {{ user_input }}
            </div>
            <div class="bot-message">
                <strong>Chatbot:</strong><br>
                {{ conversation }}
            </div>

            {% if result %}
                <h3>Detalle técnico</h3>
                <pre>{{ result }}</pre>
            {% endif %}
        {% endif %}

        <div class="footer">
            Servicio ejecutándose en VM 10.32.66.113. Las acciones se registran en logs/agent.log.
        </div>
    </div>
</body>
</html>
"""


def get_ticket_or_none(ticket_number):
    if not ticket_number:
        return None, None

    tickets, status_code = get_tickets()
    logger.info(f"API_CALL | GET tickets | HTTP={status_code}")

    ticket = find_ticket_by_number(tickets, ticket_number)

    if not ticket:
        logger.warning(f"TICKET_NOT_FOUND | ticket={ticket_number}")
        return None, {
            "error": "Ticket no encontrado",
            "ticket_number": ticket_number
        }

    return ticket, None


def build_ticket_based_response(option, ticket):
    diagnosis = generate_diagnosis(ticket)
    safe_ticket = sanitize_ticket(ticket)

    ticket_number = ticket.get("ticket_number")
    status = ticket.get("status")
    category = ticket.get("category")

    response_payload = {
        "mode": "ticket",
        "safe_ticket": safe_ticket,
        "diagnosis": diagnosis
    }

    if option == "1":
        conversation = (
            f"Encontré tu ticket {ticket_number}. Está en estado: {status}. "
            f"El tipo de reporte registrado es: {category}. "
            "Si el problema sigue ocurriendo, puedo ayudarte con una revisión básica o canalizarlo a soporte."
        )

    elif option == "2":
        if diagnosis["decision"] == "DIAGNOSTICO_REMOTO":
            conversation = (
                "Por lo que veo en tu ticket, parece un problema de velocidad o intermitencia. "
                "Vamos paso a paso: revisa que el módem esté encendido, que las luces estén estables "
                "y, si puedes, reinícialo durante 30 segundos."
            )
        elif diagnosis["decision"] == "ESCALAR_TECNICO":
            conversation = (
                "Por la información de tu ticket, parece que el problema requiere revisión técnica. "
                "No te voy a pedir que repitas reinicios si ya hay señales de falta de señal o corte."
            )
        else:
            conversation = (
                "Tu ticket parece requerir revisión por parte de soporte. "
                "Te recomiendo continuar con un agente para validar los detalles."
            )

    elif option == "3":
        conversation = (
            "Vamos a intentar un reinicio seguro. Desconecta el módem o router durante 30 segundos, "
            "vuelve a conectarlo y espera a que las luces se estabilicen. "
            "Si el problema sigue, podemos hacer una prueba de conexión o escalar el caso."
        )

    elif option == "4":
        target_ip = get_target_ip_from_ticket(ticket)

        if target_ip:
            ping_result = run_ping_test(target_ip, 4)
            ping_source = "IP técnica asociada al ticket"
        else:
            ping_result = run_ping_test("8.8.8.8", 4)
            ping_source = "destino externo de referencia porque la API no proporciona IP técnica del cliente"

        response_payload["ping_test"] = ping_result
        response_payload["ping_source"] = ping_source

        if ping_result.get("success"):
            conversation = (
                "La prueba de conexión desde el agente respondió correctamente. "
                "Esto confirma que la VM del agente tiene salida a Internet. "
                "Como la API no proporciona la IP técnica de tu equipo, esta prueba se usa como referencia general."
            )
        else:
            conversation = (
                "La prueba de conexión desde el agente falló. "
                "Esto puede indicar un problema general de conectividad o una restricción de red. "
                "Si tu reporte incluye falta de señal o luz roja, se recomienda revisión técnica."
            )

        logger.info(
            f"PING_TEST | ticket={ticket_number} | host={ping_result.get('host')} | success={ping_result.get('success')} | source={ping_source}"
        )

    elif option == "5":
        escalation_payload = build_escalation_payload(ticket, diagnosis)
        escalation_response, escalation_status = post_escalation(escalation_payload)

        logger.info(
            f"API_CALL | POST escalation | ticket={ticket_number} | HTTP={escalation_status} | payload={escalation_payload}"
        )

        response_payload["escalation"] = {
            "http_status": escalation_status,
            "payload_sent": escalation_payload,
            "api_response": escalation_response
        }

        if escalation_status in [200, 201]:
            conversation = (
                f"Listo. Registré una nota de escalamiento en el ticket {ticket_number}. "
                "Un integrante del equipo técnico deberá revisar el caso."
            )
        else:
            conversation = (
                f"Intenté registrar el escalamiento, pero la API respondió con código {escalation_status}. "
                "El evento quedó registrado en logs para revisión."
            )

    elif option == "6":
        conversation = (
            "Te canalizaré a soporte para que revisen tu solicitud. "
            "Esta opción es ideal para dudas de pago, cambios de plan, contraseña, cancelaciones o seguimiento general."
        )

    else:
        conversation = "No reconocí esa opción. Por favor selecciona una opción del menú."

    logger.info(
        f"CHATBOT_FLOW | mode=ticket | ticket={ticket_number} | option={option} | category={category} | decision={diagnosis.get('decision')}"
    )

    return conversation, response_payload


def build_ticketless_response(option, description):
    classification = classify_free_text_problem(description)

    response_payload = {
        "mode": "no_ticket",
        "description": description,
        "classification": classification
    }

    decision = classification.get("decision")

    if option == "1":
        conversation = (
            "Para consultar un ticket necesito que me compartas el número de folio. "
            "Si no lo tienes, describe tu problema y puedo orientarte con una revisión inicial."
        )

    elif option == "2":
        if decision == "DIAGNOSTICO_REMOTO":
            conversation = (
                "Parece que tu servicio está lento o intermitente. "
                "Primero revisa que el módem esté encendido y que las luces estén estables. "
                "Después reinícialo durante 30 segundos. Si sigue igual, conviene levantar o escalar un reporte."
            )
        elif decision == "ESCALAR_TECNICO":
            conversation = (
                "Por lo que describes, podría requerirse revisión técnica. "
                "Si ves luz roja, falta de señal o ya reiniciaste varias veces sin mejora, lo mejor es enviarlo a soporte técnico."
            )
        else:
            conversation = (
                "Esto parece requerir revisión por soporte. "
                "Te recomiendo compartir más detalles o contactar a un agente."
            )

    elif option == "3":
        conversation = (
            "Puedes intentar este reinicio: desconecta el módem o router durante 30 segundos, "
            "vuelve a conectarlo y espera a que las luces se estabilicen. "
            "Si ves luz roja o no regresa la señal, conviene solicitar revisión técnica."
        )

    elif option == "4":
        ping_result = run_ping_test("8.8.8.8", 4)

        response_payload["ping_test"] = ping_result
        response_payload["ping_source"] = (
            "destino externo de referencia porque no hay ticket ni IP técnica del cliente"
        )

        if ping_result.get("success"):
            conversation = (
                "La prueba de conexión desde el agente respondió correctamente. "
                "Esto solo valida la salida a Internet de la VM del agente, no directamente tu módem. "
                "Para revisar tu servicio específico se necesitaría un ticket o información técnica adicional."
            )
        else:
            conversation = (
                "La prueba de conexión desde el agente falló. "
                "Se recomienda revisar conectividad general y contactar soporte."
            )

        logger.info(
            f"PING_TEST | mode=no_ticket | host={ping_result.get('host')} | success={ping_result.get('success')}"
        )

    elif option == "5":
        if decision == "ESCALAR_TECNICO":
            escalation_payload = build_ticketless_escalation_payload(description, classification)
            response_payload["escalation_intent"] = escalation_payload

            conversation = (
                "Tu descripción indica que podría ser necesaria una revisión técnica. "
                "Como no tengo un número de ticket, no puedo registrar el escalamiento directamente en la API. "
                "Te recomiendo levantar un ticket o compartir tu folio para registrar la escalación."
            )
        else:
            conversation = (
                "Con la información proporcionada, primero recomiendo una revisión básica o contactar soporte. "
                "Si el problema es falta de señal, luz roja o corte total, solicita revisión técnica."
            )

    elif option == "6":
        conversation = (
            "Te recomiendo contactar a soporte para que validen tu cuenta o generen un ticket. "
            "Puedo orientarte mejor si describes si es falla de internet, pago, cambio de plan o instalación."
        )

    else:
        conversation = "No reconocí esa opción. Por favor selecciona una opción del menú."

    logger.info(
        f"CHATBOT_FLOW | mode=no_ticket | option={option} | decision={classification.get('decision')} | category={classification.get('category')}"
    )

    return conversation, response_payload


@app.route("/", methods=["GET"])
def home():
    return render_template_string(
        HTML,
        conversation=None,
        result=None,
        user_input=None
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "gns-chatbot-agent"
    })


@app.route("/chatbot", methods=["POST"])
def chatbot():
    option = request.form.get("option")
    ticket_number = request.form.get("ticket_number", "").strip()
    description = request.form.get("description", "").strip()

    ticket, error = get_ticket_or_none(ticket_number)

    if error:
        conversation, response_payload = build_ticketless_response(option, description)
        response_payload["ticket_lookup_error"] = error
    elif ticket:
        conversation, response_payload = build_ticket_based_response(option, ticket)
    else:
        conversation, response_payload = build_ticketless_response(option, description)

    return render_template_string(
        HTML,
        conversation=conversation,
        result=json.dumps(response_payload, indent=4, ensure_ascii=False),
        user_input=f"Opción {option} | Ticket: {ticket_number or 'sin ticket'} | Descripción: {description or 'sin descripción'}"
    )


@app.route("/api/chatbot", methods=["POST"])
def api_chatbot():
    data = request.get_json()
    option = str(data.get("option"))
    ticket_number = str(data.get("ticket_number", "")).strip()
    description = str(data.get("description", "")).strip()

    ticket, error = get_ticket_or_none(ticket_number)

    if error:
        conversation, response_payload = build_ticketless_response(option, description)
        response_payload["ticket_lookup_error"] = error
    elif ticket:
        conversation, response_payload = build_ticket_based_response(option, ticket)
    else:
        conversation, response_payload = build_ticketless_response(option, description)

    return jsonify({
        "chatbot_message": conversation,
        "technical_detail": response_payload
    })


@app.route("/api/summary", methods=["GET"])
def api_summary():
    tickets, tickets_status = get_tickets()
    categories, categories_status = get_categories()

    logger.info(f"API_CALL | GET tickets | HTTP={tickets_status}")
    logger.info(f"API_CALL | GET categories | HTTP={categories_status}")

    open_tickets = [t for t in tickets if str(t.get("status")).lower() == "abierto"]

    return jsonify({
        "total_tickets": len(tickets),
        "open_tickets": len(open_tickets),
        "categories_available": len(categories),
        "status": "summary_generated"
    })


if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
