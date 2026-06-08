
import os

import re

import json

from datetime import datetime

from pathlib import Path

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

from ai_client import generate_customer_response

load_dotenv()

app = Flask(__name__)

HTML = """

<!DOCTYPE html>

<html lang="es">

<head>

    <meta charset="UTF-8">

    <title>GNS WhatsApp Chatbot</title>

    <style>

        body {

            margin: 0;

            font-family: Arial, sans-serif;

            background: #0f172a;

            color: #111827;

        }

        .phone {

            max-width: 430px;

            margin: 30px auto;

            background: #e5ddd5;

            border-radius: 24px;

            overflow: hidden;

            box-shadow: 0 20px 50px rgba(0,0,0,0.45);

        }

        .header {

            background: #075e54;

            color: white;

            padding: 18px;

            display: flex;

            align-items: center;

            gap: 12px;

        }

        .avatar {

            width: 42px;

            height: 42px;

            background: #10b981;

            border-radius: 50%;

            display: flex;

            align-items: center;

            justify-content: center;

            font-weight: bold;

        }

        .header-text h1 {

            font-size: 18px;

            margin: 0;

        }

        .header-text p {

            margin: 2px 0 0;

            font-size: 12px;

            color: #d1fae5;

        }

        .chat {

            padding: 16px;

            min-height: 520px;

            background: #e5ddd5;

        }

        .bubble {

            max-width: 85%;

            padding: 12px 14px;

            border-radius: 12px;

            margin: 10px 0;

            line-height: 1.45;

            font-size: 14px;

            white-space: pre-line;

        }

        .bot {

            background: #ffffff;

            border-top-left-radius: 2px;

            color: #111827;

        }

        .user {

            background: #dcf8c6;

            border-top-right-radius: 2px;

            margin-left: auto;

            color: #111827;

        }

        .quick-buttons {

            display: grid;

            grid-template-columns: 1fr 1fr;

            gap: 8px;

            margin: 14px 0;

        }

        .quick-buttons button {

            border: none;

            background: #ffffff;

            color: #075e54;

            padding: 10px;

            border-radius: 999px;

            font-weight: bold;

            cursor: pointer;

            box-shadow: 0 2px 4px rgba(0,0,0,0.12);

        }

        .quick-buttons button:hover {

            background: #f0fdf4;

        }

        .quick-buttons .menu-button {

            grid-column: 1 / -1;

            background: #075e54;

            color: white;

        }

        form {

            background: #f0f2f5;

            padding: 12px;

            display: flex;

            gap: 8px;

            align-items: center;

        }

        input {

            flex: 1;

            border: none;

            border-radius: 999px;

            padding: 13px 16px;

            font-size: 14px;

            outline: none;

        }

        .send {

            width: 46px;

            height: 46px;

            border-radius: 50%;

            border: none;

            background: #25d366;

            color: white;

            font-size: 18px;

            cursor: pointer;

        }

        details {

            margin-top: 14px;

            background: rgba(255,255,255,0.86);

            padding: 10px;

            border-radius: 10px;

            font-size: 12px;

        }

        pre {

            white-space: pre-wrap;

            overflow-x: auto;

            color: #111827;

        }

        .meta {

            font-size: 11px;

            color: #64748b;

            margin-top: 6px;

        }

    </style>

</head>

<body>

    <div class="phone">

        <div class="header">

            <div class="avatar">G</div>

            <div class="header-text">

                <h1>Soporte GNS</h1>

                <p>Agente virtual en línea</p>

            </div>

        </div>

        <div class="chat">

            <div class="bubble bot">

Hola 👋 Soy el asistente virtual de GNS.

Puedes escribirme tu número de ticket, id de ticket o describir tu problema.

Ejemplos:

• mi internet está muy lento

• tengo luz roja en el módem

• TCK390236

• Consultar ticket 1208

• quiero cambiar mi plan

            </div>

            <div class="quick-buttons">

                <button type="button" onclick="setQuick('Consultar ticket TCK390236')">Consultar TCK</button>

                <button type="button" onclick="setQuick('Consultar ticket 1208')">Consultar ID</button>

                <button type="button" onclick="setQuick('mi internet está muy lento y se va y viene')">Internet lento</button>

                <button type="button" onclick="setQuick('tengo luz roja en el módem y no tengo internet')">Luz roja</button>

                <button type="button" onclick="setQuick('ejecutar prueba de conexión')">Prueba conexión</button>

                <button type="button" onclick="setQuick('quiero escalar el ticket TCK390236 a técnico')">Escalar técnico</button>

                <button type="button" onclick="setQuick('quiero cambiar mi plan')">Cambio de plan</button>

                <button type="button" onclick="setQuick('quiero hablar con soporte')">Soporte</button>

                <button type="button" class="menu-button" onclick="window.location.href='/'">Volver al menú</button>

            </div>

            {% if user_message %}

                <div class="bubble user">{{ user_message }}</div>

            {% endif %}

            {% if bot_message %}

                <div class="bubble bot">

{{ bot_message }}

                    <div class="meta">Registrado en logs/agent.log</div>

                </div>

            {% endif %}

            {% if result %}

                <details>

                    <summary>Ver detalle técnico</summary>

                    <pre>{{ result }}</pre>

                </details>

            {% endif %}

        </div>

        <form method="POST" action="/whatsapp">

            <input id="message" name="message" placeholder="Escribe tu mensaje..." required>

            <button class="send" type="submit">➤</button>

        </form>

    </div>

    <script>

        function setQuick(text) {

            document.getElementById("message").value = text;

        }

    </script>

</body>

</html>

"""

