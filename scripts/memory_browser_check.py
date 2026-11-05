"""Actual browser + private temporary vault; fixture voice/model, no personal data."""
import asyncio
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
    with tempfile.TemporaryDirectory(prefix='april-memory-ui-') as directory:
        listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        config=Config(port=port,memory_vault=directory+'/vault',avatar_3d=False,automatic_web_search=False)
        server=uvicorn.Server(uvicorn.Config(create_app(config,ToneBackend()),log_level='warning'))
        task=asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:await asyncio.sleep(.05)
            async with async_playwright() as p:
                browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                page=await browser.new_page()
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{port}/')
                await page.wait_for_function("document.body.dataset.state==='idle'")
                await page.locator('#memory-panel summary').click()
                await page.locator('#memory-content').fill('I prefer coding hints before full solutions.')
                await page.locator('#memory-save').click()
                await page.wait_for_selector('#memory-list li')
                assert len(list((Path(directory)/'vault/preferences').glob('*.md')))==1
                await page.reload()
                await page.wait_for_function("document.body.dataset.state==='idle'")
                await page.locator('#memory-panel summary').click()
                await page.locator('#memory-refresh').click()
                await page.wait_for_selector('#memory-list li')
                await page.locator('#memory-list button').click()
                await page.locator('#memory-content').fill('I prefer concise Python examples.')
                await page.locator('#memory-save').click()
                await page.wait_for_function("document.querySelector('#memory-list').textContent.includes('concise Python')")
                await page.locator('#memory-delete').click()
                await page.wait_for_function("document.querySelector('#memory-list').children.length===0")
                await page.locator('#memory-private').click()
                await page.wait_for_function("document.querySelector('#memory-status').textContent.includes('Private conversation')")
                await page.locator('#memory-new').click()
                await page.wait_for_function("document.querySelector('#memory-status').textContent.includes('Local memory active')")
                assert not errors,errors
                print('Browser memory save/reload/edit/delete and private/new-conversation controls passed. Model and audio are fixtures.')
                await browser.close()
        finally:
            server.should_exit=True;await task

if __name__=='__main__':asyncio.run(main())
