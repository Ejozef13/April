const $ = id => document.getElementById(id);
const config = await fetch('/api/config').then(r => r.json());
$('face').style.width = `min(100%, ${config.display_width}px)`;
$('face').style.height = `${Math.round(config.display_height * .65)}px`;
$('mode').textContent = config.mode === 'simulation' ? 'SIMULATION · no models / speech' : 'LIVE · local backends';
let state = 'idle', muted = false, recording = null, player = null, audioURL = null;
let generation = 0, recordPending = false, connected = false, playbackPending = false;
let suppress = false;
let playbackVersion = 0, retryPlayback = null;
const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
const send = message => { if (socket.readyState === 1) socket.send(JSON.stringify(message)); };
const descriptions = {idle:'Ready when you are.',listening:'Microphone is recording. Press again to finish.',transcribing:'Turning recorded audio into text.',thinking:'Waiting for a local response or preparing speech.',speaking:'Playing April’s response.',error:'Something went wrong. You can try again.'};
function showState(value) {
  state = value; document.body.dataset.state = value; $('state').textContent = value;
  if (value === 'idle' && !recording) $('mic').textContent = 'Microphone: off';
  $('activity').textContent = descriptions[value];
  const busy = !['idle', 'error'].includes(value);
  $('record').disabled = !connected || (busy && value !== 'listening');
  $('send').disabled = $('time').disabled = !connected || busy;
  $('record').textContent = value === 'listening' ? '■ Finish recording' : '● Start recording';
}
function error(message) { $('error').textContent = message; }
function stopPlayback() {
  playbackVersion++; retryPlayback = null; $('play-reply').hidden = true;
  if (player) {
    player.onended = player.onerror = player.onplaying = null;
    player.pause(); player.removeAttribute('src'); player.load(); player = null;
  }
  if (audioURL) { URL.revokeObjectURL(audioURL); audioURL = null; }
}
async function releaseCapture() {
  const item = recording; recording = null;
  if (!item) return;
  clearTimeout(item.timer); item.node.disconnect(); item.source.disconnect();
  item.stream.getTracks().forEach(t => t.stop());
  await item.context.close();
  return item;
}
async function cancel() {
  generation++; suppress = true; recordPending = false; playbackPending = false;
  stopPlayback(); await releaseCapture(); send({type:'cancel'});
  $('mic').textContent = 'Microphone: off';
}
socket.onopen = () => { connected = true; showState('idle'); };
socket.onclose = () => { connected = false; cancel(); showState('error'); error('Connection closed. Reload after restarting April.'); };
socket.onmessage = async event => {
  const message = JSON.parse(event.data);
  if (suppress) {
    if (message.type === 'state' && message.state === 'idle') suppress = false;
    else return;
  }
  if (message.type === 'state') {
    showState(message.state);
    if (message.state === 'listening' && recordPending) { recordPending = false; startCapture(); }
    if (message.state === 'error') { generation++; stopPlayback(); await releaseCapture(); $('mic').textContent = 'Microphone: off'; }
  }
  if (message.type === 'error') error(message.message);
  if (message.type === 'transcript') $('transcript').textContent = message.text;
  if (message.type === 'reply') $('reply').textContent = message.text;
  if (message.type === 'timings') $('timings').textContent = JSON.stringify(message, null, 2) + '\nServer total excludes capture, network transport and playback. Simulation timings are not performance evidence.';
  if (message.type === 'simulation') $('activity').textContent = message.message;
  if (message.type === 'audio') {
    if (muted) { send({type:'cancel'}); return; }
    stopPlayback();
    const epoch = generation; playbackPending = true;
    const version = playbackVersion;
    const current = () => epoch === generation && version === playbackVersion;
    const fail = message => { if (current()) { error(message); cancel(); } };
    try {
      const bytes = Uint8Array.from(atob(message.audio), c => c.charCodeAt(0));
      audioURL = URL.createObjectURL(new Blob([bytes], {type:'audio/wav'}));
      // Keep one mounted media element across turns. Reset only after its
      // handlers have been detached; an empty src can load the document URL.
      const audio = $('response-audio'); player = audio; audio.src = audioURL;
      if ($('output').value !== 'default') {
        if (!audio.setSinkId) throw new Error('Output selection is unsupported here. Use the system default.');
        await audio.setSinkId($('output').value);
      }
      if (!current()) return;
      audio.onplaying = () => {
        if (current()) { error(''); $('play-reply').hidden = true; send({type:'playback_started'}); }
      };
      audio.onended = () => {
        if (current()) { stopPlayback(); playbackPending = false; send({type:'played'}); }
      };
      audio.onerror = () => {
        const code = audio.error?.code;
        fail(code === 3 || code === 4
          ? `Playback: generated audio could not be decoded (media error ${code}). Check the Piper WAV output.`
          : `Playback: audio loading failed (media error ${code ?? 'unknown'}). Check the selected output.`);
      };
      const play = async () => {
        if (!current()) return;
        try {
          await audio.play();
        } catch (exc) {
          // Stop, mute, completion and a newer turn intentionally invalidate
          // this promise. Their cleanup must not become a new playback error.
          if (!current()) return;
          if (exc.name === 'NotAllowedError' || exc.name === 'AbortError') {
            error('Playback did not start. Press Play reply to retry, or Stop to cancel.');
            retryPlayback = play; $('play-reply').hidden = false;
          } else {
            fail('Playback failed. Check the selected output or try the system default.');
          }
        }
      };
      await play();
    } catch (exc) { fail(`Playback setup: ${exc.message}`); }
  }
};
async function devices() {
  if (!navigator.mediaDevices) throw new Error('Microphone needs localhost or HTTPS. Use the documented SSH tunnel.');
  const list = await navigator.mediaDevices.enumerateDevices();
  for (const [id, kind, setting] of [['input','audioinput','input_device_id'], ['output','audiooutput','output_device_id']]) {
    const previous = $(id).value;
    $(id).replaceChildren(new Option('System default','default'));
    for (const device of list.filter(d => d.kind === kind && d.deviceId !== 'default'))
      $(id).add(new Option(device.label || `${kind} ${$(id).length}`, device.deviceId));
    const desired = previous !== 'default' ? previous : config[setting];
    if ([...$(id).options].some(o => o.value === desired)) $(id).value = desired;
  }
}
async function startCapture() {
  const epoch = generation; let stream, context;
  try {
    if (!navigator.mediaDevices || !window.isSecureContext) throw new Error('Microphone requires localhost or HTTPS.');
    stream = await navigator.mediaDevices.getUserMedia({audio:{deviceId:$('input').value === 'default' ? undefined : {exact:$('input').value},channelCount:1,echoCancellation:true},video:false});
    if (epoch !== generation) { stream.getTracks().forEach(t => t.stop()); return; }
    context = new AudioContext(); await context.audioWorklet.addModule('/static/capture.js');
    await context.resume();
    if (epoch !== generation) { stream.getTracks().forEach(t => t.stop()); await context.close(); return; }
    const source = context.createMediaStreamSource(stream), node = new AudioWorkletNode(context, 'april-capture');
    const item = {stream,context,source,node,chunks:[],samples:0}; recording = item;
    node.port.onmessage = event => {
      if (recording !== item) return;
      if (item.samples + event.data.length > context.sampleRate * config.max_record_seconds) { finishCapture(); return; }
      item.chunks.push(event.data); item.samples += event.data.length;
    };
    source.connect(node); node.connect(context.destination);
    item.timer = setTimeout(finishCapture, config.max_record_seconds * 1000);
    $('mic').textContent = `Microphone: recording · ${stream.getAudioTracks()[0].label} · maximum ${config.max_record_seconds}s`;
    await devices();
  } catch (exc) {
    stream?.getTracks().forEach(t => t.stop());
    if (context && context.state !== 'closed') await context.close();
    error(`Microphone: ${exc.message}`); await cancel();
  }
}
async function finishCapture() {
  const epoch = generation, item = await releaseCapture();
  if (!item || epoch !== generation) return;
  $('mic').textContent = 'Microphone: off · processing recording';
  const samples = new Float32Array(item.samples); let offset = 0;
  for (const chunk of item.chunks) { samples.set(chunk,offset); offset += chunk.length; }
  // Resample to whisper.cpp's PCM16 mono WAV contract, regardless of device rate.
  const count = Math.floor(samples.length * 16000 / item.context.sampleRate);
  const buffer = new ArrayBuffer(44 + count * 2), view = new DataView(buffer);
  const tag = (at, text) => [...text].forEach((c,i) => view.setUint8(at+i,c.charCodeAt(0)));
  tag(0,'RIFF'); view.setUint32(4,36+count*2,true); tag(8,'WAVE'); tag(12,'fmt ');
  view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
  view.setUint32(24,16000,true); view.setUint32(28,32000,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
  tag(36,'data'); view.setUint32(40,count*2,true);
  for (let i=0;i<count;i++) {
    const position = i * item.context.sampleRate / 16000, left = Math.floor(position), weight = position-left;
    const value = samples[left]*(1-weight) + (samples[left+1] ?? samples[left])*weight;
    view.setInt16(44+i*2,Math.max(-1,Math.min(1,value))*32767,true);
  }
  let binary = ''; const bytes = new Uint8Array(buffer);
  for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
  send({type:'audio',audio:btoa(binary)});
}
$('record').onclick = () => {
  error('');
  if (recording) finishCapture();
  else if (state === 'listening') cancel();
  else if (['idle','error'].includes(state)) { recordPending = true; send({type:'record'}); }
};
$('stop').onclick = cancel;
$('play-reply').onclick = () => { if (retryPlayback) retryPlayback(); };
$('mute').onclick = () => { muted = !muted; $('mute').textContent = `Mute ${muted?'on':'off'}`; $('mute').setAttribute('aria-pressed',String(muted)); if (muted && (player || playbackPending)) cancel(); };
$('text-form').onsubmit = event => { event.preventDefault(); error(''); send({type:'text',text:$('text').value}); };
$('time').onclick = () => { error(''); send({type:'time',arguments:{}}); };
$('devices').onclick = async () => {
  try { const stream = await navigator.mediaDevices.getUserMedia({audio:true}); stream.getTracks().forEach(t => t.stop()); await devices(); $('mic').textContent = 'Microphone: permission granted · not recording'; }
  catch (exc) { error(`Devices: ${exc.message}`); }
};
document.addEventListener('keydown', event => { if (event.altKey && event.code === 'KeyR' && !event.repeat) { event.preventDefault(); $('record').click(); } if (event.code === 'Escape') cancel(); });
window.addEventListener('pagehide', () => { generation++; stopPlayback(); if (recording) recording.stream.getTracks().forEach(t => t.stop()); socket.close(); });
devices().catch(() => {});
