// Carrinho sem atualização de página; o backend recalcula preço e verifica estoque.
document.addEventListener('DOMContentLoaded', () => {
  const toast = document.getElementById('toast');
  let toastTimer;
  const showToast = (message, isError = false) => {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle('error', isError);
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 3300);
  };

  document.querySelectorAll('[data-add-to-cart]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (!button || button.disabled) return;
      button.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {
            'Accept': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
          },
          credentials: 'same-origin',
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.mensagem || 'Erro ao adicionar produto.');
        document.querySelectorAll('[data-cart-count]').forEach((el) => { el.textContent = data.quantidade; });
        showToast('✓ ' + data.mensagem);
      } catch (error) {
        showToast(error.message || 'Não foi possível adicionar ao carrinho.', true);
      } finally {
        button.disabled = false;
      }
    });
  });
});
