# Translations

This is the public folder for **Virtual Families 2** translations made by players. Every file here
is one language, named with its language code: `fr.tsv` (French), `es.tsv` (Spanish),
`pt-BR.tsv` (Brazilian Portuguese), `ja.tsv` (Japanese) and so on.

Anyone can add a translation or improve one. Accepted translations ship with the patcher, and the
translator's credit name is shown in the credits.

## The easy way

1. **Get a file.** To improve a language, open its file in this folder and press the download
   button ("Download raw file"), or use the patcher's **Download from GitHub...** button (Tools tab,
   **Translations...**), which lists this folder and installs the ones you pick. To start a new
   language, press **Make a translation...** in the same window: it writes the English template
   (every line of the game and of the patches, with the room each one has) and opens an editor.
2. **Translate it** with any text editor (Notepad is fine) or a spreadsheet. Fill in the
   **Translation** column only; leave **Key** and **English** exactly as they are. Save it as
   **UTF-8** text, named `<language code>.tsv` (see "File names" below if that language is
   already here).
3. **Upload it.** Press **Share on GitHub...** in the patcher's Translations window (it asks you first,
   then for the credit name you want shown, and opens this page), or come back to this folder on GitHub
   yourself and choose **Add file → Upload files**, drop your file in, and press **Propose changes**.
   You need a free GitHub account: https://github.com/signup. If you cannot change this repository yourself,
   GitHub copies it for you and opens a pull request automatically; you do not need to know git.

A robot then checks the file and writes the result on your pull request (see "What happens next").

## Before you share: please read

This is the notice the patcher's **Share** button shows, and it applies to uploading here too:

> This button allows you to share your game translation to the patcher's Public Github. IF ACCEPTED, everyone who uses this patcher will be able to see your translation in the game and your username will be included in the credits. Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!
>
> Email addresses are never saved and are rejected from translation files.
>
> This feature is meant to be a community collaboration tool for game modding only.
>
> You will need a Github account to proceed. Continue?

Every file shared here is also **sent to VirusTotal** to be checked for viruses, and VirusTotal's
partners (security companies) can see the files sent to it. That is one more reason never to put
private details in a translation file.

## Your credit name

The credit is the **@translator** row near the top of the file. Type the name you want shown in
the credits in its **Translation** column (the third column), for example:

```
@translator		Marie (Lyon)
```

- Use a nickname or your GitHub username: plain text, at most 60 letters.
- **Never put an email address in it** (or anywhere in the file). A file with an email address is
  rejected, and the check names the line so you can remove it.
- Leave it empty if you do not want a credit.

## File names

Shared translations land in this folder as `<language code>.tsv`, for example `fr.tsv`.

If that language already has a file, **no one's file is overwritten**: yours is named
`<language code>-<credit slug>.tsv` instead, for example `fr-marie-lyon.tsv` for the credit name
"Marie (Lyon)". The credit slug is your credit name in plain ASCII, lower-case, using only `a-z`,
`0-9` and `-`, at most 40 characters (`anonymous` when there is no credit name). If that name is
taken too, a number is added: `fr-marie-lyon-2.tsv`, `fr-marie-lyon-3.tsv`... The patcher's Share
button picks the name for you.

You may improve your own file under its own name. A pull request that replaces a file credited to
someone else is refused, and the check says which `<language code>-<credit slug>.tsv` name to use.

## Test files

A file whose language name (`@language`) or credit name (`@translator`) starts with `(TEST)` is a
test file. Test files may be shared here to try the checks out, but they are **never packaged into
a release** of the patcher. Every other accepted translation may ship with the patcher.

## The format, in short

A translation is a tab-separated table: `Key`, `English`, `Translation`, `Notes`. It is the same
format every patcher in this family uses (the Virtual Villagers Fun Patcher's
`docs/translation-file-format.md`, version 1). The rows starting with `@` describe the file:

| Row | Translation column |
|---|---|
| `@format` | `1` |
| `@game` | (optional: the game's name in your language) |
| `@language` | the language's own name, e.g. `Français` |
| `@code` | the language code, the same as the file name, e.g. `fr` |
| `@translator` | your credit name (optional, never an email) |

Things to keep in a translation:

- **Placeholders** like `%d` and `%s`: the same ones, in the same order.
- **Names in braces** like `{name}`: every one the English has, spelled the same.
- **Percent signs:** only the placeholders the line's own English has count as placeholders. Any other `%` is
  plain text, so write a percent sign as you normally would: `2 %`, `2 %` (no-break space), `50 % de réduction`.
  Where the game formats a line with printf, the patcher hands it each such `%` as `%%`, so it still shows one `%`
  (the extra byte counts toward the line's room); anywhere else it is shown as you wrote it. `%%` shows as two
  percent signs unless the English has `%%` itself.
- `\n` is a line break; write `{{` `}}` for braces.
- **Choices by person or number** are allowed:
  `{%1: m=Il est content | f=Elle est contente | o=Iel est content·e}` picks by the person's sex
  (m, f, o), and `%d {%1: one=pomme | other=pommes}` picks by the number (your language's plural
  forms: zero, one, two, few, many, other, or an exact `=0`, `=1`...).

## What happens next

When you open the pull request, two checks run on it:

1. **VirusTotal scan.** Every file is scanned. If any virus scanner reports it as malicious or
   suspicious, or the scan could not run at all, the check fails and nothing is accepted.
2. **Format check.** The file is read as data (never run) and checked: its rows, keys,
   placeholders and choices, the language code, and that there is no email address anywhere.
   The result is written on your pull request, naming each line to fix.

You can fix the file and upload it again to the same pull request; both checks run again. Only
`.tsv` files directly in this folder, at most 2 MB, can be shared.

The owner accepts a translation that passed both checks by merging it, or by adding the
**accept-translation** label (which merges it). A check that fails takes the label off again.
