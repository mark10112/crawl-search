import argparse
import gc
import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path

import psutil
from PIL import Image
from rapidfuzz.distance import Levenshtein
from bs4 import BeautifulSoup

ROOT = Path('/work')


def normalize(text):
    text = BeautifulSoup(text, 'html.parser').get_text(' ')
    text = re.sub(r'(?m)^\s*#{1,6}\s+', '', text)
    text = text.replace('**', '').replace('```', '').replace('\\_', '_')
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text))


class Monitor:
    def __init__(self):
        self.stop = threading.Event()
        self.rss = 0
        self.gpu = 0
        self.handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.idle_gpu = pynvml.nvmlDeviceGetMemoryInfo(self.handle).used
        except Exception:
            self.idle_gpu = None
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.thread.start()

    def sample(self):
        process = psutil.Process()
        while not self.stop.is_set():
            try:
                self.rss = max(self.rss, process.memory_info().rss + sum(p.memory_info().rss for p in process.children(recursive=True)))
                if self.handle:
                    self.gpu = max(self.gpu, self.nvml.nvmlDeviceGetMemoryInfo(self.handle).used)
            except Exception:
                pass
            self.stop.wait(.1)

    def finish(self):
        self.stop.set()
        self.thread.join()
        return {'peak_process_rss_mib': round(self.rss/2**20,2),
                'peak_device_vram_mib': round(self.gpu/2**20,2),
                'idle_device_vram_mib': round(self.idle_gpu/2**20,2) if self.idle_gpu is not None else None}


class Rapid:
    def __init__(self, items):
        from rapidocr import RapidOCR, EngineType, ModelType, OCRVersion
        self.engines = {}
        self.loads = {}
        for language in sorted({i['rapid_language'] for i in items}):
            start = time.perf_counter()
            self.engines[language] = RapidOCR(params={
                'Global.model_root_dir': '/cache/rapid', 'Global.use_cls': False,
                'Global.log_level': 'warning',
                'Det.engine_type': EngineType.ONNXRUNTIME, 'Det.model_type': ModelType.MOBILE,
                'Det.ocr_version': OCRVersion.PPOCRV5,
                'Rec.engine_type': EngineType.ONNXRUNTIME, 'Rec.lang_type': language,
                'Rec.model_type': ModelType.MOBILE, 'Rec.ocr_version': OCRVersion.PPOCRV5,
                'EngineConfig.onnxruntime.intra_op_num_threads': 4,
                'EngineConfig.onnxruntime.inter_op_num_threads': 1,
            })
            self.loads[language] = round((time.perf_counter()-start)*1000,2)
        self.metadata = {'checkpoint': 'RapidOCR 3.10.0 PP-OCRv5 mobile detector + script-specific mobile recognizers',
                         'device': 'CPU ONNX Runtime, 4 threads', 'known_script': True, 'per_language_load_ms': self.loads}

    def run(self, item):
        result = self.engines[item['rapid_language']](str(ROOT/'dataset'/item['image']))
        return '\n'.join(result.txts or []), {'truncated': False}