def extract_ticket_identifier(message):

    text = str(message).upper()

    tck_match = re.search(r"TCK\d+", text)

    if tck_match:

        return {"type": "ticket_number", "value": tck_match.group(0)}

    numeric_match = re.search(r"(?:TICKET|IDTICKET|ID|FOLIO)?\s*#?\s*(\d{2,6})", text)

    if numeric_match:

        return {"type": "idTicket", "value": int(numeric_match.group(1))}

    return {"type": None, "value": None}

def infer_option_from_message(message, has_ticket=False):

    text = str(message).lower()

    if "ping" in text or "prueba" in text or "conexión" in text or "conexion" in text:

        return "4"

    if (

        "escalar" in text

        or "técnico" in text

        or "tecnico" in text

        or "luz roja" in text

        or "sin internet" in text

        or "no tengo internet" in text

    ):

        return "5"

    if (

        "soporte" in text

        or "hablar" in text

        or "plan" in text

        or "pago" in text

        or "contraseña" in text

        or "password" in text

        or "cambiar" in text

        or "cambio" in text

    ):

        return "6"

    if has_ticket or "ticket" in text or "folio" in text or "consultar" in text:

        return "1"

    return "2"

def get_ticket_or_none(ticket_identifier):

    if not ticket_identifier or not ticket_identifier.get("value"):

        return None, None

    tickets, status_code = get_tickets()

    logger.info(f"API_CALL | GET tickets | HTTP={status_code}")

    identifier_type = ticket_identifier.get("type")

    identifier_value = ticket_identifier.get("value")

    ticket = None

    if identifier_type == "ticket_number":

        ticket = find_ticket_by_number(tickets, identifier_value)

    elif identifier_type == "idTicket":

        for item in tickets:

            try:

                if int(item.get("idTicket")) == int(identifier_value):

                    ticket = item

                    break

            except (TypeError, ValueError):

                continue

    if not ticket:

        logger.warning(f"TICKET_NOT_FOUND | type={identifier_type} | value={identifier_value}")

        return None, {

            "error": "Ticket no encontrado",

            "ticket_identifier": ticket_identifier,

        }

    return ticket, None

def apply_ai_if_safe(conversation, context, allow_ai=True):

    if not allow_ai:

        return conversation

    return generate_customer_response(conversation, context)

