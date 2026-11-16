document.getElementById('retry')?.addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true;
  const status = document.getElementById('notify-status'); status.textContent = 'กำลังส่ง…';
  try {
    const response = await fetch(button.dataset.endpoint, {method:'POST',headers:{'X-CSRF-Token':button.dataset.csrf}});
    const data = await response.json(); status.textContent = data.message || data.error || 'กรุณาลองใหม่';
    if (data.notified) button.hidden = true;
  } catch (_) { status.textContent = 'ยังยืนยันการส่งไม่ได้ กรุณาตรวจการเชื่อมต่อ'; }
  finally { button.disabled = false; }
});
