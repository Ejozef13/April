"""Run with a Python that has Playwright installed; server must use simulation.

Uses Chromium's fake microphone. This is UI evidence, never hardware evidence.
"""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    root = Path(__file__).resolve().parents[1]
    evidence = root / 'docs' / 'evidence'
    artifacts = root / 'artifacts'
    evidence.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path='/usr/bin/chromium', args=[
            '--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
        context = await browser.new_context(viewport={'width':1100,'height':1050}, permissions=['microphone'])
        page = await context.new_page()
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        frames = []
        async def capture():
            while True:
                frames.append(await page.screenshot())
                await asyncio.sleep(.2)
        await page.goto('http://127.0.0.1:8765')
        await page.wait_for_function("() => document.body.dataset.state === 'idle'")
        assert 'SIMULATION' in await page.locator('#mode').inner_text()
        assert await page.locator('#mouth').evaluate("el => getComputedStyle(el).visibility === 'hidden'")
        assert await page.locator('#closed-mouth').evaluate("el => getComputedStyle(el).visibility === 'visible'")
        assert await page.locator('.circuit-board').evaluate("el => getComputedStyle(el).pointerEvents === 'none'")
        await page.emulate_media(reduced_motion='reduce')
        assert await page.locator('.circuit-pulses').evaluate("el => getComputedStyle(el).animationName === 'none'")
        await page.emulate_media(reduced_motion='no-preference')
        recording = asyncio.create_task(capture())
        await page.screenshot(path=str(evidence / 'simulation-idle.png'), full_page=True)
        await page.locator('#text').fill('Help me choose one small task for today.')
        await page.locator('#send').click()
        await page.wait_for_function("() => document.body.dataset.state === 'thinking'")
        assert await page.locator('#mouth').evaluate("el => getComputedStyle(el).visibility === 'visible'")
        assert await page.locator('#closed-mouth').evaluate("el => getComputedStyle(el).visibility === 'hidden'")
        await page.wait_for_function("() => document.querySelector('#reply').textContent.includes('[Simulated reply]')")
        await page.wait_for_function("() => document.body.dataset.state === 'idle'")
        await page.screenshot(path=str(evidence / 'simulation-reply.png'), full_page=True)
        await page.locator('#timings').locator('..').locator('summary').click()
        async with page.expect_download() as download_event:
            await page.locator('#export-timing').click()
        download = await download_event.value
        saved = artifacts / 'fixture-timing-export.json'
        await download.save_as(str(saved))
        sample = json.loads(saved.read_text())
        assert sample['mode'] == 'simulation'
        assert sample['playback'] == 'simulated'
        assert sample['transcript_included'] is False and sample['audio_included'] is False
        assert 'Help me choose' not in saved.read_text()
        await page.locator('#face-view').click()
        await page.wait_for_function("() => document.body.classList.contains('face-view')")
        assert await page.locator('#stop').is_visible()
        assert await page.locator('#mute').is_visible()
        await page.screenshot(path=str(evidence / 'simulation-face-view.png'), full_page=True)
        await page.locator('#face-view').click()
        await page.wait_for_function("() => !document.body.classList.contains('face-view')")
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(evidence / 'simulation-mobile.png'), full_page=True)
        assert await page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
        await page.set_viewport_size({'width':1100,'height':1050})
        await page.locator('.setup-panel summary').click()
        await page.locator('#check-setup').click()
        await page.wait_for_function("() => document.querySelector('#setup-results').textContent.includes('Fixtures only')")
        await page.locator('#record').click()
        await page.wait_for_function("() => document.querySelector('#mic').textContent.includes('recording ·')")
        await page.wait_for_function("() => document.querySelector('#mic-level').value > 0")
        assert await page.locator('#mouth').evaluate("el => getComputedStyle(el).visibility === 'visible'")
        await page.screenshot(path=str(evidence / 'simulation-listening.png'), full_page=True)
        await asyncio.sleep(.8)
        await page.locator('#record').click()
        await page.wait_for_function("() => document.querySelector('#transcript').textContent.includes('[Simulated transcript]')")
        await page.wait_for_function("() => document.body.dataset.state === 'idle'")
        await page.locator('#time').click()
        await page.wait_for_function("() => document.querySelector('#reply').textContent.includes('It is ')")
        await page.wait_for_function("() => document.body.dataset.state === 'idle'")
        await page.locator('#text').fill('Cancel this request')
        await page.locator('#send').click()
        await page.wait_for_function("() => document.body.dataset.state === 'thinking'")
        await page.locator('#stop').click()
        await page.wait_for_function("() => document.body.dataset.state === 'idle'")
        await asyncio.sleep(.6)
        assert 'Cancel this request' not in await page.locator('#reply').inner_text()
        assert not errors, errors
        recording.cancel()
        try:
            await recording
        except asyncio.CancelledError:
            pass
        # Actual browser frames, no narration or claimed speech/model inference.
        process = await asyncio.create_subprocess_exec('ffmpeg','-y','-loglevel','error',
            '-f','image2pipe','-framerate','5','-i','-','-c:v','libvpx-vp9',
            str(artifacts / 'simulation-walkthrough.webm'), stdin=asyncio.subprocess.PIPE)
        await process.communicate(b''.join(frames))
        assert process.returncode == 0
        (artifacts / 'browser-check.json').write_text(json.dumps({'passed':True,'page_errors':errors,
            'microphone':'Chromium fake device','models':'simulated','speech_playback':'simulated',
            'tool':'real deterministic server clock','video_frames':len(frames)}, indent=2))
        await browser.close()
        print('Browser checks passed; screenshots and simulation walkthrough saved.')


asyncio.run(main())
