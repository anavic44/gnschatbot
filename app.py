import os
import json
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

from gns_api import get_tickets, get_comments, get_categories, post_escalation
from agent import (
    find_ticket_by_number,
    generate_diagnosis,
    build_escalation_payload,
    sanitize_ticket,
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
        .card {
            max-width: 850px;
            margin: auto;
            background: #1e293b;
            padding: 30px;
            border-radius: 14px;
        }
        input, button {
            padding: 12px;
            border-radius: 8px;
            border: none;
            margin-top: 10px;
        }
        input {
            width: 70%;
        }
        button {
            background: #10b981;
            color: white;
            cursor: pointer;
            font-weight: bold;
        }
        pre {
            background: #020617;
            padding: 20px;
            border-radius: 10px;
            overflow-x: auto;
            color: #d1fae5;
        }
        .menu {
            background: #0f172a;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .badge {
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">Agente IA - NOC GNS</span>
        <h1>GNS Chatbot Agent</h1>
        <p>Consulta el estado de un ticket y recibe diagnóstico automático de primer nivel.</p>

        <div class="menu">
            <strong>Menú:</strong>
            <ol>
                <li>Consultar estado de ticket</li>
                <li>Diagnóstico básico guiado</li>
                <li>Reinicio de equipo</li>
                <li>Prueba de ping simulada</li>
                <li>Escalamiento automático a técnico</li>
            </ol>
        </div>

        <form method="POST" action="/chat">
            <input type="text" name="ticket_number" placeholder="Ejemplo: TCK794814" required>
            <button type="submit">Consultar</button>
        </form>

        {% if result %}
            <h2>Resultado</h2>
            <pre>{{ result }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML, result=None)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "gns-chatbot-agent"})


@app.route("/chat", methods=["POST"])
def chat():
    if request.is_json:
        ticket_number = request.json.get("ticket_number")
    else:
        ticket_number = request.form.get("ticket_number")

    try:
        tickets, tickets_status = get_tickets()
        logger.info(f"API_CALL | GET tickets | HTTP={tickets_status}")

        ticket = find_ticket_by_number(tickets, ticket_number)

        if not ticket:
            logger.warning(f"TICKET_NOT_FOUND | ticket={ticket_number}")
            result = {
                "error": "Ticket no encontrado",
                "ticket_number": ticket_number,
            }
            return render_template_string(
                HTML,
                result=json.dumps(result, indent=4, ensure_ascii=False)
            )

        safe_ticket = sanitize_ticket(ticket)
        diagnosis = generate_diagnosis(ticket)

        response_payload = {
            "safe_ticket": safe_ticket,
            "diagnosis": diagnosis,
        }

        if diagnosis["decision"] == "ESCALAR_TECNICO":
            escalation_payload = build_escalation_payload(ticket, diagnosis)
            escalation_response, escalation_status = post_escalation(escalation_payload)

            logger.info(
                f"API_CALL | POST escalation | ticket={ticket_number} | HTTP={escalation_status} | payload={escalation_payload}"
            )

            response_payload["escalation"] = {
                "http_status": escalation_status,
                "payload_sent": escalation_payload,
                "api_response": escalation_response,
            }

        return render_template_string(
            HTML,
            result=json.dumps(response_payload, indent=4, ensure_ascii=False)
        )

    except Exception as error:
        logger.exception(f"APP_ERROR | {error}")
        result = {"error": str(error)}
        return render_template_string(
            HTML,
            result=json.dumps(result, indent=4, ensure_ascii=False)
        ), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    ticket_number = data.get("ticket_number")

    tickets, tickets_status = get_tickets()
    logger.info(f"API_CALL | GET tickets | HTTP={tickets_status}")

    ticket = find_ticket_by_number(tickets, ticket_number)

    if not ticket:
        logger.warning(f"TICKET_NOT_FOUND | ticket={ticket_number}")
        return jsonify({
            "error": "Ticket no encontrado",
            "ticket_number": ticket_number
        }), 404

    safe_ticket = sanitize_ticket(ticket)
    diagnosis = generate_diagnosis(ticket)

    response_payload = {
        "safe_ticket": safe_ticket,
        "diagnosis": diagnosis,
    }

    if diagnosis["decision"] == "ESCALAR_TECNICO":
        escalation_payload = build_escalation_payload(ticket, diagnosis)
        escalation_response, escalation_status = post_escalation(escalation_payload)

        logger.info(
            f"API_CALL | POST escalation | ticket={ticket_number} | HTTP={escalation_status} | payload={escalation_payload}"
        )

        response_payload["escalation"] = {
            "http_status": escalation_status,
            "payload_sent": escalation_payload,
            "api_response": escalation_response,
        }

    return jsonify(response_payload)


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