def save_local_modification(modification_type, description, ticket=None, extra=None):

    Path("data").mkdir(exist_ok=True)

    record = {

        "created_at": datetime.utcnow().isoformat() + "Z",

        "modification_type": modification_type,

        "description": description,

        "source": "gns-whatsapp-chatbot",

        "ticket": {

            "idTicket": ticket.get("idTicket") if ticket else None,

            "ticket_number": ticket.get("ticket_number") if ticket else None,

            "category": ticket.get("category") if ticket else None,

            "status": ticket.get("status") if ticket else None,

        },

        "extra": extra or {},

    }

    with open("data/local_modifications.jsonl", "a", encoding="utf-8") as file:

        file.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(

        f"LOCAL_MODIFICATION | type={modification_type} | "

        f"ticket={record['ticket']['ticket_number']} | "

        f"idTicket={record['ticket']['idTicket']}"

    )

    return record

def build_ticket_based_response(option, ticket):

    diagnosis = generate_diagnosis(ticket)

    safe_ticket = sanitize_ticket(ticket)

    ticket_number = ticket.get("ticket_number")

    id_ticket = ticket.get("idTicket")

    status = ticket.get("status")

    category = ticket.get("category")

    response_payload = {

        "mode": "ticket",

        "safe_ticket": safe_ticket,

        "diagnosis": diagnosis,

    }

    allow_ai = True

    if option == "1":

        conversation = (

            f"Encontré tu ticket {ticket_number}.\n"

            f"ID interno: {id_ticket}.\n"

            f"Estado: {status}.\n"

            f"Tipo de reporte: {category}.\n\n"

            "Si el problema sigue, puedo ayudarte con una revisión básica o canalizarlo a soporte."

        )

    elif option == "2":

        if diagnosis["decision"] == "DIAGNOSTICO_REMOTO":

            conversation = (

                "Parece un problema de velocidad o intermitencia.\n\n"

                "Vamos paso a paso:\n"

                "1. Revisa que el módem esté encendido.\n"

                "2. Confirma que las luces estén estables.\n"

                "3. Reinícialo durante 30 segundos.\n"

                "4. Si sigue igual, podemos hacer una prueba de conexión."

            )

        elif diagnosis["decision"] == "ESCALAR_TECNICO":

            conversation = (

                "Por la información de tu ticket, esto puede requerir revisión técnica.\n\n"

                "No te pediré repetir reinicios si ya hay señales de falta de señal, luz roja o corte."

            )

        else:

            conversation = (

                "Tu ticket parece requerir revisión de soporte.\n"

                "Te recomiendo continuar con un agente para validar los detalles."

            )

    elif option == "3":

        conversation = (

            "Vamos a intentar un reinicio seguro.\n\n"

            "1. Desconecta el módem o router durante 30 segundos.\n"

            "2. Vuelve a conectarlo.\n"

            "3. Espera a que las luces se estabilicen.\n\n"

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

                "La prueba de conexión respondió correctamente ✅\n\n"

                "Esto confirma que el agente tiene salida a Internet. "

                "Como la API no proporciona la IP técnica de tu equipo, esta prueba se usa como referencia general."

            )

        else:

            conversation = (

                "La prueba de conexión falló.\n"

                "Si tu reporte incluye falta de señal, luz roja o corte, se recomienda revisión técnica."

            )

        logger.info(

            f"PING_TEST | ticket={ticket_number} | host={ping_result.get('host')} | "

            f"success={ping_result.get('success')} | source={ping_source}"

        )

        allow_ai = False

    elif option == "5":

        escalation_payload = build_escalation_payload(ticket, diagnosis)

        escalation_response, escalation_status = post_escalation(escalation_payload)

        logger.info(

            f"API_CALL | POST escalation | ticket={ticket_number} | "

            f"HTTP={escalation_status} | payload={escalation_payload}"

        )

        response_payload["escalation"] = {

            "http_status": escalation_status,

            "payload_sent": escalation_payload,

            "api_response": escalation_response,

        }

        if escalation_status in [200, 201]:

            conversation = (

                f"Listo ✅ Registré una nota de escalamiento en el ticket {ticket_number}.\n"

                "Un integrante del equipo técnico deberá revisar el caso."

            )

        else:

            conversation = (

                f"Intenté registrar el escalamiento, pero la API respondió con código {escalation_status}. "

                "El evento quedó registrado en logs."

            )

        allow_ai = False

    elif option == "6":

        local_modification = save_local_modification(

            "support_request",

            "Solicitud de soporte general o trámite administrativo.",

            ticket=ticket,

            extra={"category": category, "status": status},

        )

        response_payload["local_modification"] = local_modification

        conversation = (

            "Listo ✅ Registré una solicitud local de soporte para seguimiento.\n"

            "Esto no modifica el dataset original ni el ticket en la API, pero deja evidencia de la solicitud."

        )

        allow_ai = False

    else:

        conversation = "No reconocí esa opción. Escribe tu problema o usa un botón rápido."

    logger.info(

        f"WHATSAPP_FLOW | mode=ticket | ticket={ticket_number} | option={option} | "

        f"category={category} | decision={diagnosis.get('decision')}"

    )

    conversation = apply_ai_if_safe(

        conversation,

        {

            "mode": "ticket",

            "ticket_number": ticket_number,

            "idTicket": id_ticket,

            "category": category,

            "decision": diagnosis.get("decision"),

        },

        allow_ai=allow_ai,

    )

    return conversation, response_payload

