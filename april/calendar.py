"""Dedicated CalDAV collection: bounded reads and explicit conditional writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import uuid
from urllib.parse import urlparse, urljoin

import httpx
from defusedxml import ElementTree

from .errors import BackendError


def credentials(config):
    path=Path(config.caldav_credentials).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size>4096 or path.stat().st_mode & 0o077:
        raise BackendError('calendar_not_configured','Set up the private CalDAV credentials using python -m april.calendar_setup init.')
    try:
        data=json.loads(path.read_text())
        return data['username'],data['password']
    except (OSError,ValueError,KeyError):
        raise BackendError('calendar_credentials_invalid','CalDAV credentials are invalid; do not paste them into chat.')


async def request(config, method, resource='', *, content=None, headers=None, transport=None):
    auth=credentials(config)
    url=config.caldav_url.rstrip('/')+'/'+resource
    async with httpx.AsyncClient(auth=auth,timeout=12,trust_env=False,follow_redirects=False,transport=transport) as client:
        try:
            async with client.stream(method,url,content=content,headers=headers) as response:
                chunks=bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks)>512_000:
                        raise BackendError('calendar_response_large','Calendar response exceeded the local limit.')
                if response.status_code==412:
                    raise BackendError('calendar_conflict','The event changed after review. Read it again before proposing an edit.')
                response.raise_for_status()
                if method in {'PUT','MKCALENDAR'} and response.status_code not in {200,201,204}:
                    raise BackendError('calendar_write_unconfirmed','The server has not confirmed completion. Check the calendar before retrying.')
                return bytes(chunks),response.headers
        except httpx.HTTPError:
            raise BackendError('calendar_unavailable','CalDAV request failed. Check the local calendar service and private credentials; no change is claimed.')


async def events(config, *, transport=None, period=None, now=None):
    from icalendar import Calendar
    start=now or datetime.now(timezone.utc)
    if period in {'today','tomorrow'}:
        from zoneinfo import ZoneInfo
        local=start.astimezone(ZoneInfo(config.timezone))
        start=local.replace(hour=0,minute=0,second=0,microsecond=0)
        if period=='tomorrow':start+=timedelta(days=1)
        end=(start+timedelta(days=1)).astimezone(timezone.utc)
        start=start.astimezone(timezone.utc)
    elif period is None:end=start+timedelta(days=7)
    else:raise ValueError('Unsupported calendar period')
    stamp=lambda value:value.strftime('%Y%m%dT%H%M%SZ')
    body=f'''<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
<d:prop><d:getetag/><c:calendar-data><c:expand start="{stamp(start)}" end="{stamp(end)}"/></c:calendar-data></d:prop>
<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="{stamp(start)}" end="{stamp(end)}"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>'''
    raw,_=await request(config,'REPORT',content=body.encode(),headers={'Depth':'1','Content-Type':'application/xml'},transport=transport)
    try:
        root=ElementTree.fromstring(raw)
        output=[]
        for response in root.findall('{DAV:}response'):
            data=response.find('.//{urn:ietf:params:xml:ns:caldav}calendar-data')
            if data is None or not data.text:continue
            for event in Calendar.from_ical(data.text).walk('VEVENT'):
                output.append({'title':str(event.get('SUMMARY','Untitled'))[:120],
                    'excerpt':str(event.get('DTSTART').dt)+' → '+str(event.get('DTEND').dt if event.get('DTEND') else '')+
                              '\n'+str(event.get('DESCRIPTION',''))[:800],
                    'kind':'calendar','uid':str(event.get('UID',''))[:100],
                    'etag':response.findtext('.//{DAV:}getetag'),
                    'start':event.get('DTSTART').dt.isoformat(),
                    'end':event.get('DTEND').dt.isoformat() if event.get('DTEND') else ''})
                if len(output)>=20:return output
        return output
    except (ValueError,AttributeError,TypeError):
        raise BackendError('calendar_invalid_response','Calendar data could not be read safely.')


def proposal(values):
    if not isinstance(values,dict) or set(values)-{'title','start','end','uid','etag'}:
        raise ValueError('Invalid event fields')
    title=values.get('title','')
    if not isinstance(title,str) or not title.strip() or len(title)>120 or any(c in title for c in '\r\n'):
        raise ValueError('Use an event title of 1–120 characters')
    start,end=(datetime.fromisoformat(values.get(k,'')) for k in ('start','end'))
    if not start.tzinfo or not end.tzinfo or not timedelta(0)<end-start<=timedelta(days=7):
        raise ValueError('Use timezone-aware start/end, with duration under seven days')
    uid=values.get('uid') or 'april-'+str(uuid.uuid4())
    import re
    if not isinstance(uid,str) or not re.fullmatch(r'april-[a-f0-9-]{36}',uid):
        raise ValueError('Only April-created events can be edited')
    etag=values.get('etag')
    if values.get('uid') and not etag:
        raise ValueError('Read the current event version before proposing an edit')
    if etag is not None and (not isinstance(etag,str) or len(etag)>150 or '\n' in etag or '\r' in etag):
        raise ValueError('Invalid event version')
    return {'title':title.strip(),'start':start.isoformat(),'end':end.isoformat(),
            'uid':uid,'etag':etag,'id':secrets.token_urlsafe(24)}


async def commit(config, item, *, transport=None):
    from icalendar import Calendar, Event
    if item['etag']:
        raw,existing_headers=await request(config,'GET',item['uid']+'.ics',transport=transport)
        if existing_headers.get('etag')!=item['etag']:
            raise BackendError('calendar_conflict','The event changed; review it again.')
        calendar=Calendar.from_ical(raw)
        candidates=calendar.walk('VEVENT')
        if len(candidates)!=1 or any(key in candidates[0] for key in ('RRULE','RECURRENCE-ID','ATTENDEE','ORGANIZER')):
            raise ValueError('Recurring or invitation events require a calendar client')
        event=candidates[0]
        for field in ('SUMMARY','DTSTART','DTEND','DTSTAMP'):
            if field in event:del event[field]
    else:
        calendar=Calendar()
        event=Event()
    if 'PRODID' not in calendar:calendar.add('prodid','-//APRIL//Reviewed calendar event//EN')
    if 'VERSION' not in calendar:calendar.add('version','2.0')
    for key,value in [('uid',item['uid']),('summary',item['title']),('dtstamp',datetime.now(timezone.utc)),
                      ('dtstart',datetime.fromisoformat(item['start']).astimezone(timezone.utc)),('dtend',datetime.fromisoformat(item['end']).astimezone(timezone.utc))]:
        if key in event:del event[key]
        event.add(key,value)
    if not item['etag']:calendar.add_component(event)
    headers={'Content-Type':'text/calendar'}
    headers['If-Match' if item['etag'] else 'If-None-Match']=item['etag'] or '*'
    _,response_headers=await request(config,'PUT',item['uid']+'.ics',content=calendar.to_ical(),headers=headers,transport=transport)
    return response_headers.get('etag')


async def draft_from_text(config,text):
    from zoneinfo import ZoneInfo
    now=datetime.now(ZoneInfo(config.timezone)).isoformat()
    schema={'type':'object','properties':{key:{'type':'string'} for key in ('title','start','end')},
            'required':['title','start','end'],'additionalProperties':False}
    payload={'model':config.model,'stream':False,'format':schema,
             'messages':[{'role':'system','content':'Draft a calendar event only; do not take actions. Current local datetime: '+now+
                          '. Return title, start and end as ISO8601 with timezone offsets. If a date/time is missing return empty strings for the missing fields; do not invent them.'},
                         {'role':'user','content':text[:2000]}],
             'options':{'num_ctx':config.context_tokens,'num_predict':512}}
    if config.model.startswith('gpt-oss'):payload['think']='low'
    async with httpx.AsyncClient(trust_env=False,timeout=30) as client:
        response=await client.post(config.ollama_url.rstrip('/')+'/api/chat',json=payload)
        response.raise_for_status()
        return proposal(json.loads(response.json()['message']['content']))


def readback(config, items, *, period=None):
    """Speak verified structured calendar fields; no model decides if an event exists."""
    from datetime import date
    from zoneinfo import ZoneInfo
    zone=ZoneInfo(config.timezone)
    label=period or 'the next seven days'
    if not items:
        reply='No calendar events were returned for '+label+'.'
        return reply if len(reply)<=config.max_response_chars else 'No events returned. See calendar.'

    def parse(value):
        if not isinstance(value,str) or not value:raise ValueError('Missing event date')
        if 'T' in value or ' ' in value:
            stamp=datetime.fromisoformat(value)
            return stamp.replace(tzinfo=zone) if stamp.tzinfo is None else stamp.astimezone(zone)
        return date.fromisoformat(value)

    def day(value):return value.strftime('%A, %B ')+str(value.day)
    def clock(value):return value.strftime('%I:%M %p').lstrip('0')
    parsed=[]
    for item in items:
        start=parse(item.get('start'))
        end=parse(item['end']) if item.get('end') else None
        title=' '.join(str(item.get('title') or 'Untitled event').split())[:120]
        if isinstance(start,datetime):
            if end is not None and not isinstance(end,datetime):raise ValueError('Mixed calendar date types')
            timing='at '+clock(start)+' '+start.tzname()
            if end:
                if end<start:raise ValueError('Invalid event interval')
                if end.date()==start.date() and end.tzname()==start.tzname():
                    timing='from '+clock(start)+' to '+clock(end)+' '+end.tzname()
                else:timing='from '+clock(start)+' '+start.tzname()+' to '+day(end)+' at '+clock(end)+' '+end.tzname()
            text=title+' on '+day(start)+', '+timing+'.'
            order=start.timestamp()
        else:
            if end is not None and (isinstance(end,datetime) or end<=start):raise ValueError('Invalid all-day interval')
            text=title+', all day on '+day(start)
            if end and end>start+timedelta(days=1):text+=' through '+day(end-timedelta(days=1))
            text+='.'
            order=datetime.combine(start,datetime.min.time(),zone).timestamp()
        parsed.append((order,text))
    descriptions=[value for _,value in sorted(parsed)]
    # Fit complete events, never cut a title/time in half. Full sources stay visible.
    selected=[]
    prefix='For '+label+': '
    for value in descriptions[:3]:
        remaining=len(descriptions)-len(selected)-1
        suffix=(' '+str(remaining)+' more returned events are in the sources.') if remaining else ''
        if len(prefix+' '.join(selected+[value])+suffix)>config.max_response_chars:break
        selected.append(value)
    if not selected:
        return str(len(items))+' event'+('s' if len(items)!=1 else '')+'. See calendar sources.'
    remaining=len(descriptions)-len(selected)
    return prefix+' '.join(selected)+((' '+str(remaining)+' more returned events are in the sources.') if remaining else '')
