"""Compile project PO catalogs without an external GNU msgfmt installation.

Run: python scripts/compile_translations.py
Standard Django compilemessages can also compile these catalogs when gettext is installed.
"""
import ast
from pathlib import Path
import struct


def read_catalog(path):
    messages = {}
    entry = {}
    field = None
    fuzzy = False

    def finish():
        if "msgid" not in entry or fuzzy:
            return
        key = entry["msgid"]
        if "msgctxt" in entry:
            key = entry["msgctxt"] + "\x04" + key
        if "msgid_plural" in entry:
            key += "\x00" + entry["msgid_plural"]
            plural_keys = sorted(name for name in entry if name.startswith("msgstr["))
            value = "\x00".join(entry[name] for name in plural_keys)
        else:
            value = entry.get("msgstr", "")
        if not value:
            return
        if key in messages:
            raise ValueError(f"Duplicate translation in {path}: {key!r}")
        messages[key] = value

    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line:
            finish()
            entry, field, fuzzy = {}, None, False
        elif line.startswith("#"):
            if line.startswith("#,") and "fuzzy" in line:
                fuzzy = True
        elif line.startswith('"'):
            if field is None:
                raise ValueError(f"Unexpected continuation at {path}:{number}")
            entry[field] += ast.literal_eval(line)
        else:
            name, literal = line.split(maxsplit=1)
            if name == "msgid" and "msgid" in entry:
                finish()
                entry = {}
            if name not in ("msgid", "msgid_plural", "msgctxt", "msgstr") and not name.startswith("msgstr["):
                raise ValueError(f"Unknown PO field at {path}:{number}: {name}")
            field = name
            entry[field] = ast.literal_eval(literal)
    finish()
    return messages


def compile_catalog(path):
    messages = read_catalog(path)
    keys = sorted(messages)
    count = len(keys)
    original_blob = bytearray()
    translated_blob = bytearray()
    originals = []
    translations = []
    for key in keys:
        original = key.encode("utf-8")
        translated = messages[key].encode("utf-8")
        originals.append((len(original), len(original_blob)))
        translations.append((len(translated), len(translated_blob)))
        original_blob.extend(original + b"\0")
        translated_blob.extend(translated + b"\0")
    data_offset = 28 + count * 16
    result = bytearray(struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + count * 8, 0, 0))
    for length, offset in originals:
        result.extend(struct.pack("<2I", length, data_offset + offset))
    for length, offset in translations:
        result.extend(struct.pack("<2I", length, data_offset + len(original_blob) + offset))
    result.extend(original_blob)
    result.extend(translated_blob)
    destination = path.with_suffix(".mo")
    destination.write_bytes(result)
    print(f"Compiled {destination}: {count} messages")


if __name__ == "__main__":
    for catalog in sorted((Path(__file__).resolve().parent.parent / "locale").rglob("*.po")):
        compile_catalog(catalog)
