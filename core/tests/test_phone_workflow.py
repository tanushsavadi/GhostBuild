"""Phone-only guidance uses the real generic engine and protects deliberate progress."""
from pathlib import Path
from fastapi.testclient import TestClient
from contracts.models import G2Input, G2Hello
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app
from pbhelpers import make_card, guide_dict, write_pngs, verify_luma


def rig(tmp_path, monkeypatch):
    monkeypatch.delenv('GB_TTS', raising=False)
    root = tmp_path / 'assets'
    write_pngs(root)
    # Rich phone image deliberately differs from the glasses bitmap.
    from PIL import Image
    Image.new('L', (640, 320), 170).save(root / 'knowledge/guides/gd/where.phone.png')
    guide = guide_dict('gd', 3)
    guide['views'][0]['phone_image'] = 'knowledge/guides/gd/where.phone.png'
    cards = [make_card(3, card_id='alpha', title='Assemble a frame', aliases=['frame'],
                       guides=[guide], guide_steps={0:'gd'}, measured={2:verify_luma()}),
             make_card(2, card_id='beta', title='Fold a box', aliases=['box'])]
    clock = ManualClock()
    rt = Runtime(cards, clock=clock, asset_root=root)
    return rt, TestClient(create_app(rt, tick_interval=None))


def start(rt, client, goal='frame'):
    session = client.post('/session/connect').json()
    result = client.post('/session/goal', json={'session_id':session['id'], 'mode':'build', 'via':'phone_text','text':goal})
    assert result.status_code == 200 and result.json()['status'] == 'supported'
    rt.clock.advance(3000); rt.tick()
    rt.clock.advance(1600); rt.tick()
    return session['id']


def action(rt, client, sid, verb, seq=None):
    return client.post('/session/action', json={'session_id':sid,'action':verb,'seq_seen':rt.hud.current.seq if seq is None else seq})


def test_phone_only_launch_catalog_and_rejoin_preserve_task(tmp_path, monkeypatch):
    rt, c = rig(tmp_path, monkeypatch)
    assert rt.session().id == 'none'
    assert len(c.get('/catalog').json()['tasks']) == 2
    sid = start(rt, c)
    assert rt.playbook.card.card_id == 'alpha'
    assert c.post('/session/connect').json()['id'] == sid
    assert rt.health().g2_clients == 0  # phone is not a fabricated glasses connection
    rt.clock.advance(20000)
    rt.hello(G2Hello(client_id='physical-glasses'))
    assert rt.session().id == sid and rt.playbook.card.card_id == 'alpha'
    start(rt, c, 'box')
    assert rt.playbook.card.card_id == 'beta'


def test_picture_navigation_never_confirms_and_duplicate_confirm_is_rejected(tmp_path, monkeypatch):
    rt, c = rig(tmp_path, monkeypatch); sid = start(rt, c)
    assert action(rt,c,sid,'press').json()['image']['view'] == 'where'
    assert action(rt,c,sid,'confirm').status_code == 409
    assert action(rt,c,sid,'next_view').json()['image']['view'] == 'how'
    assert rt.playbook.confirmed == []
    action(rt,c,sid,'press')
    seq = rt.hud.current.seq
    assert action(rt,c,sid,'confirm').status_code == 200
    assert rt.playbook.confirmed == ['s0']
    rt.clock.advance(2000); rt.tick()
    assert action(rt,c,sid,'confirm',seq).status_code == 409
    rt.handle_input(G2Input(gesture='swipe_down', seq_seen=seq))
    assert rt.playbook.confirmed == ['s0']
    assert action(rt,c,sid,'confirm').status_code == 200
    assert rt.playbook.step.id == 's2'
    assert action(rt,c,sid,'confirm').status_code == 409
    assert rt.playbook.verified == []


def test_grounded_where_how_correct_and_repeat_preserve_current_step(tmp_path, monkeypatch):
    rt,c = rig(tmp_path,monkeypatch); sid=start(rt,c)
    for question, view in [('Where is that?','where'),('How do I do this?','how'),('What should it look like?','correct')]:
        result=c.post('/ask',json={'session_id':sid,'text':question})
        assert result.status_code == 200 and result.json()['answer'] is not None
        assert result.json()['label'] == 'AUTHORED DEMO METADATA'
        assert rt.hud.current.mode == 'visual' and rt.hud.current.image.view == view
        assert rt.playbook.confirmed == []
    result=c.post('/ask',json={'session_id':sid,'text':'repeat'}).json()
    assert 'Full detail for step 0' in result['text']
    assert c.post('/ask',json={'session_id':'old-task','text':'next'}).status_code == 409
    assert c.post('/ask',json={'text':'   '}).status_code == 422
    for question in ['Why is the sky blue?', 'Where is the nearest restaurant?', 'How do I program a spacecraft?']:
        result=c.post('/ask',json={'session_id':sid,'text':question}).json()
        assert result['answer'] is None
        assert rt.playbook.confirmed == []


def test_phone_images_and_metadata_use_reviewed_paths_and_fallback(tmp_path,monkeypatch):
    rt,c=rig(tmp_path,monkeypatch)
    phone=c.get('/guides/gd/where.phone.png'); small=c.get('/guides/gd/where.png')
    assert phone.status_code == small.status_code == 200
    assert phone.content != small.content
    assert c.get('/guides/gd/how.phone.png').content == c.get('/guides/gd/how.png').content
    assert c.get('/guides/gd/manifest.json').json()['guide_id'] == 'gd'
    assert c.get('/guides/unknown/manifest.json').status_code == 404
    assert c.get('/guides/gd/not-a-view.phone.png').status_code == 404


def test_optional_audio_status_and_tts_consent_cooldown(tmp_path,monkeypatch):
    rt,c=rig(tmp_path,monkeypatch)
    monkeypatch.delenv('ELEVENLABS_API_KEY',raising=False)
    assert c.get('/voice/status').json()['stt'] is False
    assert c.post('/voice/speak',json={'text':'Current step','consent':True}).status_code == 503
    monkeypatch.setenv('GB_TTS','1')
    assert c.post('/voice/speak',json={'text':'Current step'}).status_code == 422
    calls=[]
    async def fake(text, *, consent):
        calls.append((text,consent)); return b'fake-test-mp3'
    monkeypatch.setattr('integrations.elevenlabs.client.synthesize',fake)
    result=c.post('/voice/speak',json={'text':'Current step','consent':True})
    assert result.status_code == 200 and result.headers['content-type'] == 'audio/mpeg'
    assert result.headers['cache-control'] == 'no-store'
    assert c.post('/voice/speak',json={'text':'Duplicate','consent':True}).status_code == 429
    assert calls == [('Current step',True)]
