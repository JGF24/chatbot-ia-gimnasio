"""
SERVIDOR DEL CHATBOT CON IA (Claude)
====================================
- Sirve la web del gimnasio (carpeta web/).
- Expone /api/chat: recibe la conversación y responde usando Claude
  con la información de conocimiento.md.
- La clave de la API se queda en el servidor: nunca llega al navegador.

Uso:
  1. Configura tu clave:   $env:ANTHROPIC_API_KEY = "tu-clave"     (PowerShell)
  2. Arranca el servidor:  python servidor.py
  3. Abre:                 http://localhost:8000
"""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

BASE = Path(__file__).parent
# La web está en la carpeta "web" de este repositorio
CARPETA_WEB = BASE / "web"
CONOCIMIENTO = (BASE / "conocimiento.md").read_text(encoding="utf-8")

MODELO = "claude-opus-5-5"
MAX_MENSAJES = 20        # Historial máximo que aceptamos
MAX_CARACTERES = 1000    # Longitud máxima de cada mensaje
MAX_CUERPO = 50_000      # Bytes máximos de una petición

SISTEMA = f"""Eres el asistente virtual de la web de Forja Gym. Hablas con personas que visitan la web:
posibles socios y socios actuales.

Responde siempre en el idioma del usuario, con un tono cercano y motivador, en 1 a 4 frases cortas.
Usa solo la información de abajo. Si te preguntan algo que no aparece (por ejemplo, ofertas
que no existen o temas médicos), dilo con naturalidad y ofrece el teléfono o el email del gimnasio.
Cuando encaje, invita a pedir la primera semana gratis con el formulario de la web.
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


def validar(datos) -> list[dict]:
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


class Manejador(SimpleHTTPRequestHandler):
    def enviar_json(self, codigo: int, datos: dict):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/estado":
            return self.enviar_json(200, {"ia": IA_DISPONIBLE})
        return super().do_GET()  # Archivos de la web (index.html, styles.css…)

    def do_POST(self):
        global IA_DISPONIBLE
        if self.path != "/api/chat":
            return self.enviar_json(404, {"error": "No encontrado"})
        if not IA_DISPONIBLE:
            return self.enviar_json(503, {"error": "IA no configurada"})

        try:
            longitud = int(self.headers.get("Content-Length", 0))
            if longitud > MAX_CUERPO:
                return self.enviar_json(413, {"error": "Mensaje demasiado largo"})
            mensajes = validar(json.loads(self.rfile.read(longitud)))
        except (ValueError, json.JSONDecodeError) as e:
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
    parser.add_argument("--puerto", type=int, default=8000)
    args = parser.parse_args()

    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), partial(Manejador, directory=str(CARPETA_WEB)))
    print(f"🏋️  Forja Gym en http://localhost:{args.puerto}  ·  IA: {'activada' if IA_DISPONIBLE else 'modo demo'}")
    print("   Pulsa Ctrl+C para parar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")


if __name__ == "__main__":
    main()
