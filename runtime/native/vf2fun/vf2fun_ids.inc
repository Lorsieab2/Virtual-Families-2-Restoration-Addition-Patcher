// vf2fun_ids.inc -- the shared ID registry and the modules built on it.
// Included by vf2fun.cpp (the host registry, Plan and Apply live there).
//
// B200 gives a feature its table entries by growing the stock tables at link
// time (achievementList, achievementOrder, stringTable and its lookup table,
// the image descriptors, ...). The vanilla executable has no relocation table
// and no spare room, so at runtime the entries live in DLL-owned storage and
// the stock readers are pointed at it. Three shapes, all proved by
// runtime/tools/gen_sites.py against the vanilla bytes:
//
//   achievementList   every reader indexes it through a 32-bit displacement of one
//                     instruction (8 of them, the only references in the file): the
//                     displacement is retargeted to a larger copy of the table.
//   achievementOrder  read by one loop in CAchievementsScene::DrawScene through
//                     three fields (count, base, end): retargeted the same way, and the
//                     two constants of the scene's constructor that size the scroll
//                     range follow the row count.
//   strings           ids the stock lookup cannot answer all end in one failure block per
//                     reader ("Unknown String Id!!!!"); the block is replaced with a stub
//                     that answers ids a module registered and falls back to the same text.
//
// IDs are RESERVED, not allocated: a feature's ids are constants (B200's own
// numbers), the same whether or not any other feature is on. Achievement ids are
// slots of the 0x125 records every save already holds, so a registered row never
// changes the save format.

// ---------------------------------------------------------------- registry data
// Modules register during their plan step. A registration belongs to the module
// that made it and is only used if that module is still planned when the
// registry itself is planned (it is last), so a module that fails to plan
// leaves nothing behind.
static const unsigned kAchOrderMax = VF2_ACH_ORDER_MAX;

struct AchRegistration {
    unsigned module;
    unsigned id, target, icon, titleString, descString, coins;
    unsigned after;  // placed directly after this id in the stock order
};
static AchRegistration AchRegistrations[8];
static unsigned AchRegistrationCount;

struct StringRegistration {
    unsigned module;
    unsigned id;
    const char *text;
};
static StringRegistration StringRegistrations[32];
static unsigned StringRegistrationCount;

static unsigned CurrentModule;  // the module whose plan is running
static unsigned PlannedSoFar;   // modules planned successfully so far

// What the registry built (only registrations of planned modules).
static unsigned AchRows[VF2_ACH_ROW_CAPACITY * (VF2_ACH_ROW_SIZE / 4)];
static unsigned AchOrder[kAchOrderMax];
static unsigned AchOrderCount;
static unsigned AchHighestId;

struct ExtString {
    unsigned id;
    const char *text;
};
static ExtString ExtStrings[32];
static unsigned ExtStringCount;

// Ids are rejected, never wrapped or clamped: a bad registration makes the
// module that asked for it fail to plan, which installs nothing for it.
static bool RegisterString(unsigned id, const char *text) {
    if (id <= VF2_STRING_STOCK_MAX_ID
        || StringRegistrationCount >= sizeof(StringRegistrations) / sizeof(StringRegistrations[0]))
        return false;
    for (unsigned i = 0; i < StringRegistrationCount; ++i)
        if (StringRegistrations[i].id == id) return false;
    StringRegistration &r = StringRegistrations[StringRegistrationCount++];
    r.module = CurrentModule;
    r.id = id;
    r.text = text;
    return true;
}

// A row of achievementList. `after` is the stock-order id it follows on the
// Achievements screen. Ids are limited to what DrawAchievement's imm8 bound can
// hold (below 0x80, see the study); higher ids need a jcc-capable stub.
static bool RegisterAchievement(unsigned id, unsigned target, unsigned icon, unsigned titleString,
                                unsigned descString, unsigned coins, unsigned after) {
    if (id < VF2_ACH_STOCK_ROWS || id > VF2_ACH_DRAW_ID_LIMIT_MAX - 1 || id >= VF2_ACH_ROW_CAPACITY)
        return false;
    if (AchRegistrationCount >= sizeof(AchRegistrations) / sizeof(AchRegistrations[0])) return false;
    for (unsigned i = 0; i < AchRegistrationCount; ++i)
        if (AchRegistrations[i].id == id) return false;
    AchRegistration &r = AchRegistrations[AchRegistrationCount++];
    r.module = CurrentModule;
    r.id = id;
    r.target = target;
    r.icon = icon;
    r.titleString = titleString;
    r.descString = descString;
    r.coins = coins;
    r.after = after;
    return true;
}

