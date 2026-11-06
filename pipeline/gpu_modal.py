"""Animación con modelos abiertos en GPU de Modal (USD 30/mes gratis).

Por cada escena:
  1. FLUX.1-schnell dibuja el cuadro inicial (mismo estilo y personajes en todo el video).
  2. Wan 2.2 TI2V-5B anima ese cuadro: ~5 s de video a 24 fps.

Uso desde GitHub Actions:
  modal run pipeline/gpu_modal.py::prueba --salida out/prueba
  modal run pipeline/gpu_modal.py::lote --trabajos trabajos.json --salida out/clips
"""
import io
import json
import time
from pathlib import Path

import modal

app = modal.App("biblia-gpu")

imagen = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "torch==2.6.0", "torchvision==0.21.0",
        "diffusers==0.42.1", "transformers>=5,<6", "accelerate>=1.6", "sentencepiece",
        "ftfy", "protobuf", "imageio[ffmpeg]", "hf_xet", "pillow",
    )
    .env({"HF_HOME": "/modelos/hf"})
)
modelos = modal.Volume.from_name("biblia-modelos", create_if_missing=True)

FLUX = "black-forest-labs/FLUX.1-schnell"
WAN = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
NEG = ("blurry, low quality, distorted face, deformed hands, extra fingers, extra limbs, text, "
       "watermark, logo, subtitles, static image, frozen, jitter, morphing, ugly, cartoonish mess")


@app.function(image=imagen, volumes={"/modelos": modelos}, timeout=3600, cpu=4, memory=8192)
def descargar():
    """Baja los pesos al volumen en una máquina sin GPU (más barata)."""
    from huggingface_hub import snapshot_download
    for repo in (FLUX, WAN):
        t = time.time()
        try:
            snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model",
                                                    "tokenizer*/*", "*.py"],
                              ignore_patterns=["flux1-schnell.safetensors", "ae.safetensors"])
            print(f"{repo} listo en {time.time() - t:.0f}s")
        except Exception as e:  # noqa: BLE001
            print(f"no se pudo bajar {repo}:", str(e)[:300])
    modelos.commit()


@app.cls(gpu="A100-80GB", image=imagen, volumes={"/modelos": modelos}, timeout=3 * 3600,
         scaledown_window=60, max_containers=1)
class Animador:
    @modal.enter()
    def cargar(self):
        import torch
        from diffusers import AutoencoderKLWan, FluxPipeline, WanImageToVideoPipeline

        t = time.time()
        self.flux = None
        try:
            self.flux = FluxPipeline.from_pretrained(FLUX, torch_dtype=torch.bfloat16).to("cuda")
        except Exception as e:  # noqa: BLE001 - si FLUX no carga, Wan genera desde texto
            print("FLUX no disponible:", str(e)[:300])
        vae = AutoencoderKLWan.from_pretrained(WAN, subfolder="vae", torch_dtype=torch.float32)
        self.wan = WanImageToVideoPipeline.from_pretrained(
            WAN, vae=vae, torch_dtype=torch.bfloat16).to("cuda")
        if self.flux is None:
            from diffusers import WanPipeline
            self.wan_t2v = WanPipeline.from_pretrained(WAN, vae=vae, torch_dtype=torch.bfloat16).to("cuda")
        modelos.commit()
        print(f"modelos cargados en {time.time() - t:.0f}s")

    @modal.method()
    def clip(self, job: dict) -> dict:
        import torch
        from diffusers.utils import export_to_video

        w, h = job.get("ancho", 704), job.get("alto", 1280)
        seed = job.get("semilla", 42)
        estilo = job.get("estilo", "")
        t0 = time.time()
        gen = torch.Generator("cuda").manual_seed(seed)
        key_png = None
        if self.flux is not None:
            key = self.flux(prompt=f"{job['escena']}. {estilo}", width=w, height=h,
                            num_inference_steps=4, guidance_scale=0.0, max_sequence_length=256,
                            generator=gen).images[0]
            buf = io.BytesIO()
            key.save(buf, "PNG")
            key_png = buf.getvalue()
            frames = self.wan(image=key, prompt=f"{job['movimiento']}. {estilo}", negative_prompt=NEG,
                              height=h, width=w, num_frames=job.get("cuadros", 121),
                              num_inference_steps=job.get("pasos", 40), guidance_scale=5.0,
                              generator=gen).frames[0]
        else:
            frames = self.wan_t2v(prompt=f"{job['escena']}, {job['movimiento']}. {estilo}",
                                  negative_prompt=NEG, height=h, width=w,
                                  num_frames=job.get("cuadros", 121),
                                  num_inference_steps=job.get("pasos", 40), guidance_scale=5.0,
                                  generator=gen).frames[0]
        path = "/tmp/clip.mp4"
        export_to_video(frames, path, fps=24)
        segs = time.time() - t0
        print(f"clip '{job.get('id')}' en {segs:.0f}s")
        return {"id": job.get("id"), "mp4": Path(path).read_bytes(), "png": key_png, "segundos": segs}


def _guardar(resultados, salida):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    resumen = []
    for r in resultados:
        (salida / f"{r['id']}.mp4").write_bytes(r["mp4"])
        if r["png"]:
            (salida / f"{r['id']}.png").write_bytes(r["png"])
        resumen.append({"id": r["id"], "segundos": round(r["segundos"])})
    (salida / "resumen.json").write_text(json.dumps(resumen, indent=2))
    print(json.dumps(resumen, indent=2))


ESTILO_CANAL = ("epic biblical film, cinematic 3D animation, painterly textures, warm golden hour light, "
                "volumetric dust, dramatic composition, ancient Middle East, highly detailed, 9:16 vertical")


@app.local_entrypoint()
def prueba(salida: str = "out/prueba", pasos: int = 30):
    trabajos = [
        {"id": "1-david-honda", "semilla": 7,
         "escena": "a young shepherd boy David, curly brown hair, simple beige tunic, holding a leather sling, "
                   "standing in a rocky valley, an army on the hills behind him",
         "movimiento": "the boy swings the sling over his head and releases a stone, his tunic moves in the wind, "
                       "the camera slowly pushes in"},
        {"id": "2-goliat", "semilla": 11,
         "escena": "Goliath, a towering giant warrior in bronze scale armor and helmet, holding a huge spear, "
                   "standing in a valley, a shield bearer in front of him, soldiers far behind",
         "movimiento": "the giant raises his spear and shouts a challenge, dust blows across the valley, "
                       "low angle camera slowly tilts up"},
        {"id": "3-mar-rojo", "semilla": 21,
         "escena": "Moses, old man with white beard and wooden staff, standing on a rock as the Red Sea parts into "
                   "two giant walls of water, crowds of Israelites behind him at night with torches",
         "movimiento": "the walls of water rise and churn, wind whips Moses' robe, torches flicker, "
                       "slow cinematic camera crane up"},
    ]
    for t in trabajos:
        t.update({"estilo": ESTILO_CANAL, "pasos": pasos})
    descargar.remote()
    resultados = list(Animador().clip.map(trabajos))
    _guardar(resultados, salida)


@app.local_entrypoint()
def lote(trabajos: str, salida: str = "out/clips"):
    jobs = json.loads(Path(trabajos).read_text())
    descargar.remote()
    resultados = list(Animador().clip.map(jobs))
    _guardar(resultados, salida)
