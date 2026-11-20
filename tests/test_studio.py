import io
import json
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import app as studio


class StudioTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.upload = self.root / 'uploads'
        self.export = self.root / 'exports'
        self.upload.mkdir()
        self.export.mkdir()
        paths = patch.multiple(studio, DB=self.root/'projects.json', UPLOAD=self.upload, EXPORT=self.export)
        paths.start()
        self.addCleanup(paths.stop)
        self.client = studio.app.test_client()

    def test_corrupt_library_preserved(self):
        studio.DB.write_text('broken')
        self.assertEqual(self.client.get('/api/projects').status_code, 500)
        self.assertEqual(studio.DB.read_text(), 'broken')

    def test_parallel_registrations(self):
        def register(i):
            with studio.app.app_context():
                return studio.register_project(str(i), self.upload/f'{i}.mp4', 'test')[1]
        with patch.object(studio, 'probe', return_value=5), ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(register, range(24))), [201]*24)
        self.assertEqual(len(studio.load()), 24)

    def test_local_route_uses_no_credentials_and_caches(self):
        studio.save([dict(id='abc', source='a.mp4', duration=2, clips=[])])
        (self.upload/'abc.local.json').write_text('legacy auto transcript')
        result = dict(captions=[], moments=[])
        with patch.object(studio, 'credential', side_effect=AssertionError), patch.object(
                studio, 'analyze_local', return_value=result) as analyze:
            for _ in range(2):
                response = self.client.post('/api/analysis/abc', json={'engine':'local'})
                self.assertEqual(response.json, result)
            analyze.assert_called_once()
            self.assertEqual(analyze.call_args.args[:3],(self.upload/'a.mp4', 2, 'sk'))
        self.assertTrue((self.upload/'abc.local.sk.v2.json').exists())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_trimmed_video_and_styled_captions(self):
        # Speech-like tone, two seconds of silence, then a second tone.
        source = self.root/'source.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=160x90:r=10:d=4',
                        '-f', 'lavfi', '-i', 'sine=d=4',
                        '-af', "volume=0:enable='between(t,1,3)'", '-c:v', 'libx264', '-c:a', 'aac',
                        str(source)], check=True)
        with source.open('rb') as video:
            project = self.client.post('/api/upload', data={'file': (video, 'skuska.mp4')}).json
        pid = project['id']
        (self.upload/f'{pid}.local.sk.v2.json').write_text(json.dumps(
            {'captions':[dict(start=3,end=4,text='Ľahký strih')]}))
        r = self.client.post('/api/clip/'+pid, json=dict(start=0,end=4,silence='0.8',
                             zoom='punch',captions=True,color='yellow',position='top',ratio='16:9'))
        self.assertEqual(r.status_code, 201, r.json)
        out = self.export/r.json['file']
        streams = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams',
                                                     '-of','json',str(out)]))['streams']
        self.assertEqual([s['codec_type'] for s in streams], ['video','audio'])
        for stream in streams:
            self.assertAlmostEqual(float(stream['duration']), 2.2, delta=.18)
        def yellow_pixels(t):
            png = subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(out),
                '-frames:v','1','-vf','scale=320:180','-f','image2pipe','-c:v','png','pipe:1'])
            frame = Image.open(io.BytesIO(png)).convert('RGB')
            return sum(r>130 and g>110 and b<100 for r,g,b in frame.crop((0,0,320,90)).get_flattened_data())
        self.assertEqual(yellow_pixels(.4), 0)
        self.assertGreater(yellow_pixels(1.7), 5)

    def test_invalid_times_and_effects(self):
        studio.save([dict(id='abc', duration=10, clips=[], source='a.mp4')])
        for options in [dict(start='nan',end=4), dict(start=0,end=4,zoom='other'),
                        dict(start=0,end=4,ratio=[]), ['unexpected']]:
            self.assertIn(self.client.post('/api/clip/abc',json=options).status_code, (400,422))
        self.assertEqual(studio.load()[0]['clips'], [])
