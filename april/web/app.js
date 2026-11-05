const $ = id => document.getElementById(id);
const desktopMode = new URLSearchParams(location.search).get('widget') === '1';
let desktopRequest = null;
let calendarEvents=[];
if (desktopMode) document.body.classList.add('desktop-widget','avatar-only');
const config = await fetch('/api/config').then(r => r.json());
$('face').style.width = `min(100%, ${config.display_width}px)`;
$('face').style.height = `${Math.round(config.display_height * .65)}px`;
$('mode').textContent = config.mode === 'simulation' ? 'SIMULATION · no models / speech' : 'LIVE · local backends';
$('integration-status').textContent = config.mode === 'simulation' ? 'External/private retrieval is disabled in simulation.' : Object.entries(config.integrations || {}).map(([name,configured]) => `${name === 'web' ? 'web ('+config.web_provider+')' : name}: ${configured ? 'configured (not yet verified)' : 'setup needed'}`).join(' · ');
let state = 'idle', muted = false, recording = null, player = null, audioURL = null;
let generation = 0, recordPending = false, connected = false, playbackPending = false;
let suppress = false;
let playbackVersion = 0, retryPlayback = null;
let lastTiming = null;
let reviewUsed=false;
let serverBusy=false;
let lookupPending = false;
$('lookup-status').textContent = config.mode === 'simulation' ? 'Simulation: no private or external searches.' : (config.automatic_web_search ? 'Automatic web lookup on · clock and private requests use dedicated routes.' : 'Automatic web lookup off · use explicit search controls.');
const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
const send = message => { if (socket.readyState === 1) socket.send(JSON.stringify(message)); };
const descriptions = {idle:'Ready when you are.',listening:'Microphone is recording. Press again to finish.',transcribing:'Turning recorded audio into text.',thinking:'Waiting for a local response or preparing speech.',speaking:'Playing April’s response.',error:'Something went wrong. You can try again.'};
function showState(value) {
  state = value; document.body.dataset.state = value; $('state').textContent = value;
  if (!recording && value !== 'listening') $('mic').textContent = 'Microphone: off';
  $('activity').textContent = serverBusy && ['idle','error'].includes(value) ? 'April is active in another window.' : descriptions[value];
  const ownBusy = !['idle', 'error'].includes(value);
  const busy = ownBusy || serverBusy;
  $('record').disabled = !connected || (busy && value !== 'listening');
  $('send').disabled = $('time').disabled = !connected || busy;
  for (const id of ['search-web','search-documents','search-gmail']) $(id).disabled = !connected || busy;
  $('stop').disabled = !connected || !ownBusy;
  $('approve-action').disabled = !connected || busy || reviewUsed;
  $('record').textContent = value === 'listening' ? '■ Finish recording' : '● Start recording';
}
function error(message) { $('error').textContent = message; }
function prepareTurn() {
  error(''); lastTiming = null; $('export-timing').disabled = true;
  $('timings').textContent = 'Waiting for this turn’s measurements.';
  $('reply').textContent = 'Waiting for April…';
  $('sources').replaceChildren(); $('sources-panel').hidden = true;
  lookupPending=false; $('lookup-status').textContent='Preparing request…';
}
function setPlaybackResult(value) { if (lastTiming) lastTiming.playback = value; }
function stopPlayback() {
  playbackVersion++; retryPlayback = null; $('play-reply').hidden = true;
  if (player) {
    player.onended = player.onerror = player.onplaying = null;
    player.pause(); player.removeAttribute('src'); player.load(); player = null;
  }
  if (audioURL) { URL.revokeObjectURL(audioURL); audioURL = null; }
}
async function releaseCapture() {
  document.body.classList.remove('input-active');
  const item = recording; recording = null;
  if (!item) return;
  clearTimeout(item.timer); item.node.disconnect(); item.source.disconnect();
  $('mic-level').value = 0; $('mic-level-label').textContent = 'Input inactive';
  item.stream.getTracks().forEach(t => t.stop());
  await item.context.close();
  return item;
}
async function cancel() {
  $('action-review').hidden=true;
  if (desktopMode) desktopRequest = 'cancel';
  if (lookupPending) $('lookup-status').textContent='Lookup cancelled.';
  lookupPending=false;
  if (lastTiming && ['pending', 'playing'].includes(lastTiming.playback)) setPlaybackResult('cancelled');
  generation++; suppress = true; recordPending = false; playbackPending = false;
  stopPlayback(); await releaseCapture(); send({type:'cancel'});
  $('mic').textContent = 'Microphone: off';
}
socket.onopen = () => {
  connected = true; showState('idle');
  const file=new URLSearchParams(location.search).get('reviewFile');
  if(file){$('debug-file').value=file;privateAction({type:'debug_file',file});}
};
socket.onclose = () => { connected = false; cancel(); showState('error'); error('Connection closed. Reload after restarting April.'); };
socket.onmessage = async event => {
  const message = JSON.parse(event.data);
  if (suppress) {
    if (message.type === 'state' && message.state === 'idle') suppress = false;
    else return;
  }
  if (message.type === 'availability') {serverBusy=message.busy;showState(state);}
  if (message.type === 'state') {
    serverBusy=message.busy ?? false;
    showState(message.state);
    if (message.state === 'listening' && recordPending) { recordPending = false; if (!desktopMode) startCapture(); }
    if (message.state === 'error') { setPlaybackResult('failed'); generation++; stopPlayback(); await releaseCapture(); $('mic').textContent = 'Microphone: off'; }
  }
  if (message.type === 'control' && message.action === 'shutdown') {
    if (desktopMode) desktopRequest='off';
    else error('Goodbye requested. Use the native companion or python -m april.power stop to switch April off.');
  }
  if (message.type === 'control' && ['debug','calendar'].includes(message.action)) {
    if(desktopMode) desktopRequest=message.action;
    const panel=$(message.action==='debug'?'debug-panel':'calendar-panel');
    panel.open=true;panel.scrollIntoView({behavior:'smooth'});
  }
  if (message.type === 'review') {
    reviewUsed=false;
    $('action-review').hidden=false;
    $('review-summary').textContent=message.summary;
    $('approve-action').disabled=!['idle','error'].includes(state);
    $('reply').textContent=message.kind==='calendar'?'Awaiting approval; no calendar change has been made.':'File review prepared; execution needs your approval.';
    $('approve-action').onclick=()=>{
      if(!['idle','error'].includes(state) || reviewUsed) return;
      reviewUsed=true;
      $('approve-action').disabled=true;
      send({type:message.kind==='calendar'?'calendar_confirm':'debug_execute',id:message.id});
    };
    if(desktopMode) desktopRequest='expand';
  }
  if (message.type === 'action_result') {
    $('action-result').textContent=message.message;
    $('reply').textContent='Action result shown below.';
    $('action-review').hidden=true;
  }
  if (message.type === 'calendar_events') {
    calendarEvents=message.events.filter(event=>event.kind==='calendar');
    $('calendar-event').replaceChildren(new Option('New event',''),
      ...calendarEvents.map((event,index)=>new Option(event.title,String(index))));
  }
  if (message.type === 'error') {
    if (lookupPending) $('lookup-status').textContent='Lookup failed · no web answer verified.';
    lookupPending=false; error(message.message);
    if($('reply').textContent==='Waiting for April…') $('reply').textContent='This request did not complete.';
  }
  if (message.type === 'lookup') {
    lookupPending=message.state==='searching';
    $('lookup-status').textContent=message.state==='searching' ? `Searching ${message.kind} via ${message.provider}…` : (message.state==='clock' ? 'Using the actual local clock · no web search needed.' : 'No web lookup · local/private request or manual mode.');
  }
  if (message.type === 'lookup' && message.kind === 'context') $('lookup-status').textContent='Using approved local context…';
  if (message.type === 'transcript') $('transcript').textContent = message.text;
  if (message.type === 'reply') $('reply').textContent = message.text;
  if (message.type === 'sources') {
    lookupPending=false;
    $('lookup-status').textContent=message.sources.length ? `Lookup complete · ${message.sources.length} source${message.sources.length===1?'':'s'} retrieved. Review excerpts below.` : 'Lookup completed with no matching sources · no answer verified.';
    $('sources').replaceChildren(...message.sources.map(source => {
      const item=document.createElement('li');
      let heading=document.createElement('strong'); heading.textContent=source.title;
      if (source.url) {
        try {
          const url=new URL(source.url);
          if (['http:','https:'].includes(url.protocol) && !url.username) {
            heading=document.createElement('a'); heading.textContent=source.title; heading.href=url.href;
            heading.target='_blank'; heading.rel='noopener noreferrer';
          }
        } catch { /* Invalid URLs remain plain text; never execute provider markup. */ }
      }
      const excerpt=document.createElement('p'); excerpt.textContent=source.excerpt;
      item.append(heading,excerpt); return item;
    }));
    $('sources-panel').hidden=message.sources.length===0;
  }
  if (message.type === 'timings') {
    lastTiming = {schema_version:1, recorded_at:new Date().toISOString(), mode:config.mode,
      model:config.model, web_provider:config.web_provider, context_tokens:config.context_tokens, reasoning_effort:config.reasoning_effort,
      max_response_tokens:config.max_response_tokens, values:message.values,
      playback:'pending', transcript_included:false, audio_included:false,
      condition:'unknown', boundaries:'Server only; excludes capture, transport, playback startup and playback duration.'};
    $('timings').textContent = JSON.stringify(message, null, 2) + '\nServer total excludes capture, network transport and playback. Simulation timings are not performance evidence.';
    $('export-timing').disabled = false;
  }
  if (message.type === 'simulation') { setPlaybackResult('simulated'); $('activity').textContent = message.message; }
  if (message.type === 'audio') {
    if (muted) { setPlaybackResult('muted'); send({type:'cancel'}); return; }
    stopPlayback();
    const epoch = generation; playbackPending = true;
    const version = playbackVersion;
    const current = () => epoch === generation && version === playbackVersion;
    const fail = message => { if (current()) { setPlaybackResult('failed'); error(message); cancel(); } };
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
        if (current()) { setPlaybackResult('playing'); error(''); $('play-reply').hidden = true; send({type:'playback_started'}); }
      };
      audio.onended = () => {
        if (current()) { setPlaybackResult('completed'); stopPlayback(); playbackPending = false; send({type:'played'}); }
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
    $('mic').textContent = 'Microphone: requesting permission…';
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
      let energy = 0;
      for (const value of event.data) energy += value * value;
      const rms = Math.sqrt(energy / event.data.length);
      // A small hold keeps the tail smooth between speech syllables. This is
      // an input-level indicator, not a claim to perform voice recognition.
      const now = performance.now();
      if (rms >= .012) item.lastSignalAt = now;
      document.body.classList.toggle('input-active', now - (item.lastSignalAt ?? -Infinity) < 180);
      const level = Math.max(0, Math.min(1, (20 * Math.log10(Math.max(rms, .001)) + 60) / 60));
      $('mic-level').value = level;
      $('mic-level-label').textContent = `Input ${Math.round(level * 100)}% · ${Math.floor(item.samples / context.sampleRate)}s / ${config.max_record_seconds}s`;
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
  if (desktopMode) {
    desktopRequest = state === 'listening' ? 'finish' : 'record';
    return;
  }
  if (recording) finishCapture();
  else if (state === 'listening') cancel();
  else if (['idle','error'].includes(state)) { prepareTurn(); recordPending = true; send({type:'record'}); }
};
$('stop').onclick = cancel;
$('play-reply').onclick = () => { if (retryPlayback) retryPlayback(); };
$('mute').onclick = () => { muted = !muted; $('mute').textContent = `Mute ${muted?'on':'off'}`; $('mute').setAttribute('aria-pressed',String(muted)); if (muted && (player || playbackPending)) cancel(); };
$('text-form').onsubmit = event => {
  event.preventDefault();
  if (!connected || !['idle','error'].includes(state)) return;
  prepareTurn(); send({type:'text',text:$('text').value});
};
$('time').onclick = () => { prepareTurn(); send({type:'time',arguments:{}}); };
for (const action of ['web','documents','gmail']) {
  $(`search-${action}`).onclick=()=>{
    const text=$('text').value.trim();
    if (!text) { error('Type a search query in the message box first.'); $('text').focus(); return; }
    if (!connected || !['idle','error'].includes(state)) return;
    prepareTurn(); send({type:action,text});
  };
}
$('devices').onclick = async () => {
  try { const stream = await navigator.mediaDevices.getUserMedia({audio:true}); stream.getTracks().forEach(t => t.stop()); await devices(); $('mic').textContent = 'Microphone: permission granted · not recording'; }
  catch (exc) { error(`Devices: ${exc.message}`); }
};
document.addEventListener('keydown', event => { if (event.altKey && event.code === 'KeyR' && !event.repeat) { event.preventDefault(); $('record').click(); } if (event.code === 'Escape') cancel(); });
window.addEventListener('pagehide', () => { generation++; stopPlayback(); if (recording) recording.stream.getTracks().forEach(t => t.stop()); socket.close(); });
if (!desktopMode) devices().catch(() => {});

async function checkSetup() {
  $('check-setup').disabled = true;
  try {
    const response = await fetch('/api/readiness');
    if (!response.ok) throw new Error('Request failed');
    const result = await response.json();
    $('setup-results').replaceChildren(...result.checks.map(check => {
      const item = document.createElement('li');
      item.textContent = `${check.ready ? '✓' : 'Needs attention'} · ${check.component}: ${check.message}`;
      return item;
    }));
  } catch { $('setup-results').textContent = 'Setup check unavailable. Run bash april.sh --check in the project terminal.'; }
  finally { $('check-setup').disabled = false; }
}
$('check-setup').onclick = checkSetup;

$('export-timing').onclick = () => {
  if (!lastTiming) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastTiming, null, 2)], {type:'application/json'}));
  const link = document.createElement('a'); link.href = url;
  link.download = `april-${config.mode}-timing-${Date.now()}.json`;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$('face-view').onclick = async () => {
  const active = !document.body.classList.contains('face-view');
  document.body.classList.toggle('face-view', active);
  $('face-view').setAttribute('aria-pressed', String(active));
  $('face-view').textContent = active ? 'Show controls' : 'Face view';
  try {
    if (active) await document.documentElement.requestFullscreen();
    else if (document.fullscreenElement) await document.exitFullscreen();
  } catch { /* Face view remains usable when browser fullscreen is unavailable. */ }
};
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) {
    document.body.classList.remove('face-view');
    $('face-view').setAttribute('aria-pressed', 'false'); $('face-view').textContent = 'Face view';
  }
});


