"""
SERVIDOR DEL CHATBOT CON IA (Claude)
====================================
- Sirve la web del gimnasio (carpeta web/).
- /api/chat: recibe la conversación y responde usando Claude con la
  información de conocimiento.md.
- /api/contacto: guarda en contactos.csv los datos de quien pide que le llamen.
- La clave de la API se queda en el servidor: nunca llega al navegador.

Uso en local:
  1. Configura tu clave:   $env:ANTHROPIC_API_KEY = "tu-clave"     (PowerShell)
  2. Arranca el servidor:  python servidor.py
  3. Abre:                 http://localhost:8000

En un hosting (Render, Railway, un VPS...) se configura con variables de entorno:
  ANTHROPIC_API_KEY    clave de la API
  PORT                 puerto que asigna el hosting (activa la escucha pública)
  ORIGENES_PERMITIDOS  webs que pueden usar el chat, separadas por comas
                       (ej.: https://www.minegocio.com). Solo hace falta si la
                       web está en un dominio distinto al de este servidor.
"""
import argparse
import csv
import json
import os
import re
import smtplib
import threading
import time
import urllib.request
from collections import defaultdict, deque
from datetime import datetime
from email.message import EmailMessage
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

BASE = Path(__file__).parent
CARPETA_WEB = BASE / "web"
CONOCIMIENTO = (BASE / "conocimiento.md").read_text(encoding="utf-8")
ARCHIVO_CONTACTOS = Path(os.environ.get("ARCHIVO_CONTACTOS", BASE / "contactos.csv"))

MODELO = "claude-opus-5-5"
MAX_MENSAJES = 20        # Historial máximo que aceptamos
MAX_CARACTERES = 1000    # Longitud máxima de cada mensaje
MAX_CUERPO = 50_000      # Bytes máximos de una petición

# Límite de uso por visitante (controla el gasto y evita abusos)
VENTANA_SEGUNDOS = 600
LIMITE_CHAT = 20         # preguntas cada 10 minutos
LIMITE_CONTACTO = 5      # formularios cada 10 minutos

ORIGENES_PERMITIDOS = {o.strip().rstrip("/") for o in os.environ.get("ORIGENES_PERMITIDOS", "").split(",") if o.strip()}

# Dónde reenviar cada contacto para conservarlo fuera del servidor (opcional)
WEBHOOK_CONTACTOS = os.environ.get("WEBHOOK_CONTACTOS", "").strip()
CORREO_DESTINO = os.environ.get("CORREO_DESTINO", "").strip()
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PUERTO = int(os.environ.get("SMTP_PUERTO", 587))
SMTP_USUARIO = os.environ.get("SMTP_USUARIO", "").strip()
SMTP_CLAVE = os.environ.get("SMTP_CLAVE", "")
SMTP_SEGURIDAD = os.environ.get("SMTP_SEGURIDAD", "starttls").strip().lower()  # starttls | ssl | ninguna

SISTEMA = f"""Eres el asistente virtual de la web de Forja Gym. Hablas con personas que visitan la web:
posibles socios y socios actuales.

Responde siempre en el idioma del usuario, con un tono cercano y motivador, en 1 a 4 frases cortas.
Usa solo la información de abajo. Si te preguntan algo que no aparece (por ejemplo, ofertas
que no existen o temas médicos), dilo con naturalidad y ofrece el teléfono o el email del gimnasio.
Cuando encaje, invita a pedir la primera semana gratis con el formulario de la web, o a dejar
sus datos con el botón «Que me llamen» del chat.
No uses Markdown (ni asteriscos ni almohadillas): la respuesta se muestra como texto plano.

<informacion_del_gimnasio>
{CONOCIMIENTO}
</informacion_del_gimnasio>"""

try:
    cliente = anthropic.Anthropic()  # Lee ANTHROPIC_API_KEY del entorno
    IA_DISPONIBLE = True
except Exception as e:  # Sin credenciales: la web funcionará en modo demo
    print(f"⚠️  IA no disponible ({e}). El chat funcionará en modo demo.")
    cliente, IA_DISPONIBLE = None, False


