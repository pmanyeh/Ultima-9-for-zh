# P8 Translation Progress

Running log of authorized P8 dialogue batches after wave 2a. Each batch: local workset export,
translation per `translation/TRANSLATION_GUIDE.md`, import, `validate` PASS, unit tests OK, commit.
No runtime or executable change. In-game checks are recorded in their own reports.

| Batch | Conversation files | Entries | Translated | validate | In game |
| --- | --- | --- | --- | --- | --- |
| W1 | MiscNPC/gypsy, MiscNPC/Hawkwind (+229) | 273 | 273 | PASS | session 1 (`reports/P8_W1_OPENING.md`) |
| W2a | Britain/LordBritish, Iolo, IoloGhost, ShrineCompassion | 237 | 235 | PASS | not yet (`reports/P8_W2A_BRITAIN_CORE.md`) |
| W2b | Britain/Aidon, Aleena, Altara, Altomar | 297 | 297 | PASS, 0 errors | not yet |
| W2c | Britain/Amoranth, Angus, Bailey, Cameron, CaptainBill, Castro, Dara | 200 | 200 | PASS, 0 errors | not yet |
| W2d | Britain/Dermot, Elva, Evidious, FarmerBob, Flann, Giovanni, Gwenno, Hans, Hennington | 271 | 271 | PASS, 0 errors | not yet |
| W2e | Britain/Jared, Jarlath, Jastral, Keller, Killigan | 192 | 192 | PASS, 0 errors | not yet |
| W2f | Britain/Kimberly, Laurana, Leon | 174 | 174 | PASS, 0 errors | not yet |

Notes:

- Journal lines (`category: journal`) are translated but show English in game (journal path not drawn by the runtime).
- Layout warnings for 3-line text are accepted where the 3-line opening line 4164 was confirmed in game.
