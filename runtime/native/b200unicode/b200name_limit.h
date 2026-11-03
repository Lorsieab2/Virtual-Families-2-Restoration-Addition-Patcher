// The one name limit in C (src/vf2_game_text.py: NAME_LETTERS and NAME_BOX_BYTES, "One character limit for every name
// box"). tests/test_name_limit.py checks these two numbers against the Python definition, so they are written here and
// nowhere else in the native sources. Included by:
//   * b200unicode.cpp for vf2unicode_b200.dll / vf2unicodefont_b200.dll (b200names.inc: the name boxes' limits);
//   * the same source built as vf2clip_b200.dll (b200clip.inc: a paste into a name box is cut to kNameLetters);
//   * b200history.cpp (vf2history_b200.dll: a whole name from the Names file is at most kNameBoxBytes).
#pragma once

static const unsigned kNameLetters = 300;              // characters (grapheme clusters) a name box takes
static const unsigned kNameBoxBytes = 1200;            // bytes of the stored form it holds (= TEXT_BOX_CEILING_BYTES)
