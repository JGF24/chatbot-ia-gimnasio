// =========================================
// CHATBOT DE FORJA GYM
// - Modo IA: si hay un servidor con /api/chat (chatbot-ia/servidor.py),
//   las respuestas las genera Claude con la información del gimnasio.
// - Modo demo: si no hay servidor (por ejemplo en GitHub Pages),
//   responde con reglas sencillas por palabras clave.
// =========================================
(function () {
  // Si el servidor del chat está en otro dominio, define antes de cargar este archivo:
  //   <script>window.CHATBOT_SERVIDOR = "https://mi-servidor.com";</script>
  const SERVIDOR = (window.CHATBOT_SERVIDOR || "").replace(/\/$/, "");
  const API = SERVIDOR + "/api/chat";
  let modoIA = false;
  let hayServidor = false; // ¿Se pueden guardar contactos?
  let ultimaPregunta = "";  // Se guarda junto al contacto para dar contexto al negocio
  let historial = []; // [{ role: "user" | "assistant", content: "..." }]

  // ---------- 1. Crear el HTML del widget ----------
  document.body.insertAdjacentHTML("beforeend", `
    <button class="chat-boton" id="chatBoton" aria-label="Abrir chat">💬<span class="chat-boton__aviso"></span></button>
    <section class="chat" id="chat" aria-label="Asistente virtual" aria-hidden="true">
      <header class="chat__cabecera">
        <div class="chat__avatar">🏋️</div>
        <div class="chat__titulo">
          <strong>Asistente Forja Gym</strong>
          <span class="chat__modo" id="chatModo">Conectando…</span>
        </div>
        <button class="chat__cerrar" id="chatCerrar" aria-label="Cerrar chat">×</button>
      </header>
      <div class="chat__mensajes" id="chatMensajes" aria-live="polite"></div>
      <div class="chat__sugerencias" id="chatSugerencias">
        <button class="chip chip--destacado" id="chatLlamar">📞 Que me llamen</button>
        <button class="chip">¿Qué precios tenéis?</button>
        <button class="chip">Horario de clases</button>
        <button class="chip">¿Cómo me apunto?</button>
        <button class="chip">¿Dónde estáis?</button>
      </div>
      <form class="chat__form" id="chatForm">
        <input id="chatInput" type="text" placeholder="Escribe tu pregunta…" autocomplete="off" maxlength="500">
        <button type="submit" id="chatEnviar" aria-label="Enviar">➤</button>
      </form>
    </section>
  `);

  const $ = (id) => document.getElementById(id);
  const chat = $("chat"), mensajes = $("chatMensajes"), input = $("chatInput"), enviar = $("chatEnviar");

  // ---------- 2. Abrir / cerrar ----------
  function alternar(abrir) {
    chat.classList.toggle("abierto", abrir);
    chat.setAttribute("aria-hidden", !abrir);
    if (abrir) {
      $("chatBoton").querySelector(".chat-boton__aviso")?.remove();
      setTimeout(() => input.focus(), 250);
    }
  }
  $("chatBoton").addEventListener("click", () => alternar(!chat.classList.contains("abierto")));
  $("chatCerrar").addEventListener("click", () => alternar(false));

  // ---------- 3. Pintar mensajes ----------
  function pintar(texto, quien) {
    const div = document.createElement("div");
    div.className = `msg msg--${quien}`;
    div.textContent = texto; // textContent evita inyectar HTML
    mensajes.appendChild(div);
    mensajes.scrollTop = mensajes.scrollHeight;
    return div;
  }

  function mostrarEscribiendo() {
    const div = pintar("", "bot");
    div.innerHTML = '<span class="escribiendo"><span></span><span></span><span></span></span>';
    return div;
  }

  // ---------- 4. Respuestas del modo demo ----------
  const REGLAS = [
    { claves: ["precio", "cuesta", "cuota", "tarifa", "plan", "pagar", "€"],
      respuesta: "Tenemos 3 planes sin matrícula ni permanencia:\n• Básico: 29€/mes (sala, de 6:00 a 23:00)\n• Premium: 45€/mes (24/7 + clases + wellness)\n• Élite: 79€/mes (todo + entrenador personal y nutrición)\n\n¡Y la primera semana es gratis!" },
    { claves: ["horario", "clase", "spinning", "yoga", "boxeo", "hiit", "pilates"],
      respuesta: "Tenemos más de 40 clases a la semana: HIIT, spinning, yoga, pilates, boxeo, cross training y powerlifting. Puedes ver el horario completo en la sección «Horario» de esta página 👆" },
    { claves: ["abierto", "abre", "cierra", "hora", "24"],
      respuesta: "Estamos abiertos 24 horas, 7 días a la semana (el plan Básico da acceso de 6:00 a 23:00)." },
    { claves: ["apunt", "inscrib", "alta", "prueba", "gratis", "empezar"],
      respuesta: "¡Genial! Rellena el formulario de «Prueba gratis» al final de la página y te llamamos en menos de 24 horas para organizar tu semana gratuita 💪" },
    { claves: ["donde", "dónde", "direcc", "ubica", "llegar"],
      respuesta: "Estamos en Calle Ejemplo 123, Madrid Centro. También puedes llamarnos al 600 000 000." },
    { claves: ["entrenador", "personal", "monitor"],
      respuesta: "Nuestro equipo: Laura (fuerza y powerlifting), David (HIIT y cross training), Sara (yoga y movilidad) y Álex (boxeo y nutrición). El plan Élite incluye 4 sesiones de entrenador personal al mes." },
    { claves: ["hola", "buenas", "hey"],
      respuesta: "¡Hola! 👋 ¿En qué te puedo ayudar? Pregúntame por precios, horarios o cómo apuntarte." },
    { claves: ["gracias"],
      respuesta: "¡A ti! Si tienes más dudas, aquí estoy 💪" },
  ];

  function respuestaDemo(texto) {
    const t = texto.toLowerCase();
    const regla = REGLAS.find((r) => r.claves.some((c) => t.includes(c)));
    return regla ? regla.respuesta
      : "No estoy seguro de eso 🤔. Puedo ayudarte con precios, horarios, clases, entrenadores o cómo apuntarte. Para otras dudas, llámanos al 600 000 000.";
  }

  // ---------- 5. Enviar una pregunta ----------
  async function preguntar(texto) {
    texto = texto.trim();
    if (!texto) return;
    ultimaPregunta = texto;
    pintar(texto, "usuario");
    input.value = "";
    enviar.disabled = true;
    const burbuja = mostrarEscribiendo();

    let respuesta;
    if (modoIA) {
      try {
        const res = await fetch(API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mensajes: [...historial, { role: "user", content: texto }] }),
        });
        const datos = await res.json();
        if (res.status === 503) { // El servidor no tiene IA configurada: pasamos a modo demo
          modoIA = false;
          $("chatModo").textContent = "● En línea · Modo demo";
        }
        if (!res.ok) throw new Error(datos.error || "Error del servidor");
        respuesta = datos.respuesta;
        historial.push({ role: "user", content: texto }, { role: "assistant", content: respuesta });
        historial = historial.slice(-20); // Solo recordamos los últimos 20 mensajes
      } catch (e) {
        console.warn("Fallo de la IA, uso respuesta demo:", e);
        respuesta = respuestaDemo(texto);
      }
    } else {
      await new Promise((r) => setTimeout(r, 600)); // Pequeña pausa para que parezca natural
      respuesta = respuestaDemo(texto);
    }

    burbuja.textContent = respuesta;
    mensajes.scrollTop = mensajes.scrollHeight;
    enviar.disabled = false;
    input.focus();
  }

  $("chatForm").addEventListener("submit", (e) => { e.preventDefault(); preguntar(input.value); });
  $("chatSugerencias").addEventListener("click", (e) => {
    if (e.target.id === "chatLlamar") return mostrarFormularioContacto();
    if (e.target.classList.contains("chip")) preguntar(e.target.textContent);
  });

  // ---------- 6. Formulario «Que me llamen» ----------
  function mostrarFormularioContacto() {
    if (document.getElementById("chatContacto")) return; // Ya está abierto
    const caja = pintar("", "bot");
    caja.id = "chatContacto";
    caja.style.whiteSpace = "normal";
    caja.innerHTML = `
      <strong>Déjanos tus datos y te llamamos</strong>
      <form class="chat-contacto" novalidate>
        <input name="nombre" type="text" placeholder="Tu nombre" maxlength="80" autocomplete="name">
        <input name="contacto" type="text" placeholder="Teléfono o email" maxlength="120">
        <small class="chat-contacto__error"></small>
        <button type="submit">Enviar</button>
      </form>`;
    mensajes.scrollTop = mensajes.scrollHeight;
    const formulario = caja.querySelector("form");
    const error = caja.querySelector(".chat-contacto__error");

    formulario.addEventListener("submit", async (e) => {
      e.preventDefault();
      const nombre = formulario.nombre.value.trim();
      const contacto = formulario.contacto.value.trim();
      const esEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contacto);
      const esTelefono = /^[0-9\s+()-]{9,20}$/.test(contacto);
      if (nombre.length < 2) return (error.textContent = "Escribe tu nombre.");
      if (!esEmail && !esTelefono) return (error.textContent = "Escribe un teléfono o un email válido.");
      error.textContent = "";

      if (!hayServidor) { // Demo sin servidor: no se guarda nada
        caja.removeAttribute("id");
        caja.textContent = `¡Gracias, ${nombre}! En esta demo tus datos no se guardan; en una web real te llamaríamos en menos de 24 horas.`;
        return;
      }
      formulario.querySelector("button").disabled = true;
      try {
        const res = await fetch(SERVIDOR + "/api/contacto", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nombre, contacto, mensaje: ultimaPregunta }),
        });
        const datos = await res.json();
        if (!res.ok) throw new Error(datos.error || "No se pudo enviar");
        caja.removeAttribute("id");
        caja.textContent = `¡Gracias, ${nombre}! Te llamaremos en menos de 24 horas.`;
      } catch (err) {
        error.textContent = err.message || "No se pudo enviar. Inténtalo de nuevo.";
        formulario.querySelector("button").disabled = false;
      }
    });
    formulario.nombre.focus();
  }

  // ---------- 7. ¿Hay servidor con IA? ----------
  fetch(SERVIDOR + "/api/estado")
    .then((r) => (r.ok ? r.json() : Promise.reject()))
    .then((d) => { modoIA = !!d.ia; hayServidor = !!d.contactos; })
    .catch(() => { modoIA = false; hayServidor = false; })
    .finally(() => {
      $("chatModo").textContent = modoIA ? "● En línea · Responde con IA" : "● En línea · Modo demo";
      pintar("¡Hola! 👋 Soy el asistente de Forja Gym. ¿En qué te puedo ayudar?", "bot");
    });
})();
