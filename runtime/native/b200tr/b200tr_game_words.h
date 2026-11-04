/* Written by runtime/tools/gen_vf2_patch_strings.py (GAME_WORDS); do not edit. */
#pragma once
/* The original game's own words that are no line of the table: the English, how many instructions of the
   game's code hand its address over (push imm32 / mov r32, imm32), and the room of a translation in bytes. */
typedef struct { const char *english; unsigned char refs; unsigned short room; } b200tr_game_word;
#define B200TR_GAME_WORD_COUNT 14
static const b200tr_game_word B200TR_GAME_WORDS[] = {
    { "Manage Games", 1, 60 },
    { "Version 1.2.4, %s", 1, 120 },
    { "Copyright 2012-2014, Last Day of Work.", 1, 120 },
    { "Decor", 1, 60 },
    { "Done", 1, 60 },
    { "%s, Lvl 1", 2, 120 },
    { "%s, Lvl 2", 2, 120 },
    { "Special training is needed to collect this", 1, 200 },
    { "They need a couch or a bed...", 1, 200 },
    { "The code that was entered is not valid.", 2, 250 },
    { "%d coins have been added to your balance.", 2, 250 },
    { "Your brokerage has increased your interest rate by %d%", 1, 250 },
    { "Your brokerage has increased your interest rate by %d", 1, 250 },
    { "There was a problem redeeming the code.\nMake sure you are connected to the internet and try again.", 2, 250 },
    { 0, 0, 0 }
};