// ---------------------------------------------------------------- string stubs
static const char *__cdecl LookupExtString(unsigned id) {
    for (unsigned i = 0; i < ExtStringCount; ++i)
        if (ExtStrings[i].id == id) return ExtStrings[i].text;
    return 0;
}

static unsigned StringGetReturn = VF2_STRING_GET_RETURN;
static unsigned StringInlineResume = VF2_STRING_INLINE_RESUME;

// Replaces `mov eax,<unknown text>` in theStringManager::GetString; the next
// instruction is the function's own `ret 4`. eax = the string id on arrival.
static __declspec(naked) void StringGetFailStub() {
    __asm {
        push eax
        call LookupExtString
        add esp, 4
        test eax, eax
        jnz found
        mov eax, VF2_STRING_UNKNOWN_TEXT
    found:
        jmp dword ptr [StringGetReturn]
    }
}

// Replaces `mov dword ptr [esp],<unknown text>` in the text-draw function's
// inlined lookup. ecx = the string id; every other register is live afterwards,
// so all of them (and the flags) are kept.
static __declspec(naked) void StringInlineFailStub() {
    __asm {
        pushfd
        pushad
        push ecx
        call LookupExtString
        add esp, 4
        test eax, eax
        jnz found
        mov eax, VF2_STRING_UNKNOWN_TEXT
    found:
        mov dword ptr [esp + 0x24], eax
        popad
        popfd
        jmp dword ptr [StringInlineResume]
    }
}

// ================================================================ module: id_registry
// Internal: installed exactly when a module that requires it is on and planned.
static bool IdRegistry;

static unsigned RelocatedDisplacement(unsigned fieldVa, unsigned oldBase, const void *newBase) {
    return *(const unsigned *)fieldVa - oldBase + (unsigned)newBase;
}

static void PlanIdRegistry(Plan &plan) {
    // Collect the registrations of the modules that are still planned.
    for (unsigned i = 0; i < StringRegistrationCount; ++i) {
        if (!(PlannedSoFar & (1u << StringRegistrations[i].module))) continue;
        ExtStrings[ExtStringCount].id = StringRegistrations[i].id;
        ExtStrings[ExtStringCount].text = StringRegistrations[i].text;
        ++ExtStringCount;
    }
    // The achievementList copy: the 0x5F stock rows (live, pinned), then the registered rows.
    memcpy(AchRows, (const void *)VF2_ACH_LIST_BASE, VF2_ACH_STOCK_ROWS * VF2_ACH_ROW_SIZE);
    // The order: the stock order (live, pinned), each registered id right after its anchor.
    memcpy(AchOrder, (const void *)VF2_ACH_ORDER_BASE, VF2_ACH_ORDER_STOCK_COUNT * 4);
    AchOrderCount = VF2_ACH_ORDER_STOCK_COUNT;
    unsigned rows = 0;
    for (unsigned i = 0; i < AchRegistrationCount && plan.ok; ++i) {
        const AchRegistration &r = AchRegistrations[i];
        if (!(PlannedSoFar & (1u << r.module))) continue;
        unsigned *row = AchRows + r.id * (VF2_ACH_ROW_SIZE / 4);
        row[0] = r.id;
        row[1] = r.target;
        row[2] = r.icon;
        row[3] = 0;
        row[4] = r.titleString;
        row[5] = r.descString;
        row[6] = r.coins;
        unsigned at = 0;
        while (at < AchOrderCount && AchOrder[at] != r.after) ++at;
        if (at == AchOrderCount || AchOrderCount >= kAchOrderMax) { plan.ok = false; break; }
        for (unsigned k = AchOrderCount; k > at + 1; --k) AchOrder[k] = AchOrder[k - 1];
        AchOrder[at + 1] = r.id;
        ++AchOrderCount;
        ++rows;
        if (r.id > AchHighestId) AchHighestId = r.id;
    }
    // DrawScene's count is a `cmp ebp,imm8`: it must fit a signed byte.
    if (AchOrderCount > VF2_ACH_DRAW_ID_LIMIT_MAX) plan.ok = false;
    if (!plan.ok || (!rows && !ExtStringCount)) return;  // nothing registered: no write at all

    if (rows) {
        for (size_t i = 0; i < sizeof(VF2_ACH_ROW_FIELDS) / sizeof(unsigned); ++i)
            plan.Field(VF2_ACH_ROW_FIELDS[i], 4, RelocatedDisplacement(VF2_ACH_ROW_FIELDS[i], VF2_ACH_LIST_BASE, AchRows));
        // Draw bound: ids below it read their saved flag and draw their row.
        unsigned limit = AchHighestId + 1;
        if (limit < VF2_ACH_STOCK_ROWS) limit = VF2_ACH_STOCK_ROWS;
        for (size_t i = 0; i < sizeof(VF2_ACH_DRAW_BOUND_FIELDS) / sizeof(unsigned); ++i)
            plan.Field(VF2_ACH_DRAW_BOUND_FIELDS[i], 1, limit);
        // Scene: the scroll range grows by one 0x42-pixel row per added order entry.
        unsigned height = VF2_ACH_CONTENT_HEIGHT_STOCK + VF2_ACH_ROW_PITCH * (AchOrderCount - VF2_ACH_ORDER_STOCK_COUNT);
        plan.Field(VF2_SCENE_HEIGHT_FIELDS[0], 4, height);
        plan.Field(VF2_SCENE_HEIGHT_FIELDS[1], 4, height);
        plan.Field(VF2_SCENE_DRAW_COUNT_FIELD, 1, AchOrderCount);
        plan.Field(VF2_SCENE_DRAW_ORDER_BASE_FIELD, 4, RelocatedDisplacement(VF2_SCENE_DRAW_ORDER_BASE_FIELD, VF2_ACH_ORDER_BASE, AchOrder));
        plan.Field(VF2_SCENE_DRAW_ORDER_END_FIELD, 4, (unsigned)(AchOrder + AchOrderCount));
    }
    if (ExtStringCount) {
        plan.Jmp(VF2_STRING_GET_FAIL, 5, (const void *)&StringGetFailStub);
        plan.Jmp(VF2_STRING_INLINE_FAIL, 7, (const void *)&StringInlineFailStub);
    }
}

