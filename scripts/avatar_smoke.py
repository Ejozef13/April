"""Render the local GLB with software WebGL; no real voice/model claim."""
import asyncio
from pathlib import Path
import socket
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.async_api import async_playwright
from april.config import Config
from april.server import create_app

async def main():
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(Config(mode='simulation',port=port)),log_level='warning'))
    task=asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started:await asyncio.sleep(.05)
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            page=await browser.new_page(viewport={'width':900,'height':900})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{port}/?avatar=3d')
            await page.wait_for_selector('body.avatar-ready',timeout=20000)
            await page.wait_for_selector('#avatar-3d[data-rendered=true]')
            await page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            await page.screenshot(path='/tmp/april-browser-3d.png')
            assert not errors,errors
            await page.goto(f'http://127.0.0.1:{port}/?widget=1')
            await page.wait_for_selector('body.avatar-ready',timeout=20000)
            assert await page.locator('.console').evaluate("el=>getComputedStyle(el).display==='none'")
            await page.locator('#avatar-3d canvas').click()
            result=await page.evaluate('window.aprilDesktop.snapshot()')
            assert result['request']=='expand',result
            print('Actual GLB/software WebGL rendering and click-to-expand passed. Voice is simulated.')
            await browser.close()
    finally:
        server.should_exit=True;await task

if __name__=='__main__':asyncio.run(main())
