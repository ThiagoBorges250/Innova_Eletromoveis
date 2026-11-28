(() => {
  const widget = document.querySelector('[data-innova-ai]');
  if (!widget) return;

  const storageKey = 'innova-ai:historico:v1';
  const maxTurns = 12;
  const launcher = widget.querySelector('.ai-launcher');
  const panel = widget.querySelector('.ai-panel');
  const chat = widget.querySelector('.ai-chat');
  const transcript = widget.querySelector('.ai-turns');
  const suggestions = widget.querySelector('.ai-suggestions');
  const form = widget.querySelector('.ai-form');
  const input = form.elements.pergunta;
  const send = form.querySelector('[type="submit"]');
  const status = widget.querySelector('.ai-status');
  const errorMessage = widget.querySelector('.ai-error');
  let pending = null;
  let turns = [];

  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || '[]');
    if (Array.isArray(saved)) {
      turns = saved.filter((turn) => turn && typeof turn.question === 'string'
        && typeof turn.message === 'string' && Array.isArray(turn.products)).slice(-maxTurns);
    }
  } catch {
    // A conversa continua na página quando o navegador bloqueia o armazenamento.
  }

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text) item.textContent = text;
    return item;
  }

  function localPath(value, prefix) {
    if (typeof value !== 'string') return '';
    try {
      const url = new URL(value, location.origin);
      if (url.origin === location.origin && url.pathname.startsWith(prefix)) return url.href;
    } catch {
      return '';
    }
    return '';
  }

  function cards(items, current) {
    const list = element('ul', 'ai-results');
    for (const product of items.slice(0, 3)) {
      if (!product || typeof product.nome !== 'string') continue;
      const url = localPath(product.url, '/produto/');
      if (!url) continue;
      const card = element('a', 'ai-product');
      card.href = url;
      const image = element('img');
      image.alt = '';
      image.src = localPath(product.imagem, '/static/') || localPath(product.imagem, '/midia/produtos/') || widget.dataset.placeholder;
      image.addEventListener('error', () => { image.src = widget.dataset.placeholder; }, { once: true });
      const copy = element('span');
      copy.append(element('strong', '', product.nome),
                  element('small', '', current ? product.preco : 'Ver preço atual'));
      const arrow = element('span', 'icon', '›');
      arrow.setAttribute('aria-hidden', 'true');
      card.append(image, copy, arrow);
      const item = element('li');
      item.append(card);
      list.append(item);
    }
    return list;
  }

  function appendTurn(turn, current = false) {
    const group = element('div');
    group.append(element('p', 'ai-message ai-message--customer', turn.question),
                 element('p', 'ai-message', turn.message));
    if (turn.products.length) group.append(cards(turn.products, current));
    transcript.append(group);
    while (transcript.childElementCount > maxTurns) transcript.firstElementChild.remove();
  }

  function scrollChat() {
    chat.scrollTop = chat.scrollHeight;
  }

  function showError(text = '') {
    errorMessage.textContent = text;
    errorMessage.hidden = !text;
  }

  function hidePanel(closed) {
    if (closed && pending) pending.abort();
    if (closed) showError();
    panel.hidden = true;
    launcher.hidden = false;
    launcher.setAttribute('aria-expanded', 'false');
    launcher.focus();
  }

  launcher.addEventListener('click', () => {
    panel.hidden = false;
    launcher.hidden = true;
    launcher.setAttribute('aria-expanded', 'true');
    if (matchMedia('(pointer: coarse)').matches) chat.focus();
    else input.focus();
    scrollChat();
  });
  widget.querySelector('[data-minimize]').addEventListener('click', () => hidePanel(false));
  widget.querySelector('[data-close]').addEventListener('click', () => hidePanel(true));
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hidePanel(false);
  });

  for (const turn of turns) appendTurn(turn);
  suggestions.hidden = !!turns.length;
  for (const button of suggestions.querySelectorAll('button')) {
    button.addEventListener('click', () => {
      if (pending) return;
      input.value = button.textContent.trim();
      form.requestSubmit();
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (pending || !question) return;

    pending = new AbortController();
    const controller = pending;
    const timer = setTimeout(() => controller.abort('timeout'), 45_000);
    const draft = element('p', 'ai-message ai-message--customer', question);
    chat.append(draft);
    input.value = '';
    send.disabled = true;
    status.hidden = false;
    showError();
    scrollChat();

    try {
      const response = await fetch(widget.dataset.endpoint, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {
          'Content-Type': 'application/json', Accept: 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
        },
        body: JSON.stringify({
          pergunta: question,
          historico: turns.slice(-2).map((turn) => turn.question),
          categoria: form.elements.categoria.value,
          orcamento_maximo: form.elements.orcamento_maximo.value,
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (controller.signal.aborted) return;
      if (!response.ok || typeof result.resposta !== 'string' || !Array.isArray(result.produtos)) {
        throw new Error(result.error || 'Não consegui carregar a resposta. Tente novamente.');
      }
      const turn = { question, message: result.resposta, products: result.produtos };
      for (const price of transcript.querySelectorAll('.ai-product small')) price.textContent = 'Ver preço atual';
      turns = [...turns, turn].slice(-maxTurns);
      suggestions.hidden = true;
      appendTurn(turn, true);
      try { sessionStorage.setItem(storageKey, JSON.stringify(turns)); } catch { /* Histórico em memória. */ }
    } catch (error) {
      if (!controller.signal.aborted || controller.signal.reason === 'timeout') {
        input.value ||= question;
        showError(controller.signal.aborted ? 'A consulta demorou demais. Tente novamente.'
          : error instanceof TypeError ? 'A conexão caiu. Tente novamente.' : error.message);
      }
    } finally {
      clearTimeout(timer);
      draft.remove();
      status.hidden = true;
      pending = null;
      send.disabled = false;
      scrollChat();
    }
  });
})();
