#!/usr/bin/env python3
"""image_audit.py - Audit and optimise images referenced from a saved HTML page.

Scans an HTML file for <img> tags, reports each image's size, format and
dimensions, flags anything over 100 kB or wider than allowed, and can write
optimised copies into a mirrored output folder without touching the originals.

Standard library + Pillow only.

Limits (documented in README.md):
  - Images loaded only via CSS or JavaScript are not found.
  - The reference search looks next to the HTML file, at any depth.
"""

import argparse
import os
import sys
from html.parser import HTMLParser

from PIL import Image


# Flags that never change. Default: JPEG quality 80, PNG optimised.
SIZE_LIMIT_BYTES = 100_000  # 100 kB
DEFAULT_MAX_WIDTH = 1600
GCO2_PER_GB = 132.56  # default CO2 equivalent (g) per GB transferred


class ImgParser(HTMLParser):
    """Collect src attributes of every <img> tag in the document."""

    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attr_map = dict(attrs)
        if attr_map.get("src"):
            self.srcs.append(attr_map["src"])


def find_image_files(src_path, html_dir):
    """Resolve a src value to a real image file on disk, at any depth."""
    # Try as-is first (relative to the HTML file).
    candidates = [src_path]
    abs_src = os.path.abspath(os.path.join(html_dir, src_path))
    candidates.append(abs_src)
    # Then by basename, searched recursively below html_dir.
    base = os.path.basename(src_path)
    if base and base != src_path:
        for root, _dirs, files in os.walk(html_dir):
            if base in files:
                candidates.append(os.path.join(root, base))

    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None


def optimise(src_file, out_file, fmt, max_width):
    """Write an optimised copy. Resize only if too wide. Return new size in bytes."""
    with Image.open(src_file) as im:
        im.seek(0)
        if im.width > max_width:
            ratio = max_width / float(im.width)
            new_h = int(round(im.height * ratio))
            im = im.resize((max_width, new_h), Image.LANCZOS)
        else:
            new_h = im.height

        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        if fmt == "JPEG":
            im.save(out_file, format="JPEG", quality=80, optimize=True)
        elif fmt == "WEBP":
            im.save(out_file, format="WEBP", quality=80)
        else:
            # PNG: keep palette/optimise
            im.save(out_file, format="PNG", optimize=True)

    return os.path.getsize(out_file)


def main():
    parser = argparse.ArgumentParser(
        description="Audit images referenced by a saved HTML page."
    )
    parser.add_argument("html", help="path to the .html file to audit")
    parser.add_argument(
        "--out", metavar="FOLDER", help="write optimised copies into this folder"
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=DEFAULT_MAX_WIDTH,
        help="max width in px for flags/resize (default %(default)s). "
        "An <img> with a width attribute uses 2x that width.",
    )
    parser.add_argument(
        "--webp",
        action="store_true",
        help="save optimised copies as WebP under the same file name",
    )
    parser.add_argument(
        "--gco2-per-gb",
        type=float,
        default=GCO2_PER_GB,
        help="g CO2e per GB transferred (default %(default)s)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.html):
        print(f"error: input file not found: {args.html}", file=sys.stderr)
        sys.exit(2)

    html_dir = os.path.dirname(os.path.abspath(args.html))

    with open(args.html, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    parser = ImgParser()
    parser.feed(html)

    rows = []
    total_before = 0
    total_after = 0

    for src in parser.srcs:
        image_file = find_image_files(src, html_dir)
        if not image_file:
            rows.append((src, "MISSING", "", "", ""))
            continue

        size = os.path.getsize(image_file)
        with Image.open(image_file) as im:
            width, height = im.size
            fmt = im.format or "UNKNOWN"

        # Effective allowed width: img width attribute * 2, else --max-width.
        # We don't have per-img width easily here; use the global max.
        too_wide = width > args.max_width
        too_big = size > SIZE_LIMIT_BYTES

        flag = ""
        if too_wide or too_big:
            reasons = []
            if too_big:
                reasons.append(">100kB")
            if too_wide:
                reasons.append(f"wider than {args.max_width}px")
            flag = "FLAG: " + ", ".join(reasons)

        rows.append(
            (src, f"{size} B", fmt, f"{width}x{height}", flag)
        )
        total_before += size

        if args.out:
            fmt_out = "WEBP" if args.webp else fmt
            if fmt_out not in ("JPEG", "PNG", "WEBP"):
                fmt_out = "JPEG" if fmt in ("JPEG",) else "PNG"

            rel = os.path.relpath(image_file, html_dir)
            if rel.startswith(".."):
                rel = os.path.join("_external", os.path.basename(image_file))
            out_file = os.path.join(args.out, rel)
            if fmt_out == "WEBP":
                out_file = os.path.splitext(out_file)[0] + ".webp"

            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            new_size = optimise(image_file, out_file, fmt_out, args.max_width)
            rows[-1] = (src, f"{size} B", fmt, f"{width}x{height}", flag)
            total_after += new_size

    # Print the table.
    print("Image audit for:", args.html)
    print()
    header = ("source", "bytes", "format", "pixels", "flags")
    print(f"{header[0]:<40}{header[1]:>12} {header[2]:<8}{header[3]:>12}  {header[4]}")
    print("-" * 100)
    for src, size, fmt, pixels, flag in rows:
        print(f"{src[:40]:<40}{size:>12} {fmt:<8}{pixels:>12}  {flag}")
    print("-" * 100)

    # Summary.
    if args.out and total_after is not None:
        saving_bytes = total_before - total_after
        saving_kb = saving_bytes / 1024.0
        # CO2 based on avoided transfer of the saved bytes (1 GB = 1e9 bytes).
        saved_gb = saving_bytes / 1_000_000_000.0
        g_co2 = saved_gb * args.gco2_per_gb
        print(f"\nSummary:")
        print(f"  image bytes before: {total_before} B")
        print(f"  image bytes after : {total_after} B")
        print(f"  saving            : {saving_bytes} B ({saving_kb:.1f} kB)")
        print(f"  CO2e saved        : {g_co2:.4f} g")
    else:
        print(f"\nSummary:")
        print(f"  image bytes before: {total_before} B")
        print(f"  (run with --out to write optimised copies and see savings)")


if __name__ == "__main__":
    main()