def build_ticketless_response(option, description):

    classification = classify_free_text_problem(description)

    response_payload = {

        "mode": "no_ticket",

        "description": description,

        "classification": classification,

    }

    decision = classification.get("decision")

    allow_ai = True

    if option == "4":

        ping_result = run_ping_test("8.8.8.8", 4)

        response_payload["ping_test"] = ping_result

        response_payload["ping_source"] = (

            "destino externo de referencia porque no hay ticket ni IP técnica del cliente"

        )

        if ping_result.get("success"):

            conversation = (

                "La prueba de conexión desde el agente respondió correctamente ✅\n\n"

                "Esto valida la salida a Internet de la VM del agente, no directamente tu módem. "

                "Para revisar tu servicio específico necesito un ticket o información técnica adicional."

            )

        else:

            conversation = "La prueba de conexión desde el agente falló. Te recomiendo contactar soporte."

        logger.info(

            f"PING_TEST | mode=no_ticket | host={ping_result.get('host')} | "

            f"success={ping_result.get('success')}"

        )

        allow_ai = False

    elif option == "5":

        if decision == "ESCALAR_TECNICO":

            escalation_payload = build_ticketless_escalation_payload(description, classification)

            response_payload["escalation_intent"] = escalation_payload

            conversation = (

                "Por lo que describes, podría requerirse revisión técnica.\n\n"

                "Como no tengo un número de ticket, no puedo registrar el escalamiento directamente en la API. "

                "Te recomiendo levantar un ticket o compartir tu folio para registrar la escalación."

            )

        else:

            conversation = (

                "Con la información proporcionada, primero recomiendo una revisión básica o contactar soporte. "

                "Si hay luz roja, falta de señal o corte total, solicita revisión técnica."

            )

        allow_ai = False

    elif option == "6":

        local_modification = save_local_modification(

            "support_request_no_ticket",

            description,

            ticket=None,

            extra={"classification": classification},

        )

        response_payload["local_modification"] = local_modification

        conversation = (

            "Listo ✅ Registré una solicitud local de soporte.\n"

            "Como no tengo número de ticket, no se modificó la API ni el dataset original."

        )

        allow_ai = False

    elif decision == "DIAGNOSTICO_REMOTO":

        conversation = (

            "Parece que tu servicio está lento o intermitente.\n\n"

            "Probemos primero esto:\n"

            "1. Revisa que el módem esté encendido.\n"

            "2. Confirma que las luces estén estables.\n"

            "3. Reinícialo durante 30 segundos.\n\n"

            "Si sigue igual, conviene levantar o escalar un reporte."

        )

    elif decision == "ESCALAR_TECNICO":

        conversation = (

            "Por lo que describes, puede ser necesaria una revisión técnica.\n\n"

            "Si ves luz roja, no tienes señal o ya reiniciaste varias veces sin mejora, lo mejor es levantar un ticket."

        )

        allow_ai = False

    else:

        conversation = (

            "Esto parece requerir revisión de soporte.\n"

            "Te recomiendo compartir más detalles o contactar a un agente."

        )

    logger.info(

        f"WHATSAPP_FLOW | mode=no_ticket | option={option} | "

        f"decision={classification.get('decision')} | category={classification.get('category')}"

    )

    conversation = apply_ai_if_safe(

        conversation,

        {

            "mode": "no_ticket",

            "description": description,

            "decision": classification.get("decision"),

            "category": classification.get("category"),

        },

        allow_ai=allow_ai,

    )

    return conversation, response_payload

