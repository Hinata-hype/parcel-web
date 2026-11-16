(() => {
  const $ = id => document.getElementById(id);
  const video = $('camera');
  let stream = null, active = false, busy = false, timer = null, generation = 0;
  const status = text => { $('status').textContent = text; };
  function stop() {
    active = false; generation++; clearTimeout(timer);
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null; video.srcObject = null;
    $('start').disabled = busy; $('stop').disabled = true;
    $('device').disabled = busy; $('camera-placeholder').hidden = false;
  }
  async function submit(blob) {
    const form = new FormData(); form.append('image', blob, 'parcel.jpg');
    const response = await fetch('/api/scan', {method:'POST', body:form,
      headers:{'X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content}});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'บันทึกไม่สำเร็จ');
    return data;
  }
  function display(data) {
    if (data.status === 'received' || data.status === 'duplicate') {
      stop(); $('result').hidden = false;
      $('result-label').textContent = data.status === 'duplicate' ? 'รับไว้แล้ว · ไม่บันทึกซ้ำ' : 'บันทึกรับพัสดุและภาพสำเร็จ';
      $('owner').textContent = data.member_name;
      $('tracking').textContent = `เลขพัสดุ: ${data.tracking_no}`;
      $('received-at').textContent = `รับเข้าเมื่อ: ${data.scanned_at}`;
      $('notification').textContent = data.notified ? '✓ ส่ง Telegram แล้ว' : 'ยังไม่ยืนยันการส่ง Telegram · ภาพถูกบันทึกแล้ว กดดูสถานะเพื่อลองส่งใหม่';
      $('evidence').src = data.evidence_url; $('receipt-link').href = data.receipt_url;
      status('รับพัสดุแล้ว ตรวจหลักฐานด้านล่างหรือสแกนชิ้นถัดไป');
    } else {
      status(data.message + (data.codes ? ` (${data.codes.join(', ')})` : ''));
      if (['unknown','conflict','multiple'].includes(data.status)) stop();
    }
  }
  async function tick(run) {
    if (!active || run !== generation || busy) return;
    if (!video.videoWidth) { timer = setTimeout(() => tick(run), 400); return; }
    busy = true; $('photo').disabled = true;
    try {
      const canvas = document.createElement('canvas');
      const scale = Math.min(1, 1920 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
      canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve,'image/jpeg',0.88));
      if (!blob) throw new Error('ถ่ายภาพไม่สำเร็จ');
      const data = await submit(blob);
      // Even if stopped during upload, show the committed receipt.
      if (run === generation || ['received','duplicate'].includes(data.status)) display(data);
    } catch (error) { stop(); status(error.message + ' — กดเปิดกล้องเพื่อลองใหม่'); }
    finally {
      busy = false; $('photo').disabled = false; $('start').disabled = active; $('device').disabled = active;
      if (active && run === generation) timer = setTimeout(() => tick(run), 1200);
    }
  }
  async function start() {
    if (busy || active) return;
    if (!navigator.mediaDevices?.getUserMedia) { status('เบราว์เซอร์นี้เปิดกล้องไม่ได้ กรุณาใช้ localhost หรือ HTTPS หรือเลือกภาพถ่าย'); return; }
    const run = ++generation;
    active = true; $('start').disabled = true; $('stop').disabled = false; $('device').disabled = true;
    status('กำลังขออนุญาตใช้กล้อง…');
    try {
      const selected = $('device').value;
      const acquired = await navigator.mediaDevices.getUserMedia({audio:false,video:{
        ...(selected ? {deviceId:{exact:selected}} : {facingMode:{ideal:'environment'}}),
        width:{ideal:1920},height:{ideal:1080}}});
      if (run !== generation) { acquired.getTracks().forEach(track => track.stop()); return; }
      stream = acquired; video.srcObject = stream; await video.play();
      if (run !== generation) return;
      $('camera-placeholder').hidden = true; $('result').hidden = true;
      status('กำลังสแกน วางป้ายให้เห็นชัดและถือให้นิ่ง…');
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        $('device').replaceChildren(new Option('กล้องเริ่มต้น / กล้องหลัง',''));
        devices.filter(d => d.kind === 'videoinput').forEach((d,i) => $('device').add(new Option(d.label || `กล้อง ${i+1}`, d.deviceId)));
        $('device').value = selected;
      } catch (_) { /* Camera works even if device listing is unavailable. */ }
      tick(run);
    } catch (error) {
      if (run !== generation) return;
      stop(); status(error.name === 'NotAllowedError' ? 'ยังไม่ได้อนุญาตกล้อง กดสัญลักษณ์ข้าง URL เพื่ออนุญาต แล้วลองใหม่' : 'เปิดกล้องไม่ได้ กรุณาปิดโปรแกรมอื่นที่ใช้กล้อง หรือเลือกกล้องใหม่');
    }
  }
  $('start').addEventListener('click', start); $('next').addEventListener('click', start);
  $('stop').addEventListener('click', () => { stop(); status(busy ? 'หยุดกล้องแล้ว กำลังรอผลภาพที่ส่งไป' : 'หยุดกล้องแล้ว'); });
  $('photo').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file || busy) return;
    stop(); busy = true; $('result').hidden = true; $('photo').disabled = true; $('start').disabled = true;
    try { status('กำลังอ่านภาพและตรวจเลขพัสดุ…'); display(await submit(file)); }
    catch (error) { status(error.message); }
    finally { busy = false; $('photo').disabled = false; $('start').disabled = false; $('device').disabled = false; event.target.value = ''; }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); status('พักกล้องแล้ว กดเปิดกล้องเพื่อสแกนต่อ'); } });
  window.addEventListener('pagehide', stop);
})();
