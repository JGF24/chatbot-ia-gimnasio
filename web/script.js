// =========================================
// 1. CABECERA: cambia de estilo al hacer scroll
// =========================================
const header = document.getElementById("header");
window.addEventListener("scroll", () => {
  header.classList.toggle("scrolled", window.scrollY > 50);
});

// =========================================
// 2. MENÚ MÓVIL (botón hamburguesa)
// =========================================
const menuToggle = document.getElementById("menuToggle");
const nav = document.getElementById("nav");

menuToggle.addEventListener("click", () => {
  const abierto = nav.classList.toggle("open");
  menuToggle.classList.toggle("open", abierto);
  menuToggle.setAttribute("aria-expanded", abierto);
});

// Cerrar el menú al pulsar un enlace
nav.querySelectorAll("a").forEach((enlace) => {
  enlace.addEventListener("click", () => {
    nav.classList.remove("open");
    menuToggle.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", false);
  });
});

// =========================================
// 3. HORARIO: datos de las clases por día
// =========================================
const horario = {
  lunes: [
    { hora: "07:00", clase: "HIIT Express", monitor: "David Ruiz" },
    { hora: "10:00", clase: "Yoga Flow", monitor: "Sara Gómez" },
    { hora: "18:30", clase: "Spinning", monitor: "David Ruiz" },
    { hora: "20:00", clase: "Boxeo", monitor: "Álex Pérez" },
  ],
  martes: [
    { hora: "07:30", clase: "Fuerza total", monitor: "Laura Martín" },
    { hora: "12:00", clase: "Movilidad", monitor: "Sara Gómez" },
    { hora: "19:00", clase: "Cross Training", monitor: "David Ruiz" },
  ],
  miercoles: [
    { hora: "07:00", clase: "HIIT Express", monitor: "David Ruiz" },
    { hora: "10:00", clase: "Pilates", monitor: "Sara Gómez" },
    { hora: "18:30", clase: "Powerlifting", monitor: "Laura Martín" },
    { hora: "20:00", clase: "Boxeo", monitor: "Álex Pérez" },
  ],
  jueves: [
    { hora: "07:30", clase: "Fuerza total", monitor: "Laura Martín" },
    { hora: "18:00", clase: "Spinning", monitor: "David Ruiz" },
    { hora: "19:30", clase: "Yoga Flow", monitor: "Sara Gómez" },
  ],
  viernes: [
    { hora: "07:00", clase: "HIIT Express", monitor: "David Ruiz" },
    { hora: "17:00", clase: "Boxeo", monitor: "Álex Pérez" },
    { hora: "19:00", clase: "Cross Training", monitor: "David Ruiz" },
  ],
  sabado: [
    { hora: "10:00", clase: "Entreno funcional", monitor: "Laura Martín" },
    { hora: "11:30", clase: "Yoga Flow", monitor: "Sara Gómez" },
  ],
};

const lista = document.getElementById("schedule");
const pestanas = document.querySelectorAll(".tab");

function mostrarDia(dia) {
  // Generamos un <li> por cada clase del día
  lista.innerHTML = horario[dia]
    .map(
      (c, i) => `
      <li style="animation-delay:${i * 0.07}s">
        <span class="hora">${c.hora}</span>
        <span class="clase">${c.clase}</span>
        <span class="monitor">${c.monitor}</span>
      </li>`
    )
    .join("");
}

pestanas.forEach((tab) => {
  tab.addEventListener("click", () => {
    pestanas.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    mostrarDia(tab.dataset.day);
  });
});

mostrarDia("lunes"); // Día que se muestra al cargar

// =========================================
// 4. ANIMACIONES AL HACER SCROLL + CONTADORES
// =========================================
const observador = new IntersectionObserver(
  (entradas) => {
    entradas.forEach((entrada) => {
      if (entrada.isIntersecting) {
        entrada.target.classList.add("visible");
        observador.unobserve(entrada.target);
      }
    });
  },
  { threshold: 0.15 }
);
document.querySelectorAll(".reveal").forEach((el) => observador.observe(el));

// Contadores animados del hero (+1200 socios, etc.)
function animarContador(el) {
  const objetivo = Number(el.dataset.count);
  const duracion = 1500;
  const inicio = performance.now();

  function paso(ahora) {
    const progreso = Math.min((ahora - inicio) / duracion, 1);
    el.textContent = Math.floor(progreso * objetivo).toLocaleString("es-ES");
    if (progreso < 1) requestAnimationFrame(paso);
  }
  requestAnimationFrame(paso);
}
document.querySelectorAll("[data-count]").forEach(animarContador);

// =========================================
// 5. VALIDACIÓN DEL FORMULARIO
// =========================================
const form = document.getElementById("contactForm");
const mensajeOk = document.getElementById("formSuccess");

const validaciones = {
  nombre: (v) => (v.trim().length >= 2 ? "" : "Escribe tu nombre."),
  email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? "" : "Introduce un email válido."),
  telefono: (v) => (/^[0-9\s+]{9,15}$/.test(v) ? "" : "Introduce un teléfono válido."),
};

form.addEventListener("submit", (e) => {
  e.preventDefault(); // Evita que la página se recargue
  let todoCorrecto = true;

  Object.keys(validaciones).forEach((campo) => {
    const input = form.elements[campo];
    const error = validaciones[campo](input.value);
    input.classList.toggle("invalid", !!error);
    input.nextElementSibling.textContent = error;
    if (error) todoCorrecto = false;
  });

  if (todoCorrecto) {
    // En un proyecto real aquí se enviarían los datos (por ejemplo, con Formspree o un backend)
    mensajeOk.hidden = false;
    form.reset();
    setTimeout(() => (mensajeOk.hidden = true), 5000);
  }
});

// =========================================
// 6. AÑO ACTUAL EN EL PIE
// =========================================
document.getElementById("year").textContent = new Date().getFullYear();
