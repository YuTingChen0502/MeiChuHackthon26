// This player is deliberately isolated: it has no imports and no network/API calls.
// A presenter selects rights-cleared prepared audio locally; only its acoustic output
// should reach the room microphone. The generated probe is an audible path check.
const media = document.querySelector('#media');
const fileInput = document.querySelector('#audio-file');
const status = document.querySelector('#now-playing');
const playProbe = document.querySelector('#play-probe');
const playSelected = document.querySelector('#play-selected');
const nextSelected = document.querySelector('#next-selected');
const pause = document.querySelector('#pause');
const stop = document.querySelector('#stop');
let selectedUrls = [];
let selectedIndex = 0;

function setStatus(message) { status.textContent = message; }
function setControls() {
  const active = !media.paused && !media.ended;
  pause.disabled = media.paused || media.ended;
  stop.disabled = media.paused && media.currentTime === 0;
  playSelected.disabled = selectedUrls.length === 0 || active;
  nextSelected.disabled = selectedUrls.length < 2 || active || selectedIndex >= selectedUrls.length - 1;
  playProbe.disabled = active;
}

function audibleProbeUrl() {
  const sampleRate = 44100;
  const samples = sampleRate * 4;
  const bytes = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(bytes);
  const write = (offset, text) => [...text].forEach((code, index) => view.setUint8(offset + index, code.charCodeAt(0)));
  write(0, 'RIFF'); view.setUint32(4, 36 + samples * 2, true); write(8, 'WAVEfmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, samples * 2, true);
  for (let index = 0; index < samples; index += 1) {
    const fade = Math.min(1, index / 800, (samples - index) / 1200);
    view.setInt16(44 + index * 2, Math.round(Math.sin(2 * Math.PI * 440 * index / sampleRate) * 0.2 * fade * 32767), true);
  }
  return URL.createObjectURL(new Blob([bytes], { type:'audio/wav' }));
}

async function play(url, label) {
  media.src = url;
  media.currentTime = 0;
  setStatus(`Starting ${label}…`);
  try { await media.play(); } catch (error) { setStatus(`Playback could not start: ${error.message}`); setControls(); }
}

fileInput.addEventListener('change', () => {
  selectedUrls.forEach(url => URL.revokeObjectURL(url));
  selectedUrls = [...fileInput.files].map(file => URL.createObjectURL(file));
  selectedIndex = 0;
  setStatus(selectedUrls.length ? `${selectedUrls.length} prepared clip${selectedUrls.length === 1 ? '' : 's'} selected locally; filenames are not displayed or transmitted.` : 'No media is playing.');
  setControls();
});
playProbe.addEventListener('click', () => play(audibleProbeUrl(), 'audible output check'));
playSelected.addEventListener('click', () => play(selectedUrls[selectedIndex], `prepared clip ${selectedIndex + 1} of ${selectedUrls.length}`));
nextSelected.addEventListener('click', () => {
  if (selectedIndex < selectedUrls.length - 1) selectedIndex += 1;
  setStatus(`Prepared clip ${selectedIndex + 1} of ${selectedUrls.length} is selected. Filenames remain hidden.`);
  setControls();
});
pause.addEventListener('click', () => media.pause());
stop.addEventListener('click', () => { media.pause(); media.currentTime = 0; setStatus('Playback stopped.'); setControls(); });
media.addEventListener('playing', () => { setStatus('Media playback is active. Route output only through the physical speaker path.'); setControls(); });
media.addEventListener('pause', () => { if (!media.ended) { setStatus('Media playback is paused.'); setControls(); } });
media.addEventListener('ended', () => { setStatus('Media playback ended.'); setControls(); });
media.addEventListener('error', () => { setStatus('Media playback error.'); setControls(); });
setControls();
