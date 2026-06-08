import requests
from logger_config import logger

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"


def looks_bad_ai_response(text):
    """
    Detecta respuestas no útiles o riesgosas generadas por el modelo.
    Si pasa esto, usamos el mensaje base del sistema.
    """
    if not text:
        return True

    lowered = text.lower()

    bad_phrases = [
        "no puedo ayudar",
        "no puedo ayudarte",
        "no tengo suficiente información",
        "consulta con un profesional",
        "lo siento, pero no puedo",
        "no estoy seguro",
        "no puedo realizar",
        "no puedo acceder",
        "por correo electrónico",
        "acordarme de esto"
	"he revisado el estado",
	"las luces están estables",
	"he revisado",
    ]

    return any(phrase in lowered for phrase in bad_phrases)


def generate_customer_response(base_message, context=None):
    """
    Usa Ollama como capa de redacción.
    La decisión técnica ya fue tomada por reglas/API/ping/POST.
    Ollama solo mejora el tono del mensaje para cliente.
    """
    context = context or {}

    prompt = f"""
Eres un asistente virtual de soporte de internet para clientes de GNS.

Tu tarea es REESCRIBIR el mensaje técnico en una respuesta para cliente.

Reglas obligatorias:
- Responde solo en español.
- Sé amable, claro y breve.
- Estilo WhatsApp.
- No afirmes que revisaste el módem, las luces, la red o el servicio si esa información no viene en el mensaje técnico.
- Usa frases como “por favor revisa” o “te sugiero revisar”, no “he revisado”.
- No cambies la decisión técnica.
- No elimines confirmaciones importantes.
- Si el mensaje dice que algo fue registrado, conserva esa confirmación.
- Si el mensaje dice que se escaló un ticket, conserva el número de ticket.
- No digas que no puedes ayudar.
- No pidas enviar correo.
- No menciones que eres un modelo de IA.
- Máximo 80 palabras.

Mensaje técnico original:
{base_message}

Contexto técnico:
{context}

Respuesta final para cliente:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 120
                }
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()
        ai_message = data.get("response", "").strip()

        if looks_bad_ai_response(ai_message):
            logger.warning("AI_RESPONSE | provider=ollama | status=rejected_bad_response")
            return base_message

        logger.info("AI_RESPONSE | provider=ollama | model=llama3.2:1b | status=success")
        return ai_message

    except Exception as error:
        logger.warning(f"AI_RESPONSE | provider=ollama | status=fallback | error={error}")
        return base_message
