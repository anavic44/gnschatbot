# GNS Chatbot Agent

Agente de IA para la gestión y diagnóstico de incidentes residenciales y empresariales de GNS.

## Objetivo

Automatizar soporte técnico de primer nivel mediante un chatbot que consulta tickets desde la API GNS Sandbox, diagnostica incidentes y decide si el caso debe resolverse mediante diagnóstico remoto, revisión por soporte o escalamiento a técnico.

## Infraestructura

- VM desplegada en XenServer
- Sistema operativo: Ubuntu 26.04 LTS
- IP estática: 10.32.66.113
- Gateway: 10.32.66.1
- DNS: 10.32.65.43 y 10.32.65.53
- Puerto de servicio: 5000

## Funciones principales

- Consulta de tickets activos e históricos desde la API GNS Sandbox.
- Diagnóstico autónomo basado en categoría y descripción del ticket.
- Flujo de diagnóstico remoto para velocidad, lentitud e intermitencia.
- Escalamiento automático para corte, luz roja, fibra o falta de señal.
- Generación de payload JSON para escalación.
- Registro persistente de logs de auditoría.
- Interfaz web básica con Flask.

## Reglas de decisión

| Tipo de caso | Acción |
|---|---|
| Problemas de velocidad | Diagnóstico remoto |
| Intermitencia | Diagnóstico remoto |
| Conexión lenta | Diagnóstico remoto |
| Corte de servicio | Escalar a técnico |
| Luz roja / falta de señal | Escalar a técnico |
| Fibra / cobertura crítica | Escalar a técnico |
| Soporte general o administrativo | Revisión por soporte |

## Variables de entorno

Crear archivo `.env`:

```env
GNS_API_BASE_URL=https://app.gns.com.mx/gns-sandbox
GNS_API_USER=usuario
GNS_API_PASSWORD=password
APP_PORT=5000
