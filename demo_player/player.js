// This module deliberately has no imports. It is an independent source environment.
const preparedTrials = [
  { assetId:'clip-amber-17', label:'Prepared clip A' },
  { assetId:'clip-north-42', label:'Prepared clip B' },
  { assetId:'clip-slate-09', label:'Prepared clip C' },
];
preparedTrials.sort(() => Math.random() - .5);
const clips = document.querySelector('#clips');
clips.innerHTML = preparedTrials.map((trial, index) => `<button data-index="${index}">Play ${trial.label}</button>`).join('');
clips.addEventListener('click', event => { const index = event.target.dataset.index; if (index === undefined) return; const trial = preparedTrials[index]; document.querySelector('#now-playing').textContent = `Playing ${trial.label} (${trial.assetId}). Route this output to the speaker; do not pass this data to inference.`; });
