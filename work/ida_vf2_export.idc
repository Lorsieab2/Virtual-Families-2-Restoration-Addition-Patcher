#include <idc.idc>

static has_kw(name)
{
  auto l;
  l = tolower(name);
  if (strstr(l, "collect") >= 0) return 1;
  if (strstr(l, "communityevent") >= 0) return 1;
  if (strstr(l, "event") >= 0) return 1;
  if (strstr(l, "villager") >= 0) return 1;
  if (strstr(l, "anim") >= 0) return 1;
  if (strstr(l, "inventory") >= 0) return 1;
  if (strstr(l, "furniture") >= 0) return 1;
  if (strstr(l, "string") >= 0) return 1;
  if (strstr(l, "imagelist") >= 0) return 1;
  if (strstr(l, "imageindex") >= 0) return 1;
  return 0;
}

static main()
{
  auto out, ea, name, n, i;
  Wait();
  out = fopen("C:\\Users\\Owner\\Documents\\Codex\\2026-06-13\\files-mentioned-by-the-user-virtual\\work\\ida_vf2_patched_export.tsv", "w");
  if (out == 0)
  {
    Exit(2);
  }
  fprintf(out, "kind\tea\tname\n");
  ea = FirstFunc();
  while (ea != BADADDR)
  {
    name = GetFunctionName(ea);
    if (has_kw(name))
    {
      fprintf(out, "func\t%08X\t%s\n", ea, name);
    }
    ea = NextFunc(ea);
  }
  n = GetEntryPointQty();
  for (i = 0; i < n; i = i + 1)
  {
    ea = GetEntryPoint(GetEntryOrdinal(i));
    name = Name(ea);
    if (has_kw(name))
    {
      fprintf(out, "entry\t%08X\t%s\n", ea, name);
    }
  }
  for (ea = MinEA(); ea != BADADDR; ea = NextAddr(ea))
  {
    name = Name(ea);
    if (name != "" && has_kw(name))
    {
      fprintf(out, "name\t%08X\t%s\n", ea, name);
    }
  }
  fclose(out);
  Exit(0);
}
