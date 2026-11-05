"""Private-action UI fixture: no real calendar account, project execution or models."""
import asyncio
from datetime import datetime,timedelta,timezone
from pathlib import Path
import socket
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.async_api import async_playwright
from april.config import Config
from april.server import create_app
from scripts.browser_playback_check import ToneBackend

async def main():
    with tempfile.TemporaryDirectory(prefix='april-ui-fixture-') as directory:
        root=Path(directory);(root/'bug.py').write_text('def broken(:\n pass\n')
        listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        config=Config(port=port,debug_project_root=str(root),automatic_web_search=False,avatar_3d=False)
        server=uvicorn.Server(uvicorn.Config(create_app(config,ToneBackend()),log_level='warning'))
        task=asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:await asyncio.sleep(.05)
            async with async_playwright() as p:
                browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                page=await browser.new_page()
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{port}/?panel=debug')
                await page.wait_for_function("() => document.body.dataset.state==='idle'")
                await page.locator('#debug-file').fill('bug.py')
                await page.locator('#review-file').click()
                await page.wait_for_selector('#action-review:not([hidden])')
                await page.wait_for_function("() => document.body.dataset.state==='idle'")
                assert await page.locator('#approve-action').is_enabled()
                assert 'bug.py' in await page.locator('#review-summary').inner_text()
                await page.locator('#sources-panel summary').click()
                content=await page.locator('#sources').text_content()
                assert 'bug.py:1:' in content, {'sources':content,'error':await page.locator('#error').inner_text()}
                await page.locator('#reject-action').click()
                await page.wait_for_selector('#action-review[hidden]',state='attached')
                await page.wait_for_function("() => document.body.dataset.state==='idle'")
                await page.locator('#calendar-panel summary').click()
                start=datetime.now(timezone.utc)+timedelta(days=1)
                await page.locator('#event-title').fill('Public review fixture')
                await page.locator('#event-start').fill(start.isoformat())
                await page.locator('#event-end').fill((start+timedelta(hours=1)).isoformat())
                await page.locator('#calendar-propose').click()
                await page.wait_for_selector('#action-review:not([hidden])')
                await page.wait_for_function("() => document.body.dataset.state==='idle'")
                assert 'Public review fixture' in await page.locator('#review-summary').inner_text()
                assert 'no calendar change' in await page.locator('#reply').inner_text()
                await page.locator('#reject-action').click()
                assert not errors,errors
                print('Browser fixture: file source/line review, approval availability/discard, calendar proposal and no implicit write passed.')
                await browser.close()
        finally:
            server.should_exit=True;await task

if __name__=='__main__':asyncio.run(main())
