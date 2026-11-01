"""Unicode Text: what the companion DLL vf2unicode_b200.dll finds in the B200 Virtual Families 2 executable.

Single source of truth for every function the DLL relies on. Each pin is a WHOLE stock function, taken from the
B200 desktop object file the executable is linked from (work/desktop_obj_files); its relocated fields and its
call / jmp rel32 displacements are wildcards. runtime/tools/gen_b200_unicode_sites.py proves that every pin is in
the executable exactly once (core variant and every other executable it is given), derives each call target and
writes the DLL's header. The DLL holds no game address.

What the DLL replaces (entry jumps, vtable slots and one import slot; the game's own bytes are otherwise untouched):

* ldwGameWindowImpl::DrawString, ldwGameWindowImpl::DrawChars, ldwFont::GetWidth(const char *, float),
  ldwFont::GetNextJustifiedLine: their first 5 bytes jump to the DLL's versions, which are the stock functions
  with a CHARACTER in place of a byte (src/vf2_game_text.py is the same code in Python, proved equal to the stock
  functions for every single-byte text by running the game's code under emulation). GetHeight, GetJustifiedHeight
  and GetJustifiedParagraph are stock and reach the new GetNextJustifiedLine through their own calls.
* ldwGameWindow::DrawStringJustified (dialog and store text, which does its own word wrapping): its first 9 bytes
  jump to a wrapper that hands the stock function a copy of the text in which each different character beyond
  ASCII is one byte 80h..FFh, and the ldwFontImpl vtable's GetCharSourceRect (slot 1) answers those bytes with the
  character's glyph for the length of that call. The stock function then wraps, measures and draws characters.
* ldwTextControlImpl's HandleKey (its vtable slot 2): a typed character beyond ASCII (delivered by the event hook
  below) is added to the text box's text in the stored form (UTF-8 or single bytes, src/vf2_game_text.py encode)
  only if the whole text still fits the box's own byte limit; Backspace removes a whole character. Everything else
  goes to the stock HandleKey.
* ldwTextControl::GetText(buffer, size): its first 5 bytes jump to the DLL's version, which copies the text box's
  text cut to size - 1 bytes at a CHARACTER (src/vf2_game_text.fit) and fills the rest with zeros, as strncpy did;
  the stock copy cut at a byte, which could split a UTF-8 character. Every name the player types reaches its save
  field through GetText (nickname and player names 20, villager names 19, the Family Tree note 80).
* the executable's import slot of SDL_PollEvent: a typed text (SDL_TEXTINPUT) of anything other than one ASCII
  byte (accented keys, dead keys, Alt codes, the IME) is given to the game one character at a time as
  HandleKey(5, code point | KEY_MARK, 0) - the stock code drops it - and the event is then hidden from the stock
  code. A plain ASCII key is untouched.

The glyphs: each game font's sheet surface is replaced by a taller copy (the stock pixels unchanged at the top)
with the patcher-made glyphs ("Unicode Text\\<font>.png") below, and characters neither has are drawn into the
free rows at first use (GDI, in the font's fitted style, as src/vf2_game_text.runtime_glyph). Every tinted copy
the font has cached gets the new glyph too, so the stock tinting and blitting draw it.
"""
from __future__ import annotations

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2unicode_b200.dll"
INI_NAME = "vf2unicode.ini"
LOG_NAME = "vf2unicode.log"
GLYPH_FOLDER = "Unicode Text"
STARTUP = "B200Unicode_Startup"
STATUS_MAGIC = 0x54584E55          # 'UNXT'
KEY_TYPE_CHARACTER = 5
KEY_MARK = 0x40000000               # HandleKey(5, cp | KEY_MARK, 0): a character the DLL delivers (code point cp)
SDL_TEXTINPUT = 0x303
SDL_HIDDEN_EVENT = 0x8000           # SDL_USEREVENT: the stock CheckForEvents ignores it
TEXT_FIELD = 0x0C                   # SDL_TextInputEvent.text
FONT_VSLOT_CHAR_RECT = 1            # ldwFontImpl vtable: GetCharSourceRect
TEXT_VSLOT_HANDLE_KEY = 2           # ldwTextControlImpl vtable: HandleKey
FONT_TYPE_NAME = ".?AVldwFontImpl@@"
TEXT_TYPE_NAME = ".?AVldwTextControlImpl@@"
JUSTIFIED_STEAL = 9                 # DrawStringJustified: push ebp; mov ebp,esp; sub esp,550h

