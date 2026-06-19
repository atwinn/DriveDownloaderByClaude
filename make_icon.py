"""Render a simple Google Drive style tricolor-triangle icon to icon_1024.png."""
from PIL import Image, ImageDraw

S = 1024
SS = 4          # supersample factor for smooth edges
W = S * SS
img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

def P(x, y):
    return (x * SS, y * SS)

# Triangle vertices (on a 1024 grid)
A  = (512, 196)      # apex
L  = (168, 792)      # bottom-left
R  = (856, 792)      # bottom-right
# Edge midpoints
M_AL = ((A[0]+L[0])/2, (A[1]+L[1])/2)
M_AR = ((A[0]+R[0])/2, (A[1]+R[1])/2)
M_LR = ((L[0]+R[0])/2, (L[1]+R[1])/2)
# Centroid
C = ((A[0]+L[0]+R[0])/3, (A[1]+L[1]+R[1])/3)

YELLOW = (255, 207, 72, 255)
BLUE   = (38, 132, 252, 255)
GREEN  = (15, 161, 96, 255)

# top rhombus (yellow), lower-left (blue), lower-right (green)
d.polygon([P(*A), P(*M_AR), P(*C), P(*M_AL)], fill=YELLOW)
d.polygon([P(*M_AL), P(*C), P(*M_LR), P(*L)], fill=BLUE)
d.polygon([P(*M_AR), P(*R), P(*M_LR), P(*C)], fill=GREEN)

img = img.resize((S, S), Image.LANCZOS)
img.save("icon_1024.png")
# Windows .ico (multi-resolution, max 256)
img.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                            (128, 128), (256, 256)])
print("wrote icon_1024.png and icon.ico")
