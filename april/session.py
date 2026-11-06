"""One foreground turn; bounded shared RAM context and separate memory extraction."""
import asyncio
import base64
import tempfile
import time
import sqlite3
import uuid
from pathlib import Path

from .audio import validate_wav, spoken_answer
from .state import State, StateMachine
from .tools import current_time, is_time_request, is_goodbye_request
from .errors import BackendError
from .knowledge import route_knowledge, retrieve


class Session:
    def __init__(self, config, backends, send, gate, memory=None):
        self.config, self.backends, self.send, self.gate = config, backends, send, gate
        self.machine = StateMachine()
        self.task = None
        self.owns_gate = False
        self.record_timer = None
        self.memory = memory
        self.private_conversation = False
        self.conversation_id = uuid.uuid4().hex

    async def state(self, value):
        self.machine.move(value)
        await self.send({"type": "state", "state": value})

    def release(self):
        if self.record_timer:
            self.record_timer.cancel()
            self.record_timer = None
        if self.owns_gate:
            self.gate.release()
            self.owns_gate = False

    async def cancel(self, *, invalidate_review=True):
        if invalidate_review:self.pending_review=None
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        self.release()
        await self.state(State.IDLE)

    async def error(self, message, code='interaction_failed'):
        self.release()
        await self.state(State.ERROR)
        await self.send({"type": "error", "message": message, "code": code})

    async def begin(self, recording=False):
        if self.owns_gate or self.gate.locked():
            await self.send({"type": "error", "message": "April is busy. Stop the current interaction first."})
            return False
        await self.gate.acquire()
        self.owns_gate = True
        if self.machine.state == State.ERROR:
            await self.state(State.IDLE)
        if recording:
            await self.state(State.LISTENING)
            self.record_timer = asyncio.create_task(self.record_deadline())
        return True

    async def record_deadline(self):
        await asyncio.sleep(self.config.max_record_seconds + 3)
        self.record_timer = None
        await self.error("Recording expired. Check microphone permissions and try again.")

    async def handle(self, message):
        action = message.get("type")
        if action == "memory":
            if await self.begin():
                self.task=asyncio.create_task(self.memory_action(message))
        elif action in {"debug_screen","debug_file","debug_execute","calendar_read","calendar_propose","calendar_confirm","calendar_draft","briefing"}:
            if await self.begin():
                from .assistant_actions import run
                self.task=asyncio.create_task(run(self,message))
        elif action == "cancel":
            await self.cancel()
        elif action == "record":
            await self.begin(recording=True)
        elif action == "played" and self.machine.state == State.SPEAKING:
            await self.cancel(invalidate_review=False)
        elif action == "audio":
            if self.machine.state != State.LISTENING:
                await self.send({"type": "error", "message": "Start recording before sending audio."})
                return
            if self.record_timer:
                self.record_timer.cancel()
                self.record_timer = None
            try:
                encoded = message.get("audio", "")
                if not isinstance(encoded, str) or len(encoded) > 1_300_000:
                    raise ValueError("Recording too large")
                data = base64.b64decode(encoded, validate=True)
                validate_wav(data, self.config.max_record_seconds)
            except (ValueError, TypeError) as exc:
                await self.error(str(exc))
                return
            await self.state(State.TRANSCRIBING)
            self.task = asyncio.create_task(self.run(audio=data))
        elif action in {"text", "time", "web", "documents", "gmail"}:
            text = message.get("text", "")
            if action != "time" and (not isinstance(text, str) or not text.strip() or len(text) > 2000):
                await self.send({"type": "error", "message": "Enter 1–2000 characters."})
                return
            if await self.begin():
                self.task = asyncio.create_task(self.run(text=text.strip(), tool=action == "time", arguments=message.get("arguments", {}),search_action=action if action in {'web','documents','gmail'} else None))
        else:
            await self.send({"type": "error", "message": "Unknown or out-of-order action."})

    async def memory_action(self,message):
        try:
            if not self.memory or not self.memory.enabled:
                raise ValueError('Memory is disabled in this mode or configuration.')
            operation=message.get('operation','list')
            if operation=='save':
                if self.private_conversation:raise ValueError('Memory paused for this conversation.')
                self.memory.invalidate()
                self.memory.save(message.get('content'),key=message.get('id'),category=message.get('category','preferences'),due_at=message.get('due_at'),conversation_id=self.conversation_id)
            elif operation=='forget':
                if not self.memory.forget(message.get('id')):raise ValueError('Memory not found.')
            elif operation=='clear':
                if message.get('confirmation')!='FORGET ALL':raise ValueError('Type FORGET ALL to clear memory.')
                self.memory.clear()
            elif operation=='private':
                self.private_conversation=True
                self.memory.forget_conversation(self.conversation_id)
            elif operation=='new':
                self.memory.invalidate()
                self.private_conversation=False
                self.conversation_id=uuid.uuid4().hex
            elif operation!='list':raise ValueError('Unknown memory operation.')
            await self.send({'type':'memory_view','items':self.memory.list(),
                             'private':self.private_conversation,'notice':self.memory.notice})
        except (ValueError,OSError,TypeError,sqlite3.Error):
            await self.send({'type':'error','message':'Memory action failed. Check the private vault, summary, ID and confirmation.'})
        finally:
            self.release()
            await self.state(State.IDLE)

    async def memory_command(self,text):
        """Direct user instructions only; retrieved/model text never reaches this router."""
        from .tools import normalize_request
        command=normalize_request(text)
        if not self.memory or not self.memory.enabled:
            if command.startswith(('remind me','remember','forget','show my memories','show me my memories','what do you remember','do not remember',"don't remember")):
                return 'Personal memory is disabled in this mode or local configuration.'
            return None
        if command in {"don't remember this conversation",'do not remember this conversation'}:
            self.private_conversation=True
            self.memory.forget_conversation(self.conversation_id)
            return 'This conversation is now private. Its queued and saved conversation memories have been removed, and I will not remember further turns until you start a new conversation.'
        if command in {'start a new conversation','new conversation'}:
            self.memory.invalidate()
            self.private_conversation=False
            self.conversation_id=uuid.uuid4().hex
            return 'A fresh conversation is ready. Your saved memories are still available.'
        if command in {'what do you remember about me','show my memories','show me my memories'}:
            items=self.memory.list()
            await self.send({'type':'memory_view','items':items,'private':self.private_conversation,'notice':self.memory.notice})
            selected=[i for i in items if i['category'] not in {'pending','recent'}]
            return ('Here are some saved notes: '+' '.join(i['content'] for i in selected[:3]))[:self.config.max_response_chars] if selected else 'I have no saved personal notes yet. You can tell me, Remember this, followed by what you want me to keep.'
        if command in {'forget everything','forget all memories'}:
            self.memory.clear()
            return 'I removed my stored memory notes, rebuilt the search index, and cleared recent conversation context.'
        import re
        # Normalize only the prefix; preserve the original fact's spelling/case.
        original=re.sub(r'^(?:hey\s+)?april[\s,:!.-]*','',text.strip(),flags=re.I)
        original=re.sub(r'^please\s+','',original,flags=re.I)
        reminder=re.fullmatch(r'remind me in (\d{1,4}) (minutes?|hours?|days?) to (.+)',original.strip(' .!?'),re.I)
        if reminder:
            if self.private_conversation:return 'Memory is paused; start a new conversation before saving a reminder.'
            from datetime import datetime,timedelta,timezone
            from zoneinfo import ZoneInfo
            count=int(reminder[1]);unit=reminder[2].casefold().rstrip('s')
            seconds=count*{'minute':60,'hour':3600,'day':86400}[unit]
            if not 60<=seconds<=365*86400:raise ValueError('Reminder interval must be between one minute and one year.')
            due=datetime.now(timezone.utc)+timedelta(seconds=seconds)
            item=self.memory.save(reminder[3],category='projects',key='reminder-'+uuid.uuid4().hex,
                                  due_at=due.isoformat(),conversation_id=self.conversation_id)
            await self.send({'type':'memory_saved','item':item})
            return 'Reminder saved for '+due.astimezone(ZoneInfo(self.config.timezone)).strftime('%B %d at %I:%M %p %Z')+'. April must be running for the notification.'
        match=re.match(r'(?:remember this|remember that|remember)\s*[:,]?\s+(.+)',original,re.I)
        if match:
            if self.private_conversation:return 'Memory is paused for this conversation. Start a new conversation before saving a note.'
            item=self.memory.save(match[1],conversation_id=self.conversation_id)
            await self.send({'type':'memory_saved','item':item})
            return 'I saved this note: '+item['content']
        match=re.match(r'forget\s+(.+)',original,re.I)
        if match:
            count=self.memory.forget(match[1].strip(' .'))
            return 'That memory has been removed, along with recent conversation context.' if count else 'I could not find an exact memory match. Open My memories and delete the note you mean.'
        return None

    async def run(self, text="", audio=None, tool=False, arguments=None,search_action=None, sources_override=None, job_started=None, inherited_timings=None):
        timings = dict(inherited_timings or {})
        started = time.perf_counter() if job_started is None else job_started
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                with tempfile.TemporaryDirectory(prefix="april-") as directory:
                    root = Path(directory)
                    if audio is not None:
                        recording = root / "input.wav"
                        recording.write_bytes(audio)
                        tick = time.perf_counter()
                        text = await self.backends.transcribe(recording)
                        timings["stt_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    await self.send({"type": "transcript", "text": "What time is it?" if tool else text})
                    if not tool and not search_action and is_goodbye_request(text):
                        await self.send({"type":"control","action":"shutdown"})
                        self.release()
                        await self.state(State.IDLE)
                        return
                    memory_reply=None
                    if not tool and not search_action and sources_override is None:
                        memory_reply=await self.memory_command(text)
                    from .tools import normalize_request
                    command=normalize_request(text)
                    if not tool and not search_action and sources_override is None and command.startswith(
                        ('schedule a meeting','schedule an appointment','create an event','add an event','add a calendar event')):
                        from .assistant_actions import run
                        await run(self,{"type":"calendar_draft","text":text},started=started,timings=timings)
                        return
                    if not tool and not search_action and sources_override is None and command in {'edit my calendar','change my calendar'}:
                        await self.send({"type":"control","action":"calendar"})
                        self.release()
                        await self.state(State.IDLE)
                        return
                    if not tool and not search_action and sources_override is None and command in {'debug this','help me debug this'}:
                        await self.send({"type":"control","action":"debug"})
                        self.release()
                        await self.state(State.IDLE)
                        return
                    if not tool and not search_action and sources_override is None and command in {
                        'brief me on my day','what do i have planned','what do i have planned this week',
                        'give me a weekly recap','summarize my emails','any internship updates',
                        'what do i have planned today','what do i have planned tomorrow',
                        "what's on my calendar",'what is on my calendar','what am i doing today'}:
                        from .assistant_actions import run
                        await run(self,{"type":"briefing","text":text},started=started,timings=timings)
                        return
                    # Spoken/typed clock queries must use the actual clock,
                    # not the model's training data. Preserve the real transcript.
                    if not tool and not search_action and is_time_request(text):
                        tool, arguments = True, {}
                    if self.machine.state != State.THINKING:
                        await self.state(State.THINKING)
                    tick = time.perf_counter()
                    sources=[]
                    model_called=False
                    from .memory import local_conversation
                    if memory_reply is not None:
                        reply=memory_reply[:self.config.max_response_chars]
                        action=None
                    elif not tool:
                        detected,query=('context',text) if sources_override is not None else route_knowledge(text,automatic_web_search=self.config.automatic_web_search and self.config.mode=='live' and not local_conversation(command) and not (self.memory and not self.private_conversation and self.memory.is_followup(command)))
                        action=search_action or detected
                        if action:
                            if self.config.mode=='simulation':
                                raise BackendError('simulation_search_disabled','Private/external retrieval is disabled in simulation. Use live mode after local setup.')
                            query=text if search_action else query
                            await self.send({'type':'lookup','state':'searching','kind':action,
                                             'provider':self.config.web_provider if action=='web' else action})
                            sources=sources_override if action=='context' else await retrieve(self.config,action,query)
                            timings['retrieval_ms']=round((time.perf_counter()-tick)*1000,1)
                            await self.send({'type':'sources','sources':sources})
                            tick=time.perf_counter()
                            if sources:
                                reply=await self.respond_with_memory(text,sources=sources)
                                model_called=True
                            else:reply='No matching sources were returned. I cannot verify an answer from this search.'
                        else:
                            await self.send({'type':'lookup','state':'skipped','kind':'local',
                                             'reason':'Web lookup not selected for this request.'})
                            reply=await self.respond_with_memory(text)
                            model_called=True
                    else:
                        await self.send({'type':'lookup','state':'clock','kind':'local'})
                        reply=current_time(arguments,self.config.timezone)
                    if tool or model_called:
                        timings["tool_ms" if tool else "llm_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    await self.send({"type": "reply", "text": reply, "source": "current_time" if tool else ('retrieval' if action else self.config.mode)})
                    output = root / "reply.wav"
                    tick = time.perf_counter()
                    await self.backends.synthesize(spoken_answer(reply, len(sources)), output)
                    if self.memory and memory_reply is None and not self.private_conversation and model_called:
                        job=self.memory.completed(text,reply,self.backends,allow_extract=not sources and search_action is None and sources_override is None,conversation_id=self.conversation_id,source_kind=action or 'conversation')
                        if job:
                            await self.send({'type':'memory_status','message':'Considering a short personal memory in the background…'})
                            observer=asyncio.create_task(self.memory_finished(job,self.memory.epoch))
                            observer.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
                    timings["tts_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    timings["server_total_ms"] = round((time.perf_counter() - started) * 1000, 1)
                    await self.send({"type": "timings", "values": timings, "mode": self.config.mode})
                    # Speaking starts only on the client's playback-start acknowledgment.
                    if self.config.mode == "simulation":
                        await self.send({"type": "simulation", "message": "Speech playback simulated; no TTS audio."})
                        self.release()
                        await self.state(State.IDLE)
                    else:
                        await self.send({"type": "audio", "audio": base64.b64encode(output.read_bytes()).decode()})
                        # Wait for client playback events with an independent timeout.
                        self.task = asyncio.create_task(self.playback_deadline())
        except asyncio.CancelledError:
            raise
        except BackendError as exc:
            await self.error(str(exc), exc.code)
        except Exception as exc:
            # Never expose exception bodies, prompts, paths or remote responses.
            hints = {FileNotFoundError: "Speech binary or model missing. Check local configuration.",
                     TimeoutError: "Request timed out. Try a shorter request.",
                     ValueError: "Input or model output was invalid. Check configuration and retry."}
            await self.error(hints.get(type(exc), "Local backend failed. Check Ollama, speech binaries and model paths; then retry."))

    async def memory_finished(self,job,epoch):
        try:
            await asyncio.shield(job)
            if epoch==self.memory.epoch:
                await self.send({'type':'memory_status','message':self.memory.notice or
                                 'Memory analysis finished. Open My memories to review selected notes.'})
        except (asyncio.CancelledError,RuntimeError,ConnectionError):pass

    async def respond_with_memory(self,text,*,sources=None):
        context=None
        if self.memory and not self.private_conversation:
            try:
                context=self.memory.context(text)
                if context:
                    await self.send({'type':'memory_status','message':
                        'Using '+str(len(context['memories']))+' saved notes and '+str(len(context['recent_turns']))+' recent turns.'})
            except (OSError,ValueError,sqlite3.Error):
                self.memory.notice='Memory is unavailable; this reply has no saved context.'
                await self.send({'type':'memory_status','message':self.memory.notice})
        if hasattr(self.backends,'respond_with_context'):
            return await self.backends.respond_with_context(text,sources=sources,context=context)
        return await self.backends.respond(text,sources=sources) if sources else await self.backends.respond(text)

    async def playback_deadline(self):
        await asyncio.sleep(self.config.playback_timeout_seconds)
        await self.error("Playback timed out. Check the selected output and retry.")

    async def playback_started(self):
        if self.owns_gate and self.machine.state == State.THINKING:
            await self.state(State.SPEAKING)