@app.route("/", methods=["GET"])

def home():

    return render_template_string(

        HTML,

        user_message=None,

        bot_message=None,

        result=None,

    )

@app.route("/whatsapp", methods=["POST"])

def whatsapp():

    message = request.form.get("message", "").strip()

    ticket_identifier = extract_ticket_identifier(message)

    option = infer_option_from_message(message, has_ticket=bool(ticket_identifier.get("value")))

    ticket, error = get_ticket_or_none(ticket_identifier)

    if error:

        bot_message, response_payload = build_ticketless_response(option, message)

        response_payload["ticket_lookup_error"] = error

    elif ticket:

        bot_message, response_payload = build_ticket_based_response(option, ticket)

    else:

        bot_message, response_payload = build_ticketless_response(option, message)

    return render_template_string(

        HTML,

        user_message=message,

        bot_message=bot_message,

        result=json.dumps(response_payload, indent=4, ensure_ascii=False),

    )

@app.route("/api/whatsapp", methods=["POST"])

def api_whatsapp():

    data = request.get_json() or {}

    message = data.get("message", "").strip()

    ticket_identifier = extract_ticket_identifier(message)

    option = infer_option_from_message(message, has_ticket=bool(ticket_identifier.get("value")))

    ticket, error = get_ticket_or_none(ticket_identifier)

    if error:

        bot_message, response_payload = build_ticketless_response(option, message)

        response_payload["ticket_lookup_error"] = error

    elif ticket:

        bot_message, response_payload = build_ticket_based_response(option, ticket)

    else:

        bot_message, response_payload = build_ticketless_response(option, message)

    return jsonify(

        {

            "message": message,

            "inferred_option": option,

            "ticket_identifier": ticket_identifier,

            "chatbot_message": bot_message,

            "technical_detail": response_payload,

        }

    )

@app.route("/health", methods=["GET"])

def health():

    return jsonify({"status": "ok", "service": "gns-whatsapp-chatbot"})

@app.route("/api/chatbot", methods=["POST"])

def api_chatbot():

    data = request.get_json() or {}

    message = data.get("message") or data.get("description") or data.get("ticket_number") or ""

    ticket_identifier = extract_ticket_identifier(message)

    option = str(

        data.get("option")

        or infer_option_from_message(message, has_ticket=bool(ticket_identifier.get("value")))

    )

    ticket, error = get_ticket_or_none(ticket_identifier)

    if error:

        bot_message, response_payload = build_ticketless_response(option, message)

        response_payload["ticket_lookup_error"] = error

    elif ticket:

        bot_message, response_payload = build_ticket_based_response(option, ticket)

    else:

        bot_message, response_payload = build_ticketless_response(option, message)

    return jsonify({"chatbot_message": bot_message, "technical_detail": response_payload})

@app.route("/api/summary", methods=["GET"])

def api_summary():

    tickets, tickets_status = get_tickets()

    categories, categories_status = get_categories()

    logger.info(f"API_CALL | GET tickets | HTTP={tickets_status}")

    logger.info(f"API_CALL | GET categories | HTTP={categories_status}")

    open_tickets = [t for t in tickets if str(t.get("status")).lower() == "abierto"]

    return jsonify(

        {

            "total_tickets": len(tickets),

            "open_tickets": len(open_tickets),

            "categories_available": len(categories),

            "status": "summary_generated",

        }

    )

if __name__ == "__main__":

    port = int(os.getenv("APP_PORT", 5000))

    app.run(host="0.0.0.0", port=port, debug=True)

