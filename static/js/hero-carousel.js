/* Banner de ofertas da Innova: navegação acessível, rotação automática e pausa. */
document.addEventListener('DOMContentLoaded', () => {
  const carousel = document.querySelector('[data-hero-carousel]');
  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll('[data-hero-slide]'));
  const dots = Array.from(carousel.querySelectorAll('[data-hero-dot]'));
  const previous = carousel.querySelector('[data-hero-prev]');
  const next = carousel.querySelector('[data-hero-next]');
  if (slides.length <= 1) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let current = 0;
  let timer = null;

  function showSlide(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, position) => {
      const active = position === current;
      slide.classList.toggle('is-active', active);
      slide.setAttribute('aria-hidden', String(!active));
      slide.inert = !active;
    });
    dots.forEach((dot, position) => {
      const active = position === current;
      dot.classList.toggle('is-active', active);
      dot.setAttribute('aria-current', String(active));
    });
  }

  function pause() {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
  }

  function resume() {
    pause();
    if (reducedMotion.matches || document.hidden || carousel.matches(':hover') || carousel.contains(document.activeElement)) return;
    timer = window.setInterval(() => showSlide(current + 1), 5000);
  }

  function navigate(index) {
    showSlide(index);
    pause();
    // Se o controle mantém o foco, a rotação só volta ao sair do carrossel.
    resume();
  }

  previous?.addEventListener('click', () => navigate(current - 1));
  next?.addEventListener('click', () => navigate(current + 1));
  dots.forEach((dot, index) => dot.addEventListener('click', () => navigate(index)));

  carousel.addEventListener('mouseenter', pause);
  carousel.addEventListener('mouseleave', resume);
  carousel.addEventListener('focusin', pause);
  carousel.addEventListener('focusout', (event) => {
    if (!carousel.contains(event.relatedTarget)) resume();
  });
  document.addEventListener('visibilitychange', resume);
  reducedMotion.addEventListener?.('change', resume);

  // Deslizar horizontalmente no celular também troca o produto.
  let touchStartX = null;
  carousel.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0]?.screenX ?? null;
    pause();
  }, { passive: true });
  carousel.addEventListener('touchend', (event) => {
    const endX = event.changedTouches[0]?.screenX;
    if (touchStartX !== null && endX !== undefined) {
      const distance = endX - touchStartX;
      if (Math.abs(distance) > 55) showSlide(current + (distance < 0 ? 1 : -1));
    }
    touchStartX = null;
    resume();
  }, { passive: true });

  showSlide(0);
  resume();
});
