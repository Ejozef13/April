"""Explicit private review actions; model text never grants execution/write access."""
import secrets
import asyncio
import time

from .errors import BackendError
from .state import State


async def _run(session,message,*,started=None,timings=None):
    started=time.perf_counter() if started is None else started
    preparation=time.perf_counter()
    timings=dict(timings or {})
    kind=message['type']
    try:
        if session.machine.state != State.THINKING:
            await session.state(State.THINKING)
        if session.config.mode=='simulation':
            raise BackendError('simulation_private_disabled','Private screen/file/calendar actions are disabled in simulation.')
        if kind in {'debug_file','debug_screen'}:
            from .debugging import review_file,screen_text
            if kind=='debug_file':
                source,item=review_file(session.config,message.get('file'))
                session.pending_review={'kind':'execute','item':item,'expires':time.monotonic()+300}
                await session.send({'type':'review','kind':'execute','id':item['id'],
                    'summary':'Run '+item['file']+' in a networkless, read-only container (10s/256 MB). Only approved aprilfiles is mounted.'})
            else:
                source=await screen_text(message.get('image'))
            await session.run(text='Review this code context. Give a diagnostic hint, citing actual file/line evidence when present. OCR line numbers are uncertain; do not claim execution.',
                              sources_override=[source],job_started=started,
                              inherited_timings={**timings,'preparation_ms':round((time.perf_counter()-preparation)*1000,1)})
            return
        if kind in {'calendar_read','briefing'}:
            from .calendar import events
            question=message.get('text','').casefold()
            sources=[]
            if not any(word in question for word in ('emails','internship')):
                sources=await events(session.config)
            if kind=='briefing' and 'have planned' not in question:
                from .gmail import search_gmail
                query='newer_than:7d'
                if 'internship' in question:query+=' (internship OR interview OR recruiter OR application)'
                mail=await search_gmail(session.config,query)
                sources=sources[:3]+mail[:3]
            await session.send({'type':'calendar_events','events':sources if kind=='calendar_read' else []})
            if not sources:
                sources=[{'title':'Completed private query','kind':'status',
                          'excerpt':'The configured private query completed and returned no matching items in its bounded date range.'}]
            await session.run(text=message.get('text') or 'Summarize the next seven days. Mention that results are bounded, not an exhaustive inbox/calendar audit.',
                              sources_override=sources[:6],job_started=started,
                              inherited_timings={**timings,'preparation_ms':round((time.perf_counter()-preparation)*1000,1)})
            return
        if kind in {'calendar_propose','calendar_draft'}:
            from .calendar import proposal,draft_from_text
            item=await draft_from_text(session.config,message['text']) if kind=='calendar_draft' else proposal(message.get('event'))
            session.pending_review={'kind':'calendar','item':item,'expires':time.monotonic()+300}
            await session.send({'type':'review','kind':'calendar','id':item['id'],
                                'summary':('Update ' if item['etag'] else 'Create ')+item['title']+'\n'+item['start']+' → '+item['end'],
                                'event':item})
        elif kind in {'calendar_confirm','debug_execute'}:
            pending=getattr(session,'pending_review',None)
            session.pending_review=None  # Every approval token is single-use.
            expected='calendar' if kind=='calendar_confirm' else 'execute'
            if (not pending or pending['kind']!=expected or pending['expires']<time.monotonic()
                    or not isinstance(message.get('id'),str)
                    or not secrets.compare_digest(message['id'],pending['item']['id'])):
                raise ValueError('Review expired or does not match. Prepare it again.')
            if kind=='calendar_confirm':
                from .calendar import commit
                etag=await commit(session.config,pending['item'])
                await session.send({'type':'action_result','message':'Calendar write completed. Event version: '+str(etag or 'not supplied')})
            else:
                from .debugging import execute
                result=await execute(session.config,pending['item'])
                await session.send({'type':'action_result','message':str(result)})
                await session.run(text='Give a debugging hint based on this actual approved run. Cite a traceback line if present; do not claim a fix was applied.',
                                  sources_override=[{'title':pending['item']['file']+' execution',
                                      'kind':'execution','excerpt':str(result)[:12000]}],job_started=started,
                                  inherited_timings={**timings,'preparation_ms':round((time.perf_counter()-preparation)*1000,1)})
                return
        session.release()
        await session.state(State.IDLE)
    except BackendError as exc:
        await session.error(str(exc),exc.code)
    except Exception:
        await session.error('Private action failed. Check optional dependencies, approved file, calendar setup or execution image. No successful change is claimed.','private_action_failed')


async def run(session,message,*,started=None,timings=None):
    try:
        async with asyncio.timeout(session.config.timeout_seconds):
            await _run(session,message,started=started,timings=timings)
    except TimeoutError:
        await session.error('Private action timed out; no successful completion is claimed.','private_action_timeout')