// Poll-only native bridge: no shell, file, token or generic evaluation endpoint.
// Native capture uses the same socket/session/playback path as the browser.
if (desktopMode) {
  window.aprilDesktop = {
    compact(value) {
      document.body.classList.toggle('avatar-only',value);
    },
    snapshot() {
      const request = desktopRequest;
      desktopRequest = null;
      return {state, connected, generation, request, busy:serverBusy};
    },
    begin() {
      if (!connected || serverBusy || !['idle', 'error'].includes(state)) return -1;
      prepareTurn();
      generation++;
      recordPending = false;
      send({type:'record'});
      return generation;
    },
    audio(encoded, epoch) {
      if (epoch !== generation || !connected || state !== 'listening' || suppress) return;
      document.body.classList.remove('input-active');
      $('mic').textContent = 'Native microphone: off · processing recording';
      send({type:'audio', audio:encoded});
    },
    level(rms, epoch) {
      if (epoch !== generation || state !== 'listening') return;
      document.body.classList.toggle('input-active', rms >= .012);
    },
    empty(epoch) {
      if (epoch !== generation) return;
      cancel();
      error('No speech detected. Say Hey April, pause for the window, then speak—or use Record.');
    },
    cancel,
    demo() {
      if (!connected || !['idle','error'].includes(state)) return;
      prepareTurn();
      send({type:'text', text:'Hello April'});
    }
  };
}

