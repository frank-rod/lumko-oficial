/* LUMKO Studio — interactions
 * - sticky nav scroll state
 * - paquetes responsive cards with active lottie sync
 * - portafolio horizontal scroller with prev/next + drag
 * - footer year
 */

(function () {
  'use strict';

  /* ---------- year ---------- */
  document.querySelectorAll('[data-year]').forEach(el => {
    el.textContent = String(new Date().getFullYear());
  });

  /* ---------- nav scrolled ---------- */
  const nav = document.querySelector('[data-nav]');
  const onScroll = () => {
    if (!nav) return;
    nav.classList.toggle('is-scrolled', window.scrollY > 8);
  };
  document.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- lotties ----------
   * Wait for lottie-web (lottie_light) to load, then mount each [data-lottie].
   * Main card lotties: play when their card is the current one.
   */
  function mountLotties() {
    if (!window.lottie) return false;
    document.querySelectorAll('[data-lottie]').forEach(el => {
      if (el.dataset.lottieMounted === '1') return;
      const path = el.getAttribute('data-lottie');
      const isMain = el.hasAttribute('data-lottie-main');
      try {
        const anim = window.lottie.loadAnimation({
          container: el,
          renderer: 'svg',
          loop: true,
          autoplay: false,
          path,
        });
        anim.addEventListener('DOMLoaded', () => {
          anim.goToAndStop(0, true);
        });
        el._lottie = anim;
        el.dataset.lottieMounted = '1';
      } catch (err) {
        console.warn('lottie load failed', path, err);
      }
    });
    return true;
  }

  function whenLottieReady(cb, attempts = 60) {
    if (window.lottie) { cb(); return; }
    if (attempts <= 0) return;
    setTimeout(() => whenLottieReady(cb, attempts - 1), 100);
  }
  whenLottieReady(mountLotties);

  /* ---------- paquetes cards ---------- */
  const track = document.querySelector('[data-track]');
  const cards = Array.from(document.querySelectorAll('.card[data-card]'));

  let currentIdx = -1;

  function setActive(idx) {
    if (idx === currentIdx) return;
    currentIdx = idx;

    cards.forEach((c, i) => c.classList.toggle('is-current', i === idx));

    // play current card's main lottie, freeze the others
    cards.forEach((c, i) => {
      const lottieEl = c.querySelector('[data-lottie-main]');
      if (!lottieEl || !lottieEl._lottie) return;
      if (i === idx) {
        lottieEl._lottie.play();
      } else {
        lottieEl._lottie.goToAndStop(0, true);
      }
    });
  }

  // On mobile the package cards are a horizontal scroll-snap track.
  // Pick the card whose center is closest to the visible track center.
  function pickCurrent() {
    if (!track || cards.length === 0) return;
    const cs = window.getComputedStyle(track);
    const isHorizontal = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
    const trackRect = track.getBoundingClientRect();
    const center = isHorizontal
      ? trackRect.left + trackRect.width / 2
      : trackRect.top + trackRect.height / 2;
    let best = 0, bestDist = Infinity;
    cards.forEach((c, i) => {
      const r = c.getBoundingClientRect();
      const cCenter = isHorizontal
        ? r.left + r.width / 2
        : r.top + r.height / 2;
      const d = Math.abs(cCenter - center);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    setActive(best);
  }

  if (track) {
    let raf = 0;
    track.addEventListener('scroll', () => {
      if (raf) return;
      raf = requestAnimationFrame(() => { raf = 0; pickCurrent(); });
    }, { passive: true });
    // initial pick after layout settles + lottie mount
    requestAnimationFrame(() => requestAnimationFrame(pickCurrent));
    setTimeout(pickCurrent, 400);
  }

  // On desktop, cards sit in a compact grid. Use viewport visibility to keep
  // the highlighted state and lottie playback stable while crossing sections.
  if ('IntersectionObserver' in window) {
    const isStackedLayout = () => {
      if (!track) return false;
      const cs = window.getComputedStyle(track);
      return cs.overflowY === 'visible' && cs.overflowX === 'visible';
    };
    const io = new IntersectionObserver(
      (entries) => {
        if (!isStackedLayout()) return;
        let bestEntry = null;
        entries.forEach(e => {
          if (!bestEntry || e.intersectionRatio > bestEntry.intersectionRatio) bestEntry = e;
        });
        if (bestEntry && bestEntry.isIntersecting) {
          const idx = Number(bestEntry.target.dataset.card || 0);
          setActive(idx);
        }
      },
      { threshold: [0.4, 0.6, 0.8] }
    );
    cards.forEach(c => io.observe(c));
  }

  /* ---------- portafolio scroller ---------- */
  const port = document.querySelector('[data-port]');
  const portPrev = document.querySelector('[data-port-prev]');
  const portNext = document.querySelector('[data-port-next]');
  if (port && portPrev && portNext) {
    const step = () => {
      const first = port.querySelector('.port__card');
      if (!first) return 320;
      const gap = parseInt(window.getComputedStyle(port).columnGap || '18', 10) || 18;
      return first.getBoundingClientRect().width + gap;
    };
    const updateNav = () => {
      portPrev.disabled = port.scrollLeft <= 4;
      portNext.disabled = port.scrollLeft + port.clientWidth >= port.scrollWidth - 4;
    };
    portPrev.addEventListener('click', () => port.scrollBy({ left: -step(), behavior: 'smooth' }));
    portNext.addEventListener('click', () => port.scrollBy({ left:  step(), behavior: 'smooth' }));
    port.addEventListener('scroll', () => {
      if (port._raf) return;
      port._raf = requestAnimationFrame(() => { port._raf = 0; updateNav(); });
    }, { passive: true });
    window.addEventListener('resize', updateNav);
    updateNav();

    // pointer drag
    let dragging = false, startX = 0, startScroll = 0;
    port.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      dragging = true; startX = e.clientX; startScroll = port.scrollLeft;
      port.setPointerCapture(e.pointerId);
      port.style.cursor = 'grabbing';
    });
    port.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      port.scrollLeft = startScroll - (e.clientX - startX);
    });
    const stopDrag = () => { dragging = false; port.style.cursor = ''; };
    port.addEventListener('pointerup', stopDrag);
    port.addEventListener('pointercancel', stopDrag);
    port.addEventListener('pointerleave', stopDrag);
  }
})();
