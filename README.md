# 🤖 Chatbot con IA para la web de un negocio

Asistente virtual integrado en la web de **Forja Gym** que responde a los clientes 24/7 sobre precios, horarios, clases y cómo apuntarse. Usa la IA de **Claude (Anthropic)** y solo responde con la información real del negocio.

## Cómo funciona
```
Navegador (chatbot.js)  ──►  servidor.py (/api/chat)  ──►  API de Claude
       ▲                          │  añade conocimiento.md
       └──────── respuesta ◄──────┘  (la clave de la API nunca sale del servidor)
```
- **`conocimiento.md`**: todo lo que sabe el bot. Para otro cliente basta con cambiar este archivo.
- **`servidor.py`**: sirve la web y hace de intermediario seguro con la API (valida los mensajes, limita su tamaño y gestiona los errores).
- **`web/chatbot.js` y `web/chatbot.css`**: el widget del chat (botón flotante, burbujas, sugerencias rápidas y animación de "escribiendo…").
- **Modo demo**: si no hay servidor (por ejemplo, en GitHub Pages) el widget responde con reglas por palabras clave, así la demo pública siempre funciona.

## Ponerlo en marcha
```powershell
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "tu-clave"      # se crea en console.anthropic.com
python servidor.py
```
Abre http://localhost:8000 y pulsa el botón 💬.

## Para un cliente real
- Desplegar `servidor.py` en un hosting con Python (Render, Railway, un VPS…) y guardar la clave como variable de entorno.
- Añadir un límite de peticiones por usuario para controlar el gasto.
- Ampliaciones: guardar las conversaciones, pasar los contactos interesados a un Excel o CRM, o conectarlo a WhatsApp/Telegram.

## Tecnologías
Python · API de Claude (SDK oficial `anthropic`) · JavaScript (fetch, DOM) · HTML/CSS
