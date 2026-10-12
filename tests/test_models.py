import unittest
from unittest.mock import patch
from borg.models import infer


class ModelAdapterTests(unittest.TestCase):
    def test_mock_is_explicitly_not_ai(self):
        self.assertIn('not an AI answer',infer('hello',backend='mock'))

    def test_unknown_backend_rejected(self):
        with self.assertRaises(ValueError): infer('hello',backend='arbitrary-code')

    def test_remote_plaintext_blocked(self):
        with self.assertRaises(ValueError): infer('x',backend='openai-compatible',model='test',base_url='http://remote.example/v1')

    def test_openai_shape(self):
        class Resp:
            def __enter__(self):return self
            def __exit__(self,*a):return False
        with patch('borg.models.urlopen') as fake:
            fake.return_value=Resp()
            with patch('borg.models.json.load',return_value={'choices':[{'message':{'content':'done'}}]}):
                self.assertEqual(infer('question',backend='openai-compatible',model='qwen',base_url='https://inference.example/v1'),'done')
            self.assertTrue(fake.called)

    def test_ollama_shape(self):
        class Resp:
            def __enter__(self):return self
            def __exit__(self,*a):return False
        with patch('borg.models.urlopen') as fake:
            fake.return_value=Resp()
            with patch('borg.models.json.load',return_value={'message':{'content':'ollama answer'}}):
                self.assertEqual(infer('question',backend='ollama',model='qwen3:1.7b'),'ollama answer')

if __name__=='__main__': unittest.main()

class DirectLocalModelTests(unittest.TestCase):
    def test_gguf_requires_explicit_file(self):
        with self.assertRaises(ValueError):
            infer('question',backend='gguf',model='does-not-exist.gguf')

    def test_local_gguf_inference_protocol(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            model_path=Path(tmp)/'small.gguf'
            model_path.write_bytes(b'Test placeholder - not real weights')
            fake_result={'choices':[{'message':{'content':'direct local result'}}]}
            class FakeLlama:
                def create_chat_completion(self,**kwargs):
                    self.prompt=kwargs['messages'][0]['content']
                    return fake_result
            fake=FakeLlama()
            with patch('borg.models._local_gguf',return_value=fake):
                self.assertEqual(infer('One question',backend='gguf',model=str(model_path)),
                                 'direct local result')
                self.assertEqual(fake.prompt,'One question')
