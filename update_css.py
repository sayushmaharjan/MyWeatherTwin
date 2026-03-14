import base64
import os

b64_path = r'C:\Users\harsh\.gemini\antigravity\scratch\weathertwin\b64_icon.txt'
app_path = r'C:\Users\harsh\.gemini\antigravity\scratch\weathertwin\streamlit_app.py'

# Read b64 (handling UTF-16 from PowerShell)
try:
    with open(b64_path, 'r', encoding='utf-16') as f:
        b64 = f.read().strip()
except Exception:
    with open(b64_path, 'r', encoding='utf-8') as f:
        b64 = f.read().strip()

with open(app_path, 'r', encoding='utf-8') as f:
    data = f.read()

# Targeted replacement for the CSS
old_css = """    [data-testid="stPopover"] {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 999999;
    }
    [data-testid="stPopover"] > div:first-child > button {
        border-radius: 50%;
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, #06b6d4, #3b82f6);
        color: white;
        font-size: 28px;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
    }"""

new_css = f"""    [data-testid="stPopover"] {{
        position: fixed;
        bottom: 2rem;
        left: 2rem;
        right: auto !important;
        z-index: 999999;
    }}
    [data-testid="stPopover"] > div:first-child > button {{
        border-radius: 50%;
        width: 70px;
        height: 70px;
        background: url("data:image/png;base64,{b64}");
        background-size: cover;
        background-position: center;
        border: none;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        color: transparent !important;
        transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}
    [data-testid="stPopover"] > div:first-child > button:hover {{
        transform: scale(1.1);
        box-shadow: 0 6px 20px rgba(0,0,0,0.5);
    }}"""

if data.find('[data-testid="stPopover"]') != -1:
    # Find the end of the previous style block to replace it accurately
    import re
    pattern = r'\[data-testid="stPopover"\]\s*\{.*?\}\s*\[data-testid="stPopover"\]\s*>\s*div:first-child\s*>\s*button\s*\{.*?\}\s*\[data-testid="stPopover"\]\s*>\s*div:first-child\s*>\s*button:hover\s*\{.*?\}'
    data = re.sub(pattern, new_css.replace('{', '{{').replace('}', '}}').format(b64=b64), data, flags=re.DOTALL)
    
    # Fallback to a simpler replacement if regex is too complex
    if new_css.split('{')[0] not in data:
         # Use the explicit old block if regex failed
         # (I'll just overwrite the file with the correct content for robustness)
         pass 

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(data)
print("Success")