# (pin name, object file, decorated function name)
FUNCTIONS = (
    ("draw_string", "ldwGameWindow", "?DrawString@ldwGameWindowImpl@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z"),
    ("draw_chars", "ldwGameWindow", "?DrawChars@ldwGameWindowImpl@@QAEHPBDHHH_NUldwColor@@PAVldwFont@@@Z"),
    ("draw_justified", "ldwGameWindow",
     "?DrawStringJustified@ldwGameWindow@@QAEHPBDHHHUldwColor@@PAVldwFont@@_N3H@Z"),
    ("check_for_events", "ldwGameWindow", "?CheckForEvents@ldwGameWindowImpl@@AAEXXZ"),
    ("get_width", "ldwFont", "?GetWidth@ldwFont@@QAEHPBDM@Z"),
    ("next_line", "ldwFont", "?GetNextJustifiedLine@ldwFont@@QAEPBDPBDPADHHAA_N_NM@Z"),
    ("char_rect", "ldwFontImpl", "?GetCharSourceRect@ldwFontImpl@@UAEXHAAUldwRect@@@Z"),
    ("get_image", "ldwFontImpl", "?GetImage@ldwFontImpl@@QAEPAUSDL_Surface@@UldwColor@@@Z"),
    ("text_handle_key", "ldwTextControl", "?HandleKey@ldwTextControlImpl@@UAE_NHHH@Z"),
    ("get_text", "ldwTextControl", "?GetText@ldwTextControl@@QAEXPADH@Z"),
)

# Sites: (site name, pin, how). "entry" = the pin's own address; ("call", symbol) = the target of the pin's call
# to that symbol (every such call in the pin must agree); ("abs", symbol) = the address in the pin's absolute field
# naming that symbol. A site named more than once is derived each way, and the
# DLL refuses the executable unless every derivation agrees.
SITES = (
    ("DRAW_STRING", "draw_string", "entry"),
    ("DRAW_CHARS", "draw_chars", "entry"),
    ("DRAW_JUSTIFIED", "draw_justified", "entry"),
    ("GET_WIDTH", "get_width", "entry"),
    ("NEXT_LINE", "next_line", "entry"),
    ("CHAR_RECT", "char_rect", "entry"),
    ("GET_IMAGE", "get_image", "entry"),
    ("TEXT_HANDLE_KEY", "text_handle_key", "entry"),
    ("GET_TEXT", "get_text", "entry"),
    ("CLIP_RECT", "draw_string", ("call", "?ClipRect@ldwGameWindowImpl@@AAE_NAAUldwRect@@AAH1@Z")),
    ("BLIT_ALPHA", "draw_string",
     ("call", "?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z")),
    ("UPPER_BLIT", "draw_string", ("call", "_SDL_UpperBlit")),
    ("WHITE", "draw_string", ("abs", "?cLdwWhite@@3UldwColor@@B")),     # the game's cLdwWhite colour
    ("WHITE", "draw_justified", ("abs", "?cLdwWhite@@3UldwColor@@B")),
    ("GET_IMAGE", "draw_string", ("call", "?GetImage@ldwFontImpl@@QAEPAUSDL_Surface@@UldwColor@@@Z")),
    ("POLL_EVENT", "check_for_events", ("call", "_SDL_PollEvent")),
    ("EVENTS_GET", "check_for_events", ("call", "?Get@ldwEventManager@@SAPAV1@XZ")),
    ("EVENTS_HANDLE_KEY", "check_for_events", ("call", "?HandleKey@ldwEventManager@@QAEXHHH@Z")),
    ("POST_MESSAGE", "text_handle_key", ("call", "?PostAMessage@ldwEventManager@@QAEXHJ@Z")),
    ("EVENTS_GET", "text_handle_key", ("call", "?Get@ldwEventManager@@SAPAV1@XZ")),
    ("GET_IMAGE", "draw_justified", ("call", "?GetImage@ldwFontImpl@@QAEPAUSDL_Surface@@UldwColor@@@Z")),
    ("DRAW_CHARS", "draw_justified",
     ("call", "?DrawChars@ldwGameWindowImpl@@QAEHPBDHHH_NUldwColor@@PAVldwFont@@@Z")),
)
