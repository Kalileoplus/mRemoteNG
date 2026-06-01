"""
Decodifica bitmap RDP: raw 32/24bpp e RLE (interleaved).
Basato su MS-RDPEGDI §2.2.9.1.1 e §3.1.9.
"""
import struct
from typing import Optional


def decode_bitmap(data: bytes, width: int, height: int,
                  bpp: int, compressed: bool) -> Optional[bytes]:
    """
    Decodifica un rettangolo bitmap RDP.
    Ritorna bytes BGRA (4 byte per pixel) pronti per QImage Format_ARGB32.
    """
    if not compressed:
        return _decode_raw(data, width, height, bpp)
    else:
        return _decode_rle(data, width, height, bpp)


def _decode_raw(data: bytes, width: int, height: int, bpp: int) -> bytes:
    if bpp == 32:
        # Dati BGRA, righe dal basso verso l'alto (bottom-up)
        row_bytes = width * 4
        rows = [data[i * row_bytes:(i + 1) * row_bytes]
                for i in range(height)]
        return b"".join(reversed(rows))

    if bpp == 24:
        row_bytes = width * 3
        out = bytearray(width * height * 4)
        for row in range(height):
            src_row = height - 1 - row   # bottom-up
            src_off = src_row * row_bytes
            dst_off = row * width * 4
            for col in range(width):
                b = data[src_off + col * 3]
                g = data[src_off + col * 3 + 1]
                r = data[src_off + col * 3 + 2]
                out[dst_off + col * 4]     = b
                out[dst_off + col * 4 + 1] = g
                out[dst_off + col * 4 + 2] = r
                out[dst_off + col * 4 + 3] = 0xFF
        return bytes(out)

    if bpp == 16:
        out = bytearray(width * height * 4)
        idx = 0
        for row in range(height):
            src_row = height - 1 - row
            src_off = src_row * width * 2
            dst_off = row * width * 4
            for col in range(width):
                pixel = struct.unpack_from("<H", data, src_off + col * 2)[0]
                r = (pixel >> 11) & 0x1F
                g = (pixel >> 5)  & 0x3F
                b = pixel & 0x1F
                out[dst_off + col * 4]     = (b * 255) // 31
                out[dst_off + col * 4 + 1] = (g * 255) // 63
                out[dst_off + col * 4 + 2] = (r * 255) // 31
                out[dst_off + col * 4 + 3] = 0xFF
        return bytes(out)

    return None


def _decode_rle(data: bytes, width: int, height: int, bpp: int) -> bytes:
    """
    RLE bitmap decompressor (MS-RDPEGDI §3.1.9.2).
    Supporta RLE a 8/15/16/24bpp.
    """
    bytes_per_pixel = (bpp + 7) // 8
    output = bytearray(width * height * bytes_per_pixel)
    src = 0
    dst = 0
    x, y = 0, 0

    def put_pixel(pixel_bytes: bytes):
        nonlocal dst, x, y
        pos = y * width + x
        p   = pos * bytes_per_pixel
        if p + bytes_per_pixel <= len(output):
            output[p:p + bytes_per_pixel] = pixel_bytes
        x += 1
        if x >= width:
            x = 0
            y += 1

    while src < len(data):
        header = data[src]; src += 1
        mode = (header & 0xF0) >> 4
        length = header & 0x0F

        if mode == 0x0:   # REGULAR_BG_RUN
            if length == 0:
                length = data[src] + 16; src += 1
            for _ in range(length):
                put_pixel(b"\x00" * bytes_per_pixel)

        elif mode == 0x1:  # REGULAR_FG_RUN
            if length == 0:
                length = data[src] + 16; src += 1
            fg = data[src:src + bytes_per_pixel]; src += bytes_per_pixel
            for _ in range(length):
                put_pixel(fg)

        elif mode == 0x2:  # REGULAR_COLOR_RUN
            if length == 0:
                length = data[src] + 16; src += 1
            color = data[src:src + bytes_per_pixel]; src += bytes_per_pixel
            for _ in range(length):
                put_pixel(color)

        elif mode == 0xA:  # REGULAR_COLOR_IMAGE (uncompressed block)
            if length == 0:
                length = data[src] + 16; src += 1
            for _ in range(length):
                pixel = data[src:src + bytes_per_pixel]; src += bytes_per_pixel
                put_pixel(pixel)

        elif mode == 0x6 or mode == 0x7:  # COLOR_IMAGE (3-byte encoding)
            # MEGA_MEGA variants use 2-byte length
            if length == 0xF:
                length = struct.unpack_from("<H", data, src)[0]; src += 2
            for _ in range(length):
                pixel = data[src:src + bytes_per_pixel]; src += bytes_per_pixel
                put_pixel(pixel)

        else:
            # Unknown — skip byte to avoid infinite loop
            src += 1

    # Convert to 32bpp BGRA
    if bytes_per_pixel == 4:
        return bytes(output)
    return _decode_raw(bytes(output), width, height, bpp)


def parse_update_pdu(data: bytes):
    """
    Parsa un UPDATE PDU e ritorna lista di rettangoli bitmap.
    Ritorna: [(x, y, w, h, bgra_bytes), ...]
    """
    if len(data) < 4:
        return []

    update_type = struct.unpack_from("<H", data, 0)[0]
    if update_type != 0x0001:   # UPDATETYPE_BITMAP
        return []

    num_rects = struct.unpack_from("<H", data, 2)[0]
    offset    = 4
    results   = []

    for _ in range(num_rects):
        if offset + 26 > len(data):
            break
        (x, y, x_right, y_bottom, width, height,
         bpp, flags, compress_type, compress_flags, line_size, data_size
         ) = struct.unpack_from("<HHHHHHHHHHHH", data, offset)
        offset += 26

        rect_data = data[offset:offset + data_size]
        offset   += data_size

        w = x_right  - x + 1
        h = y_bottom - y + 1

        compressed = bool(flags & 0x0400)   # BITMAP_COMPRESSION flag
        if flags & 0x0010:   # NO_BITMAP_COMPRESSION_HDR
            bitmap_bytes = rect_data
        else:
            # Salta compression header (8 bytes)
            bitmap_bytes = rect_data[8:] if compressed else rect_data

        bgra = decode_bitmap(bitmap_bytes, w, h, bpp, compressed)
        if bgra:
            results.append((x, y, w, h, bgra))

    return results
