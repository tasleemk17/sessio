"""Checks on an uploaded file's real content. An extension is only a name anyone can type, so the first bytes
must match the kind of file the name claims, and anything that looks like a program is turned away."""

_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # old Word, Excel, PowerPoint
_ZIP = (b"PK\x03\x04",)  # docx, xlsx, pptx and zip are all zip containers

MAGIC = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".doc": (_OLE,),
    ".xls": (_OLE,),
    ".ppt": (_OLE,),
    ".docx": _ZIP,
    ".xlsx": _ZIP,
    ".pptx": _ZIP,
    ".zip": _ZIP,
}
ALLOWED = set(MAGIC) | {".txt", ".md"}

# Windows program, Linux program, script with a shebang, macOS programs
PROGRAM_SIGNATURES = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe")


def content_matches(extension: str, data: bytes) -> bool:
    if data.startswith(PROGRAM_SIGNATURES):
        return False
    if extension in (".txt", ".md"):
        return b"\x00" not in data[:4096]  # real text has no NUL bytes
    return data.startswith(MAGIC[extension])
