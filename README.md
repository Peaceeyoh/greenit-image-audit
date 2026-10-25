# image_audit.py

Audits the images referenced by a saved HTML page and can write optimised
copies, without ever touching the originals.

## What it does

- Scans an `.html` file for every `<img>` tag (using the standard library
  HTML parser).
- Resolves each `src` to a real image file searched next to the HTML file,
  at any depth.
- For each image prints:
  - the source reference
  - the file size in bytes
  - the image format (JPEG, PNG, WebP, ...)
  - the pixel dimensions
  - a flag when the image is **over 100 kB** or **wider than the allowed
    width** (default 1600 px).
- With `--out`, writes optimised copies into a mirrored output folder and
  prints a summary: bytes before / after, the saving in kB, and the CO2e
  saved (default 132.56 g CO2e per GB).

## Requirements

- Python 3 (standard library)
- [Pillow](https://python-pillow.org) (`pip install Pillow`)

## How to run

```bash
# Just audit an existing page
python image_audit.py path\to\page.html

# Write optimised copies into an output folder (originals are never changed)
python image_audit.py path\to\page.html --out path\to\out

# Also save a WebP version under the same file name
python image_audit.py path\to\page.html --out path\to\out --webp

# Change the allowed maximum width (default 1600 px)
python image_audit.py path\to\page.html --max-width 1920

# Set a different CO2 intensity (g CO2e per GB)
python image_audit.py path\to\page.html --out out --gco2-per-gb 250
```

## Options

| Option            | Default | Meaning                                                                 |
| ----------------- | ------- | ----------------------------------------------------------------------- |
| `--out FOLDER`    | none    | Write optimised copies into this folder. Originals are never modified.  |
| `--max-width PX`  | 1600    | Maximum allowed width. Images wider than this are flagged and (with `--out`) resized. |
| `--webp`          | off     | Save optimised copies as WebP (same base name, `.webp` extension).      |
| `--gco2-per-gb`   | 132.56  | Grams of CO2e emitted per GB of transferred data, used for the saving estimate. |

## What it prints

1. A table: one row per image with `source`, `bytes`, `format`, `pixels`
   and any `flags`.
2. A summary (only when `--out` is used): bytes before and after, the
   saving in kB, and the estimated CO2e saved.

## Exit codes

- `0` – success.
- `2` – the input HTML file does not exist.

## Known limits

- **Images loaded only via CSS or JavaScript are not found.** Only `<img>`
  tags in the static HTML are scanned. Background images, lazy-loading
  scripts and CSS `url()` references are out of scope.
- Only `<img>` `src` attributes are resolved; `srcset`/`data-src` variants
  are not followed.
- An `<img>` with a `width` attribute effectively allows up to `2 × width`
  pixels (per the task spec), but this is applied as the global maximum
  width, not per-tag.
- External (absolute `http(s)` / `//` ) image URLs are not downloaded;
  only local files on disk are audited.
