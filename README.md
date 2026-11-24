# 🤖 Chatbot con IA para la web de un negocio

Asistente virtual integrado en la web de **Forja Gym** que responde a los clientes 24/7 sobre precios, horarios, clases y cómo apuntarse, y guarda los datos de quien pide que le llamen. Usa la IA de **Claude (Anthropic)** y solo responde con la información real del negocio.

## Qué hace
- **Responde con IA** usando únicamente la información de `conocimiento.md`: no inventa precios ni ofertas, y contesta en el idioma del visitante.
- **Recuerda la conversación** para entender preguntas encadenadas.
- **Guarda contactos**: el botón «Que me llamen» recoge nombre y teléfono o email, y los añade a `contactos.csv` (se abre con Excel).
- **Protege el gasto**: límite de preguntas por visitante y validación de todo lo que llega del navegador.
- **Modo demo**: si no hay servidor (por ejemplo, en GitHub Pages) el widget responde con reglas por palabras clave, así la demo pública siempre funciona.

## Cómo funciona
```
Navegador (chatbot.js)  ──►  servidor.py (/api/chat)  ──►  API de Claude
       ▲                          │  añade conocimiento.md
       └──────── respuesta ◄──────┘  (la clave de la API nunca sale del servidor)
```
| Archivo | Para qué sirve |
|---|---|
| `conocimiento.md` | Todo lo que sabe el bot. Para otro negocio basta con cambiar este archivo. |
| `servidor.py` | Sirve la web, habla con la IA y guarda los contactos. |
| `web/chatbot.js` y `web/chatbot.css` | El widget: botón flotante, burbujas, sugerencias y formulario de contacto. |
| `arrancar.py` | Arranque en local: pide la clave sin mostrarla en pantalla. |
| `render.yaml` | Configuración para desplegarlo en Render. |

## Ponerlo en marcha en local
```powershell
pip install -r requirements.txt
python arrancar.py        # pide la clave de la API (se crea en console.anthropic.com)
```
Abre http://localhost:8000 y pulsa el botón 💬.

## Desplegarlo en un hosting
El servidor se configura con variables de entorno, como piden Render, Railway o un VPS:

| Variable | Uso |
|---|---|
| `ANTHROPIC_API_KEY` | Clave de la API. Nunca se sube al repositorio. |
| `PORT` | Puerto que asigna el hosting. |
| `ORIGENES_PERMITIDOS` | Dominio de la web del cliente, si está en otro servidor (ej.: `https://www.minegocio.com`). |

Para usar el chat desde una web alojada en otro sitio, se añade antes de `chatbot.js`:
```html
<script>window.CHATBOT_SERVIDOR = "https://mi-servidor.com";</script>
```

> En hostings gratuitos el disco se borra al reiniciar: para conservar los contactos hace falta un disco persistente o enviarlos por email o a una hoja de cálculo.

## Tecnologías
Python · API de Claude (SDK oficial `anthropic`) · JavaScript (fetch, DOM) · HTML/CSS
