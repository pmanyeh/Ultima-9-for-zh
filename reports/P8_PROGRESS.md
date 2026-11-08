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
| W2g | Britain/Lydia, Margery, Meribeth, Nicodemus, Nimrond, Olsen, Olwyn, Ooli, Orson | 247 | 247 | PASS, 0 errors | not yet |
| W2h | Britain/Peiter, Renald, Richard, Robison, Roprick, Sarah, Siona, Skeleton1, Thadious, Tyson | 222 | 222 | PASS, 0 errors | not yet |
| W3a | Paws (all 9 files) | 181 | 181 | PASS, 0 errors | not yet |
| W4a | MiscNPC/Agmar, Ailuj, Anaaj, Bakura, Blackthorn, Brock | 211 | 210 | PASS, 0 errors | not yet |
| W4b | MiscNPC/Calan, Ciara, CircleStones, Cleo, Colando, Elizabeth, Eve | 186 | 186 | PASS, 0 errors | not yet |
| W4c | MiscNPC generic NPCs, Geoffrey, GeoffreyGhost, Groldek, Guardian | 169 | 169 | PASS, 0 errors | not yet |
| W4d | MiscNPC/Jaana, JaanaGhost, Julia, JuliaGhost, Khelereth, Lothar, Lyssa, Malchir | 182 | 182 | PASS, 0 errors | not yet |
| W4e | MiscNPC/Marek, Maria, Mathis, questions, Rand | 178 | 173 | PASS, 0 errors | not yet |
| W4f | MiscNPC/Raven (4677-4870) | 194 | 194 | PASS, 0 errors | not yet |
| W4g | MiscNPC/Raven (4871-5040) | 170 | 170 | PASS, 0 errors | not yet |
| W4h | MiscNPC/Raven (5041-5146), RavenCourt, RavenDress, RestlessSpirit, Sentinel | 167 | 167 | PASS, 0 errors | not yet |
| W4i | MiscNPC/Shamino, ShaminoVoice, ShrineSpirituality, Stephen, Umberto, travelers, WyrmguardDamon, Yerffoeg | 235 | 233 | PASS, 0 errors | not yet |
| W5a | BuccaneersDen/Aneassa to Herzog | 179 | 179 | PASS, 0 errors | not yet |
| W5b | BuccaneersDen/Herzog (end), Jade, Jonah, Katie, Keagan, Linus, Montego, Omar | 183 | 183 | PASS, 0 errors | not yet |
| W5c | BuccaneersDen/Omar (end), Pearli, Phineus, Samhayne, Sasha, Warrick | 181 | 181 | PASS, 0 errors | not yet |
| W6a | NewMagencia/Katrina, ShrineHumility | 80 | 78 | PASS, 0 errors | not yet |
| W7a | Moonglow/Batista, Byron, Duncan, Ella, hairam | 190 | 190 | PASS, 0 errors | not yet |
| W7b | Moonglow/hairam (end), Janus, Joshua, Kyra, Leeland, Linda, Mariah, MariahGhost, Markus | 192 | 192 | PASS, 0 errors | not yet |
| W7c | Moonglow/Markus (end), Marna, generic, Oracle, Phillipa, Randolas, ShrineHonesty, Tommy, Tydus | 188 | 186 | PASS, 0 errors | not yet |

Notes:

- Journal lines (`category: journal`) are translated but show English in game (journal path not drawn by the runtime).
- Layout warnings for 3-line text are accepted where the 3-line opening line 4164 was confirmed in game.
- W2g tool change: a record may declare `not a term: X` in `notes` when a source word only looks like
  an approved term (`Feeling better?`); validate then skips that term's target and annotation checks
  for the record. Tested in `tests/test_p8a_terms.py`.
- W4a: 3606 (Blackthorn's incantation) stays in English.
- W4e: typed answers 4651, 4654, 4657, 4660, 4662 (mantra, Word of Power, password, incantations) stay in English.
- W4i: typed answers 5317 (om) and 5328 (vas mani corp) stay in English.
- W6a: typed answers 6118 (lum) and 6128 (vas mani corp) stay in English.
- W7c: typed answers 5951 (ahm) and 5964 (vas mani corp) stay in English.
