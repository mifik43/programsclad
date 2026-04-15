from PIL import Image, ImageDraw
import os

sizes = [72, 96, 128, 144, 152, 192, 384, 512]
color = (13, 110, 253)  # Bootstrap primary blue
os.makedirs('static/icons', exist_ok=True)

for size in sizes:
    img = Image.new('RGB', (size, size), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(size//4, size//4), (3*size//4, 3*size//4)], fill=(255,255,255))
    img.save(f'static/icons/icon-{size}.png')
print("Icons generated")