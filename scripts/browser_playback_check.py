"""Browser playback regression checks with a real WAV tone and fixture backends.

No pretrained inference or physical audio is claimed. Requires Playwright and
Chromium in the invoking Python environment. Starts/stops only its own server.
"""
import asyncio
import math
import socket
import struct
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.async_api import async_playwright
from april.config import Config
from april.server import create_app
from april.documents import build_index


class ToneBackend:
    async def respond(self, text, *, sources=None):
        await asyncio.sleep(.1)
        return 'Fixture source-backed reply [1].' if sources else 'Fixture reply; audio is a test tone.'

    async def synthesize(self, text, output):
        with wave.open(str(output), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b''.join(struct.pack('<h', int(1000 * math.sin(i * math.tau * 440 / 16000)))
                                     for i in range(32000)))


async def main():
    temporary=tempfile.TemporaryDirectory(prefix='april-browser-docs-')
    folder=Path(temporary.name)/'aprilfiles';folder.mkdir()
    (folder/'project.md').write_text('April wears a purple collar. This is a public test fixture.')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    config=Config(automatic_web_search=False,port=port,document_roots=[str(folder)],documents_index_path=str(Path(temporary.name)/'index.sqlite3'))
    build_index(config)
    server = uvicorn.Server(uvicorn.Config(create_app(config, ToneBackend()), log_level='warning'))
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started:
            if server_task.done():
                await server_task
                raise RuntimeError('Fixture server failed to start')
            await asyncio.sleep(.05)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            try:
                page = await browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{port}')
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                await page.locator('#text').fill('Hello')
                await page.locator('#send').click()
                await page.wait_for_function("() => document.body.dataset.state === 'speaking'")
                assert await page.locator('#tail').evaluate("el => getComputedStyle(el).animationName === 'tail-wag'")
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                assert await page.locator('#tail').evaluate("el => getComputedStyle(el).animationName === 'none'")
                assert not await page.locator('#error').inner_text(), await page.locator('#error').inner_text()
                assert not errors, errors
                print('Real WAV tone playback: speaking -> idle passed.')

                # A browser can block asynchronous playback despite the form
                # interaction. Retry must use the same WAV, not another model job.
                await page.evaluate('''() => {
                    window.originalAprilPlay = HTMLMediaElement.prototype.play;
                    let first = true;
                    HTMLMediaElement.prototype.play = function() {
                        if (first) { first = false; return Promise.reject(new DOMException('blocked', 'NotAllowedError')); }
                        return window.originalAprilPlay.call(this);
                    };
                }''')
                await page.locator('#send').click()
                await page.locator('#play-reply').wait_for(state='visible')
                await page.locator('#play-reply').click()
                await page.wait_for_function("() => document.body.dataset.state === 'speaking'")
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                assert not await page.locator('#error').inner_text()
                print('Blocked autoplay -> explicit user retry -> playback passed.')

                # Reproduce an end/cleanup race while play() is still pending.
                # Previously cleanup's src reset could surface as the user's
                # misleading "media was removed" rejection after completion.
                await page.evaluate('''() => {
                    window.aprilRaceStates = [];
                    window.aprilRaceObserver = new MutationObserver(() => {
                        window.aprilRaceStates.push(document.body.dataset.state);
                    });
                    window.aprilRaceObserver.observe(document.body, {attributes:true, attributeFilter:['data-state']});
                    HTMLMediaElement.prototype.play = function() {
                        return new Promise((resolve, reject) => {
                            setTimeout(() => {
                                this.onplaying?.();
                                setTimeout(() => {
                                    this.onended?.();
                                    reject(new DOMException('media was removed', 'AbortError'));
                                }, 50);
                            }, 20);
                        });
                    };
                }''')
                await page.locator('#send').click()
                # The injected speaking state lasts only 50ms. Observe changes
                # rather than relying on animation-frame polling to catch it.
                await page.wait_for_function("() => window.aprilRaceStates.includes('speaking') && document.body.dataset.state === 'idle'")
                await page.evaluate('() => window.aprilRaceObserver.disconnect()')
                await asyncio.sleep(.15)
                assert not await page.locator('#error').inner_text()
                assert await page.locator('#play-reply').is_hidden()
                print('Completion while play promise is pending: no spurious error passed.')

                # Preserve the first media error when teardown rejects play().
                await page.evaluate('''() => {
                    HTMLMediaElement.prototype.play = function() {
                        return new Promise((resolve, reject) => {
                            setTimeout(() => {
                                this.dispatchEvent(new Event('error'));
                                reject(new DOMException('media was removed', 'AbortError'));
                            }, 20);
                        });
                    };
                }''')
                await page.locator('#send').click()
                await page.wait_for_function("() => document.querySelector('#error').textContent.includes('audio loading failed')")
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                assert 'media was removed' not in await page.locator('#error').inner_text()
                print('Original media error survives cleanup passed.')

                await page.evaluate('''() => {
                    HTMLMediaElement.prototype.play = window.originalAprilPlay;
                }''')
                await page.locator('#send').click()
                await page.wait_for_function("() => document.body.dataset.state === 'speaking'")
                await page.locator('#stop').click()
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                await asyncio.sleep(.15)
                assert not await page.locator('#error').inner_text()
                await page.locator('#send').click()
                await page.wait_for_function("() => document.body.dataset.state === 'speaking'")
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                assert not await page.locator('#error').inner_text()
                assert not errors, errors
                print('Stop during playback, then successful retry passed.')
                await page.locator('#knowledge-panel summary').click()
                await page.locator('#text').fill('purple collar')
                await page.locator('#search-documents').click()
                await page.wait_for_function("() => document.querySelector('#sources').textContent.includes('project.md')")
                await page.locator('#sources-panel summary').click()
                assert 'purple collar' in await page.locator('#sources').inner_text()
                assert 'Lookup complete' in await page.locator('#lookup-status').inner_text()
                await page.wait_for_function("() => document.body.dataset.state === 'speaking'")
                await page.wait_for_function("() => document.body.dataset.state === 'idle'")
                assert '[1]' in await page.locator('#reply').inner_text()
                assert not await page.locator('#error').inner_text()
                print('Approved-folder retrieval -> visible source -> fixture answer -> WAV playback passed.')
            finally:
                await browser.close()
    finally:
        server.should_exit = True
        await server_task
        listener.close()
        temporary.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
