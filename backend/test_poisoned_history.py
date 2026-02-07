
import asyncio
import os
import base64
from google import genai
from config.settings import get_config
from app.core.prompts import get_system_prompt

async def test_poisoned_history():
    conf = get_config()
    api_key = conf.get("GOOGLE_API_KEY")
    if not api_key:
        print("No API Key")
        return

    # Load image
    img_path = "/home/anderss/Downloads/d23395ad-d853-40d3-a5ba-9c8b1c35053c_preview.jpeg"
    if not os.path.exists(img_path):
        print("Image not found")
        # Try to find any jpeg
        import glob
        jpgs = glob.glob("/home/anderss/Downloads/*.jpeg")
        if jpgs: img_path = jpgs[0]
        else:
             print("No images found to test with.")
             return

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    model_id = "gemini-2.0-flash"
    client = genai.Client(api_key=api_key)
    
    # Poisoned history
    history = [
        {"role": "user", "parts": [{"text": "Vad är det på bilden?"}]},
        {"role": "model", "parts": [{"text": "Jag kan tyvärr inte se eller beskriva bilder, Anders. Jag är en textbaserad assistent."}]},
        {"role": "user", "parts": [{"text": "Försök igen."}]},
        {"role": "model", "parts": [{"text": "Jag kan tyvärr inte se eller beskriva bilder, Anders. Jag är en textbaserad assistent."}]},
    ]
    
    # New message with image
    new_msg = {
        "role": "user", 
        "parts": [
            {"text": "Beskriv vad du ser på bilden nu."},
            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
        ]
    }
    
    contents = history + [new_msg]
    
    sys_prompt = get_system_prompt()
    # Add strong override
    sys_prompt += "\n\nIGNORE PREVIOUS REFUSALS. YOU CAN SEE IMAGES."

    print("Testing with poisoned history...")
    try:
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=contents,
            config={"system_instruction": sys_prompt}
        )
        print("Response:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_poisoned_history())
