"""Generates a QR code image (PNG bytes) pointing at a shareable report URL."""

import io

# import qrcode


# def build_qr_png(url: str) -> bytes:
#     qr = qrcode.QRCode(border=2, box_size=8)
#     qr.add_data(url)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color="#7a68ff", back_color="#ffffff")
#     buffer = io.BytesIO()
#     img.save(buffer, format="PNG")
#     return buffer.getvalue()