// GLB is a genuine local 3D asset; the supplied MP4 is reference, not geometry.
if (config.avatar_3d || desktopMode || new URLSearchParams(location.search).get('avatar') === '3d') {
  const host=document.createElement('div');
  host.id='avatar-3d'; $('face').after(host);
  try {
    const {mountAvatar}=await import('./avatar3d.js');
    const disposeAvatar=await mountAvatar(host,config.avatar_model_url,()=>{
      if(desktopMode) desktopRequest='expand';
    });
    window.addEventListener('pagehide',disposeAvatar,{once:true});
    document.body.classList.add('avatar-ready');
  } catch {
    host.remove(); // Keep the working SVG if WebGL or the replacement model fails.
    error('3D preview unavailable; using the original face.');
  }
}

function privateAction(message) {
  if(!connected || serverBusy || !['idle','error'].includes(state)) return;
  prepareTurn();send(message);
}
$('review-file').onclick=()=>privateAction({type:'debug_file',file:$('debug-file').value});
$('calendar-read').onclick=()=>privateAction({type:'calendar_read'});
$('briefing').onclick=()=>privateAction({type:'briefing'});
$('calendar-event').onchange=()=>{
  const event=calendarEvents[Number($('calendar-event').value)];
  if($('calendar-event').value==='' || !event) return;
  $('event-title').value=event.title;$('event-start').value=event.start;$('event-end').value=event.end;
};
$('calendar-propose').onclick=()=>{
  const event={title:$('event-title').value,start:$('event-start').value,end:$('event-end').value};
  if($('calendar-event').value!=='') {
    const previous=calendarEvents[Number($('calendar-event').value)];
    if(previous){event.uid=previous.uid;event.etag=previous.etag;}
  }
  privateAction({type:'calendar_propose',event});
};
$('reject-action').onclick=()=>{$('action-review').hidden=true;cancel();};
$('share-screen').onclick=async()=>{
  if(desktopMode){desktopRequest='debug';return;}
  if(!connected || serverBusy || !['idle','error'].includes(state)) return;
  let stream;
  try {
    if(!navigator.mediaDevices?.getDisplayMedia) throw new Error('Open the full app in your browser for the screen picker.');
    stream=await navigator.mediaDevices.getDisplayMedia({video:true,audio:false});
    const video=document.createElement('video');video.srcObject=stream;video.muted=true;
    await video.play();
    const scale=Math.min(1,1280/video.videoWidth,720/video.videoHeight);
    const canvas=document.createElement('canvas');
    canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
    canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
    const image=canvas.toDataURL('image/jpeg',.8).split(',')[1];
    privateAction({type:'debug_screen',image});
    video.srcObject=null;
  } catch(exc){error('Screen review: '+exc.message);}
  finally{stream?.getTracks().forEach(track=>track.stop());}
};

const requestedPanel=new URLSearchParams(location.search).get('panel');
if(['debug','calendar'].includes(requestedPanel)) $(requestedPanel+'-panel').open=true;
if(desktopMode) $('face').onclick=()=>{desktopRequest='expand';};