class VLM:
    def __init__(self, name, revision):
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        self.torch = torch
        torch.set_num_threads(4)
        self.name = name
        model_id = 'PaddlePaddle/PaddleOCR-VL-1.6' if name == 'paddle' else 'lightonai/LightOnOCR-2-1B'
        model_class, processor_class = AutoModelForImageTextToText, AutoProcessor
        if name == 'lighton':
            from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor
            model_class, processor_class = LightOnOcrForConditionalGeneration, LightOnOcrProcessor
        self.processor = processor_class.from_pretrained(model_id, revision=revision)
        self.model, loading_info = model_class.from_pretrained(model_id, revision=revision,
                    torch_dtype=torch.bfloat16, attn_implementation='sdpa', device_map='cuda', output_loading_info=True)
        if loading_info.get('missing_keys') or loading_info.get('unexpected_keys') or loading_info.get('mismatched_keys'):
            raise RuntimeError('Checkpoint did not load cleanly: '+json.dumps(loading_info,default=str)[:2500])
        self.model.eval()
        self.metadata = {'checkpoint': model_id, 'revision': revision, 'device': 'RTX 4060 CUDA BF16',
                         'attention': 'sdpa', 'max_new_tokens': 768, 'max_generation_time_s': 45,
                         'model_class': type(self.model).__name__, 'processor_class':type(self.processor).__name__,
                         'loading_info':json.loads(json.dumps(loading_info,default=lambda value: sorted(value) if isinstance(value,set) else str(value))),
                         'pipeline': 'direct checkpoint OCR; no external page layout detector or oracle crops'}

    def run(self, item):
        image = Image.open(ROOT/'dataset'/item['image']).convert('RGB')
        content = [{'type':'image','image':image}]
        if self.name == 'paddle':
            content.append({'type':'text','text':'OCR:'})
        messages = [{'role':'user','content':content}]
        kwargs = dict(add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt')
        # Use the checkpoint's default image processor. Recent Transformers stores
        # resize bounds in size rather than the older min_pixels attribute.
        inputs = self.processor.apply_chat_template(messages, **kwargs)
        inputs = {k: v.to(device='cuda',dtype=self.torch.bfloat16) if v.is_floating_point() else v.to('cuda') for k,v in inputs.items()}
        with self.torch.inference_mode():
            ids = self.model.generate(**inputs, max_new_tokens=768, max_time=45, do_sample=False)
        generated = ids[0, inputs['input_ids'].shape[1]:]
        text = self.processor.decode(generated, skip_special_tokens=True)
        return text, {'generated_tokens': len(generated), 'truncated': len(generated) >= 768,
                      'gpu_allocated_peak_mib': round(self.torch.cuda.max_memory_allocated()/2**20,2),
                      'gpu_reserved_peak_mib': round(self.torch.cuda.max_memory_reserved()/2**20,2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['rapid','paddle','lighton'], required=True)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--output',default=None)
    args = parser.parse_args()
    output = ROOT/'results'/(args.output or (args.model+'.json'))
    output.parent.mkdir(exist_ok=True)
    items = json.loads((ROOT/'dataset/manifest.json').read_text(encoding='utf-8'))['items']
    if args.limit:
        items = items[:args.limit]
    monitor = Monitor()
    payload = {'model': args.model, 'repeats':args.repeats, 'rows': [], 'notes': [
        'Self-authored controlled image documents, not a representative real-world corpus.',
        'CER removes whitespace and Markdown presentation, preserves case, punctuation and diacritics.',
        'Rapid gets the known script; VLMs do not. CPU vs GPU deployment comparison, not same-kernel throughput.',
        'Paddle direct Transformers OCR is element-level; this does not benchmark its official full page-layout pipeline.',
        'Device VRAM includes Windows/background consumers; torch allocation excludes those.']}
    try:
        start = time.perf_counter()
        revision = None
        if args.model != 'rapid':
            import requests
            model_id = 'PaddlePaddle/PaddleOCR-VL-1.6' if args.model == 'paddle' else 'lightonai/LightOnOCR-2-1B'
            revision_file = ROOT/'model-revisions.json'
            revisions = json.loads(revision_file.read_text()) if revision_file.exists() else {}
            revision = revisions.get(model_id)
            if not revision:
                response = requests.get('https://huggingface.co/api/models/'+model_id,timeout=30)
                response.raise_for_status()
                revision = response.json()['sha']
                revisions[model_id] = revision
                revision_file.write_text(json.dumps(revisions,indent=2))
        engine = Rapid(items) if args.model == 'rapid' else VLM(args.model, revision)
        payload['load_ms_including_downloads'] = round((time.perf_counter()-start)*1000,2)
        payload['metadata'] = engine.metadata
        warm = time.perf_counter()
        engine.run(items[0])
        if args.model != 'rapid':
            engine.torch.cuda.synchronize()
        payload['first_inference_ms_excluded_from_warm'] = round((time.perf_counter()-warm)*1000,2)
        payload['load_and_first_resources'] = monitor.finish()
        monitor = Monitor()
        for repeat in range(args.repeats):
            for item in items:
                try:
                    if args.model != 'rapid':
                        engine.torch.cuda.synchronize()
                        engine.torch.cuda.reset_peak_memory_stats()
                    start = time.perf_counter()
                    text, extra = engine.run(item)
                    if args.model != 'rapid':
                        engine.torch.cuda.synchronize()
                    elapsed = (time.perf_counter()-start)*1000
                    reference = normalize(item['reference'])
                    prediction = normalize(text)
                    edits = Levenshtein.distance(reference,prediction)
                    operations = Levenshtein.editops(reference,prediction)
                    row = {'id': item['id'], 'languages':item['languages'], 'kind':item['kind'], 'repeat':repeat,
                           'ok': bool(prediction), 'elapsed_ms':round(elapsed,2), 'text':text,
                           'reference_chars':len(reference), 'edits':edits, 'cer':edits/len(reference),
                           'deletions':sum(op.tag=='delete' for op in operations),
                           'insertions':sum(op.tag=='insert' for op in operations), **extra}
                except Exception as exc:
                    row = {'id':item['id'],'repeat':repeat,'ok':False,'error':str(exc),'elapsed_ms':round((time.perf_counter()-start)*1000,2)}
                payload['rows'].append(row)
                output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({k:row.get(k) for k in ['id','repeat','cer','elapsed_ms','error']},ensure_ascii=False),flush=True)
    except Exception as exc:
        import traceback
        payload['fatal_error'] = f'{type(exc).__name__}: {exc}'
        payload['traceback'] = traceback.format_exc()
        print(payload['traceback'],flush=True)
    finally:
        payload['resources'] = monitor.finish()
        payload['requirements'] = Path('/opt/benchmark-requirements.txt').read_text()
        output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(output),'resources':payload['resources'],'fatal_error':payload.get('fatal_error')}),flush=True)


if __name__ == '__main__':
    main()
