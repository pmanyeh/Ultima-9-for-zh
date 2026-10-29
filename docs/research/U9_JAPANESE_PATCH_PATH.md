# Public Japanese patch mechanism — source audit

P4-A, 2026-10-29. Source-only inspection of Fenyx4/UltimaPatcher commit
`c5db7b77b93a3b99b27556c3e5d8654d1679ced5`. No Japanese assets, executable
delta/signature payloads or Locale Emulator binaries were fetched or executed.
The no-checkout partial clone is ignored; only selected text source blobs were
read. No Japanese executable was reconstructed.

## CONFIRMED — text installation branch

[U9Form.vb lines 807–844](https://github.com/Fenyx4/UltimaPatcher/blob/c5db7b77b93a3b99b27556c3e5d8654d1679ced5/UltimaPatcher/U9Form.vb#L807)
checks the selected downloaded language pack and recursively copies its `static/`
directory into the game installation. When the selection is `Jp`:

- Current installed `u9.exe` is opened as the delta basis.
- `Files/U9JPLanguagePatch/u9.exe.octodiff` is read through BinaryDeltaReader;
  DeltaApplier writes an intermediate `Files/U9JPLanguagePatch/u9.exe`.
- That generated executable is copied to the installation as `u9.jp.exe`.
- Locale Emulator 2.5.0.1's directory is copied to the installation, and its
  `LEProc.exe` is also copied over the normal launcher name `u9.exe`.
- The UI tells the user that Japanese Windows language support must be installed.
- For non-Japanese selections the branch instead restores the bundled `u9.exe`.

CONFIRMED: `signatureFilePath` names `u9.exe.sig`, but that variable is not read
by this installation block. `SkipHashCheck = False` is explicitly set on the
delta applier. The project references Octodiff 1.3.23.0. These source observations
do not identify a baseline SHA-256 or prove that this project's English GOG
executable is a compatible delta basis. Exact accepted basis/hash is UNKNOWN;
the delta/signature payloads were deliberately not inspected or applied.

## CONFIRMED — locale launcher and resources

[U9JPLanguagePatch/u9.bat](https://github.com/Fenyx4/UltimaPatcher/blob/c5db7b77b93a3b99b27556c3e5d8654d1679ced5/UltimaPatcher/Files/U9JPLanguagePatch/u9.bat)
contains the launch command `LEProc.exe u9.jp.exe`.

CONFIRMED: the text button copies the selected pack's entire `static/` tree;
the separate speech button (lines 781–794) copies its `Movies/` and `sound/`
trees when present. The recursive copy helper overwrites destination files.
UNKNOWN: the exact Japanese language-pack file manifest and which particular
FLX/font files it contains; no language pack was downloaded to answer that.

## STRONG EVIDENCE — executable-side localization

The explicit delta-generated `u9.jp.exe` and locale launcher show that the
documented Japanese installation mechanism involves executable-side changes,
in addition to language resources. This is not evidence of what the changes do.

HYPOTHESIS: the altered executable and locale environment may affect decoding,
DBCS handling, fonts or layout. UNKNOWN: which functions change, native CJK path,
font resources, charset/codepage settings and compatibility with this baseline.
No conclusion about those internals is drawn from the filename alone.

## Reproducibility and boundary

Use `git show <pinned-commit>:UltimaPatcher/U9Form.vb` in a no-checkout partial
clone; inspect the text handler and launcher script above. The source SHA-256 is
`d610c5f68b7bf1e017dcc806718b54f879d7f21dcd95da4301f65da6f3b8dade`.
Launcher-script SHA-256:
`aaf2071f1a5124ff63b1527f194da8bb60adc86ebb6c00ace7c70c7d3835bfa9`.
Actual English/Japanese binary differential remains NOT EXECUTED because no
lawful local Japanese oracle is available. This batch does not acquire one.
