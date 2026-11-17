document.querySelectorAll('[data-copy]').forEach(button => {
  const original = button.textContent;
  button.addEventListener('click', async () => {
    const source = document.getElementById(button.dataset.copy);
    const text = source.tagName === 'TEXTAREA' ? source.value : source.textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = 'Copiado!';
      document.getElementById('copy-feedback').textContent = 'Conteúdo copiado.';
    } catch {
      if (source.tagName === 'TEXTAREA') {
        source.focus(); source.select();
      } else {
        const range = document.createRange();
        range.selectNodeContents(source);
        const selection = window.getSelection();
        selection.removeAllRanges(); selection.addRange(range);
      }
      button.textContent = 'Selecione e copie';
      document.getElementById('copy-feedback').textContent = 'Cópia automática indisponível. Use Ctrl+C ou Cmd+C para copiar a seleção.';
    }
    setTimeout(() => { button.textContent = original; }, 2200);
  });
});
const checks = [...document.querySelectorAll('.guide-check')];
function atualizarChecklist() {
  const count = checks.filter(check => check.checked).length;
  document.getElementById('check-count').textContent = count + ' de ' + checks.length;
  document.getElementById('check-progress').value = count;
}
checks.forEach(check => check.addEventListener('change', atualizarChecklist));
atualizarChecklist();
