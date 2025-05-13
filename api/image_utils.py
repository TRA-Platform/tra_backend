import base64
import io
import tempfile
import os
import re
import asyncio
from PIL import Image, ImageDraw, ImageFont
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

def read_tailwind_script():
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'tailwind', 'script.js')
    
    try:
        with open(script_path, 'r') as f:
            logger.info(f"Successfully read local Tailwind script from {script_path}")
            return f.read()
    except Exception as e:
        logger.error(f"Error reading Tailwind script from {script_path}: {str(e)}")
        return """
        /* Minimal Tailwind-like CSS fallback */
        .container { width: 100%; }
        .flex { display: flex; }
        .flex-col { flex-direction: column; }
        .items-center { align-items: center; }
        .justify-center { justify-content: center; }
        .w-full { width: 100%; }
        .p-4 { padding: 1rem; }
        """

tailwind_script = read_tailwind_script()

def generate_placeholder_image(width=100, height=100, text="Placeholder"):
    img = Image.new('RGB', (width, height), color=(200, 200, 200))
    d = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("Arial", 14)
    except IOError:
        font = ImageFont.load_default()
    
    text_width, text_height = d.textsize(text, font=font) if hasattr(d, 'textsize') else d.textbbox((0, 0), text, font=font)[2:4]
    position = ((width - text_width) // 2, (height - text_height) // 2)
    
    d.text(position, text, fill=(80, 80, 80), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

def process_html_for_rendering(html_content):
    logger.info("Processing HTML content with local Tailwind script inlined")
    
    tailwind_content = tailwind_script
    
    if "<html" not in html_content.lower():
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Mockup</title>
            <script>
            {tailwind_content}
            </script>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
    else:
        html_content = re.sub(
            r'<link[^>]*tailwindcss[^>]*>|<script[^>]*tailwindcss[^>]*>.*?</script>|<script[^>]*src=["\']([^"\']*tailwind[^"\']*)["\'][^>]*></script>',
            '',
            html_content,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'<script>{tailwind_content}</script></head>')
        else:
            html_content = re.sub(
                r'<body[^>]*>',
                f'<head><script>{tailwind_content}</script></head><body>',
                html_content,
                flags=re.IGNORECASE
            )
    
    placeholder_pattern = re.compile(r'src=["\']https?://via\.placeholder\.com/(\d+)x(\d+)(?:\?text=([^"\'&]+))?["\']')
    
    def replace_placeholder(match):
        width = int(match.group(1))
        height = int(match.group(2))
        text = match.group(3) or "Placeholder"
        text = text.replace('+', ' ')
        
        img_data = generate_placeholder_image(width, height, text)
        data_url = f'src="data:image/png;base64,{base64.b64encode(img_data).decode("utf-8")}"'
        return data_url
    
    html_content = placeholder_pattern.sub(replace_placeholder, html_content)
    
    social_icon_replacements = {
        r'src=["\']https?://[^"\']*google[^"\']*\.svg["\']': 'src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIgZmlsbD0iIzQyODVmNCIvPjx0ZXh0IHg9IjEyIiB5PSIxNyIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSI+RzwvdGV4dD48L3N2Zz4="',
        r'src=["\']https?://[^"\']*vk[^"\']*\.svg["\']': 'src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIgZmlsbD0iIzQ2NzdiZiIvPjx0ZXh0IHg9IjEyIiB5PSIxNyIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSI+Vks8L3RleHQ+PC9zdmc+"',
    }
    
    for pattern, replacement in social_icon_replacements.items():
        html_content = re.sub(pattern, replacement, html_content, flags=re.IGNORECASE)
    
    return html_content

async def _render_html_to_png_async(html_content, width=1200, height=800):
    logger.info("Rendering HTML to PNG using Playwright")
    
    processed_html = process_html_for_rendering(html_content)
    
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
        temp_html.write(processed_html.encode('utf-8'))
        temp_html_path = temp_html.name
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport={'width': width, 'height': height},
                device_scale_factor=2  # For better quality
            )
            page = await context.new_page()
            
            # Load the HTML content
            await page.set_content(processed_html)
            
            # Wait for any dynamic content to load
            await page.wait_for_load_state('networkidle')
            
            # Take screenshot
            screenshot = await page.screenshot(
                type='png',
                full_page=True,
                scale='device'
            )
            
            await browser.close()
            return screenshot
            
    except Exception as e:
        logger.error(f"Error rendering HTML to PNG with Playwright: {str(e)}")
        error_img = generate_placeholder_image(width, 400, "Rendering Error")
        return error_img
    
    finally:
        if os.path.exists(temp_html_path):
            os.unlink(temp_html_path)

def render_html_to_png(html_content, width=1200, height=800):
    return asyncio.run(_render_html_to_png_async(html_content, width, height))

def png_to_base64(png_data):
    return base64.b64encode(png_data).decode('utf-8')

def html_to_base64_png(html_content, width=1200, height=800):
    png_data = render_html_to_png(html_content, width, height)
    return png_to_base64(png_data)

def resize_base64_image(base64_string, max_width=800):
    img_data = base64.b64decode(base64_string)
    img = Image.open(io.BytesIO(img_data))
    
    width, height = img.size
    if width > max_width:
        ratio = max_width / width
        new_width = max_width
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8') 