// ================================================================ module: achievement_records
// B200 patch_custom_achievements, CAchievement::LoadState. The save holds 0x125
// records of 12 bytes. Stock keeps the first 0x5F and, if any later record is
// non-empty, clears 200 records starting at record 0x5D -- which also wipes
// Bottlologist (0x5E), because nothing but a modded save ever has data there.
// B200 validates and clears only the reserved tail (records 0xAC..0x124), so
// the rows below it (0x5F..0xAB, the ids features register) survive a load
// whether or not the feature that owns them is on. Vanilla-format saves have
// zeros there, so they load exactly as before.
static bool AchievementReservedRecords;

static void PlanAchievementRecords(Plan &plan) {
    const unsigned reservedOffset = VF2_ACH_RESERVED_FIRST * VF2_ACH_RECORD_SIZE;
    const unsigned reservedCount = VF2_ACH_RECORD_COUNT - VF2_ACH_RESERVED_FIRST;
    plan.Field(VF2_LOAD_CTR_START_FIELD, 1, 0);
    plan.Field(VF2_LOAD_SCAN_PTR_FIELD, 4, reservedOffset);
    plan.Field(VF2_LOAD_SCAN_END_FIELD, 4, reservedCount);
    plan.Field(VF2_LOAD_CLEAR_PTR_FIELD, 4, reservedOffset);
    plan.Field(VF2_LOAD_CLEAR_COUNT_FIELD, 4, reservedCount);
}

// ================================================================ module: ornament_achievement
// B200's Holiday Ornaments achievement row only (see the module table in
// vf2_runtime_sites.py for what is NOT included). Values are B200's:
// patch_custom_achievements row (0x5F, target 12, icon 0x1ED, 0, title, desc, 0),
// strings 0xE31/0xE32 from holiday_ornament_achievement_*_string_id(), and
// patch_achievements_scene inserts the id right after Bottlologist (0x5E).
static bool OrnamentAchievement;

static void PlanOrnamentAchievement(Plan &plan) {
    bool ok = RegisterString(VF2_STRING_ORNAMENT_TITLE, "Ornamentologist")
           && RegisterString(VF2_STRING_ORNAMENT_DESC, "You completed the collection of holiday ornaments.")
           && RegisterAchievement(VF2_ACH_ORNAMENT_ID, VF2_ACH_ORNAMENT_TARGET, VF2_ACH_ORNAMENT_ICON,
                                  VF2_STRING_ORNAMENT_TITLE, VF2_STRING_ORNAMENT_DESC, 0,
                                  VF2_ACH_ORDER_ANCHOR_BOTTLOLOGIST);
    if (!ok) plan.ok = false;
}