# ---------------------------------------------------------------
# IA
# ---------------------------------------------------------------
def responder(mensajes: list[dict]) -> str:
    """Envía la conversación a Claude y devuelve el texto de la respuesta."""
    respuesta = cliente.beta.messages.create(
        model=MODELO,
        max_tokens=2048,
        system=SISTEMA,
        messages=mensajes,
        output_config={"effort": "low"},  # Preguntas sencillas: respuesta rápida y barata
        # Si el modelo rechaza la petición, la API la reintenta sola con otro modelo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        return "Lo siento, con eso no puedo ayudarte. Para cualquier duda, llámanos al 600 000 000."
    texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
    return texto or "Perdona, no te he entendido. ¿Puedes repetirlo?"


def validar_chat(datos) -> list[dict]:
    """Comprueba que la conversación que llega del navegador tiene un formato seguro."""
    mensajes = datos.get("mensajes") if isinstance(datos, dict) else None
    if not isinstance(mensajes, list) or not mensajes:
        raise ValueError("Falta la conversación.")
    mensajes = mensajes[-MAX_MENSAJES:]
    limpios = []
    for m in mensajes:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            raise ValueError("Mensaje con formato incorrecto.")
        contenido = m.get("content")
        if not isinstance(contenido, str) or not contenido.strip():
            raise ValueError("Mensaje vacío.")
        limpios.append({"role": m["role"], "content": contenido[:MAX_CARACTERES]})
    while limpios and limpios[0]["role"] != "user":  # La API exige empezar por el usuario
        limpios.pop(0)
    if not limpios or limpios[-1]["role"] != "user":
        raise ValueError("El último mensaje debe ser del usuario.")
    return limpios


# ---------------------------------------------------------------
# CONTACTOS
# ---------------------------------------------------------------
RE_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RE_TELEFONO = re.compile(r"^[0-9\s+()-]{9,20}$")
candado_csv = threading.Lock()


def texto_seguro(valor: str, maximo: int) -> str:
    """Limpia un texto antes de guardarlo: sin saltos de línea y sin fórmulas de Excel."""
    valor = " ".join(str(valor).split())[:maximo]
    if valor[:1] in ("=", "+", "-", "@"):  # Evita que Excel lo ejecute como fórmula
        valor = "'" + valor
    return valor


def validar_contacto(datos) -> dict:
    if not isinstance(datos, dict):
        raise ValueError("Formato incorrecto.")
    nombre = str(datos.get("nombre", "")).strip()
    contacto = str(datos.get("contacto", "")).strip()
    if not 2 <= len(nombre) <= 80:
        raise ValueError("Escribe tu nombre.")
    if not (RE_EMAIL.match(contacto) or RE_TELEFONO.match(contacto)):
        raise ValueError("Escribe un teléfono o un email válido.")
    return {
        "nombre": texto_seguro(nombre, 80),
        "contacto": contacto[:120],  # Ya validado: no puede ser una fórmula peligrosa salvo '+34...'
        "mensaje": texto_seguro(datos.get("mensaje", ""), 500),
    }


def guardar_contacto(c: dict):
    """Añade una fila a contactos.csv (lo crea con cabecera si no existe)."""
    with candado_csv:
        nuevo = not ARCHIVO_CONTACTOS.exists()
        with ARCHIVO_CONTACTOS.open("a", newline="", encoding="utf-8-sig") as f:
            escritor = csv.writer(f, delimiter=";")
            if nuevo:
                escritor.writerow(["Fecha", "Nombre", "Contacto", "Mensaje"])
            escritor.writerow([datetime.now().strftime("%d/%m/%Y %H:%M"), c["nombre"],
                               "'" + c["contacto"] if c["contacto"].startswith("+") else c["contacto"],
                               c["mensaje"]])


def enviar_a_webhook(c: dict):
    """Envía el contacto a una URL (Google Sheets con Apps Script, Zapier, Make, n8n...)."""
    datos = json.dumps({"fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), **c}, ensure_ascii=False).encode("utf-8")
    peticion = urllib.request.Request(WEBHOOK_CONTACTOS, data=datos, method="POST",
                                      headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        respuesta.read()


def enviar_por_email(c: dict):
    """Envía el contacto por correo al negocio usando su servidor SMTP."""
    correo = EmailMessage()
    correo["Subject"] = f"Nuevo contacto desde el chat: {c['nombre']}"
    correo["From"] = SMTP_USUARIO or CORREO_DESTINO
    correo["To"] = CORREO_DESTINO
    correo.set_content(
        f"Alguien ha pedido que le llamen desde el chat de la web.\n\n"
        f"Nombre:   {c['nombre']}\n"
        f"Contacto: {c['contacto']}\n"
        f"Pregunta: {c['mensaje'] or '(sin pregunta previa)'}\n"
        f"Fecha:    {datetime.now():%d/%m/%Y %H:%M}\n"
    )
    if SMTP_SEGURIDAD == "ssl":
        conexion = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PUERTO, timeout=15)
    else:
        conexion = smtplib.SMTP(SMTP_HOST, SMTP_PUERTO, timeout=15)
    with conexion:
        if SMTP_SEGURIDAD == "starttls":
            conexion.starttls()
        if SMTP_USUARIO:
            conexion.login(SMTP_USUARIO, SMTP_CLAVE)
        conexion.send_message(correo)


def avisar_contacto(c: dict):
    """Reenvía el contacto fuera del servidor para que no se pierda si el hosting se reinicia.
    Se ejecuta en segundo plano: el visitante no espera y un fallo aquí no rompe el chat."""
    for nombre, activo, funcion in (("webhook", bool(WEBHOOK_CONTACTOS), enviar_a_webhook),
                                    ("email", bool(SMTP_HOST and CORREO_DESTINO), enviar_por_email)):
        if not activo:
            continue
        try:
            funcion(c)
            print(f"📤 Contacto enviado por {nombre}", flush=True)
        except Exception as e:
            print(f"❌ No se pudo enviar el contacto por {nombre}: {e!r}", flush=True)


# ---------------------------------------------------------------
# LÍMITE DE USO POR VISITANTE
# ---------------------------------------------------------------
usos = defaultdict(deque)
candado_usos = threading.Lock()


def permitido(ip: str, tipo: str, limite: int) -> bool:
    """Devuelve False si esta IP ha superado el límite en los últimos 10 minutos."""
    ahora = time.monotonic()
    with candado_usos:
        cola = usos[(ip, tipo)]
        while cola and ahora - cola[0] > VENTANA_SEGUNDOS:
            cola.popleft()
        if len(cola) >= limite:
            return False
        cola.append(ahora)
        return True


# ---------------------------------------------------------------
# SERVIDOR HTTP
# ---------------------------------------------------------------
class Manejador(SimpleHTTPRequestHandler):
    def cabeceras_cors(self):
        """Permite que una web en otro dominio (el del cliente) use este servidor."""
        origen = (self.headers.get("Origin") or "").rstrip("/")
        if origen and origen in ORIGENES_PERMITIDOS:
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Vary", "Origin")

    def enviar_json(self, codigo: int, datos: dict):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.cabeceras_cors()
        self.end_headers()
        self.wfile.write(cuerpo)

    def ip_cliente(self) -> str:
        # Detrás de un hosting, la IP real llega en X-Forwarded-For
        reenviada = self.headers.get("X-Forwarded-For", "")
        return reenviada.split(",")[0].strip() or self.client_address[0]

    def leer_json(self):
        longitud = int(self.headers.get("Content-Length", 0))
        if longitud > MAX_CUERPO:
            raise OverflowError
        return json.loads(self.rfile.read(longitud))

    def do_OPTIONS(self):  # Petición previa que hace el navegador con CORS
        self.send_response(204)
        self.cabeceras_cors()
        self.end_headers()

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/estado":
            return self.enviar_json(200, {"ia": IA_DISPONIBLE, "contactos": True})
        if ruta.startswith("/api/"):
            return self.enviar_json(404, {"error": "No encontrado"})
        return super().do_GET()  # Archivos de la web (index.html, styles.css…)

    def do_POST(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/chat":
            return self.post_chat()
        if ruta == "/api/contacto":
            return self.post_contacto()
        return self.enviar_json(404, {"error": "No encontrado"})

    def post_contacto(self):
        if not permitido(self.ip_cliente(), "contacto", LIMITE_CONTACTO):
            return self.enviar_json(429, {"error": "Demasiados envíos, prueba más tarde"})
        try:
            contacto = validar_contacto(self.leer_json())
        except OverflowError:
            return self.enviar_json(413, {"error": "Mensaje demasiado largo"})
        except json.JSONDecodeError:
            return self.enviar_json(400, {"error": "Formato incorrecto."})
        except ValueError as e:
            return self.enviar_json(400, {"error": str(e)})
        try:
            guardar_contacto(contacto)
        except OSError as e:
            print(f"❌ No se pudo guardar el contacto: {e!r}")
            return self.enviar_json(500, {"error": "No se pudo guardar"})
        print(f"📇 Nuevo contacto guardado: {contacto['nombre']}", flush=True)
        threading.Thread(target=avisar_contacto, args=(contacto,), daemon=True).start()
        return self.enviar_json(200, {"ok": True})

    def post_chat(self):
        global IA_DISPONIBLE
        if not IA_DISPONIBLE:
            return self.enviar_json(503, {"error": "IA no configurada"})
        if not permitido(self.ip_cliente(), "chat", LIMITE_CHAT):
            return self.enviar_json(429, {"error": "Has hecho muchas preguntas seguidas, prueba en unos minutos"})
        try:
            mensajes = validar_chat(self.leer_json())
        except OverflowError:
            return self.enviar_json(413, {"error": "Mensaje demasiado largo"})
        except json.JSONDecodeError:
            return self.enviar_json(400, {"error": "Formato incorrecto."})
        except ValueError as e:
            return self.enviar_json(400, {"error": str(e)})

        try:
            return self.enviar_json(200, {"respuesta": responder(mensajes)})
        except TypeError as e:
            # El SDK lanza TypeError si no encuentra ninguna credencial (no hay ANTHROPIC_API_KEY)
            if "authentication" not in str(e).lower():
                raise
            print("⚠️  No hay clave de API configurada: el chat pasa a modo demo.")
            IA_DISPONIBLE = False
            return self.enviar_json(503, {"error": "IA no configurada"})
        except anthropic.AuthenticationError:
            print("❌ La clave de la API no es válida.")
            return self.enviar_json(500, {"error": "Clave de API no válida"})
        except anthropic.RateLimitError:
            return self.enviar_json(429, {"error": "Demasiadas peticiones, prueba en un momento"})
        except anthropic.APIStatusError as e:
            print(f"❌ Error de la API ({e.status_code}): {e.message}")
            return self.enviar_json(502, {"error": "Error del servicio de IA"})
        except anthropic.APIConnectionError:
            return self.enviar_json(502, {"error": "Sin conexión con el servicio de IA"})
        except Exception as e:  # Cualquier otro fallo: respondemos en vez de cortar la conexión
            print(f"❌ Error inesperado: {e!r}")
            return self.enviar_json(500, {"error": "Error interno"})


def main():
    parser = argparse.ArgumentParser(description="Servidor del chatbot de Forja Gym")
    parser.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()

    # En un hosting (variable PORT definida) hay que escuchar en todas las interfaces
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    servidor = ThreadingHTTPServer((host, args.puerto), partial(Manejador, directory=str(CARPETA_WEB)))
    print(f"🏋️  Forja Gym en http://localhost:{args.puerto}  ·  IA: {'activada' if IA_DISPONIBLE else 'modo demo'}", flush=True)
    print("   Pulsa Ctrl+C para parar.", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")


if __name__ == "__main__":
    main()
