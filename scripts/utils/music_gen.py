import os
import shutil


def generate_ai_music(prompt, out_path, duration=15):
    """
    Generate original instrumental music matching the video's mood using Meta's
    MusicGen model, hosted free on Hugging Face Spaces. Raises on any failure so
    the caller can fall back to royalty-free tracks instead.
    """
    from gradio_client import Client

    client = Client("facebook/MusicGen")

    # Log the actual API signature so future runs are easy to debug if this ever changes
    try:
        print(f"[musicgen] API signature: {client.view_api(print_info=False)}")
    except Exception:
        pass

    result = client.predict(
        prompt,       # text description of the desired music
        None,         # no melody conditioning audio
        duration,     # duration in seconds
        api_name="/predict",
    )

    # The space returns a path (or tuple containing one) to the generated audio/video file
    generated_path = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(generated_path, dict):
        generated_path = generated_path.get("name") or generated_path.get("path")

    shutil.copy(generated_path, out_path)
    return out_path
