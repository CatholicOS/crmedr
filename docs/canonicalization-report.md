# Draft canonical IDs — Martyrologium Romanum (CRMEDR working document)

Generated mechanically from the Latin texts (editio altera 2004, 'elaborazione' transcription,
corrected against the Vatican print where noted). **All IDs are drafts for committee review.**

## Scheme

`mr:MMDD-slug` — MMDD anchors the entry's placement in the editio altera 2004;
the slug is the Latin nominative lemma of the first-named subject, ASCII-folded,
lowercase, honorific-free (no sanctus/beatus). Each edition's actual entry number,
asterisk, and placement are per-edition attributes, not part of the identity.

Rules applied, in order:
1. Personal names extracted after the first sanctity marker (sancti/beatae/sanctorum...);
   genitive converted to nominative by declension rules + a curated irregular map.
2. Religious-name titles after a/de remain uninflected (teresia-a-iesu, ignatius-de-loyola).
3. Papal ordinals rendered as roman numerals (pius-x, clemens-i); non-papal regnal
   ordinals remain Latin adjectives (ludovicus-nonus).
4. Cognomento epithets appended (petrus-chrysologus, albertus-magnus).
5. Two named subjects: both joined (cosmas-et-damianus). Three or more, or explicit
   'et sociorum': first-named + et-socii (paulus-miki-et-socii).
6. Marian titles: maria + invocation (maria-de-lourdes, maria-de-guadalupe).
7. Christological/liturgical feasts: manual override slugs (see below).
8. Anonymous groups: class + number + place, mechanically (quadraginta-milites-sebastem).
9. Same-slug collisions within a day: the day's lead keeps the bare slug; numbered
   entries take the place of death; ordinals as last resort.

## Special identity decisions

**Feb 28/29**: the four leap-day elogia printed twice in both IT and LA editions carry
ONE identity each, anchored at 0229; the Feb 28 rows bear the same ID:
- mr:0229-hilarius (also at Feb 28, voce 4)
- mr:0229-oswaldus (also at Feb 28, voce 5)
- mr:0229-antonia-de-florentia (also at Feb 28, voce 6)
- mr:0229-augustus-chapdelaine (also at Feb 28, voce 7)

**Entries absent from the "with IDs" workbook** (both present in the parallel-texts
workbook, whose reviewer comments document their numbering across editions):
- mr:0104-abrunculus — entry 2* in the Latin print, absent from the Italian (CEI)
  edition and from Mons. Barba's Word transcription
- mr:0104-emmanuel-gonzalez-garcia — entry 12* in the Latin print, numbered 11* in the
  Italian (CEI) edition and in Mons. Barba's Word transcription (Bl. M. González García,
  canonized 2016: status change with no ID change, as intended)

**Per-edition asterisk discrepancies (29)**: the registry follows the Latin print; each
affected entry carries a note. All were counter-verified against the page scans of BOTH
editions (July 2026), independently of the digitized workbook:

- *Latin editio altera 2004 print*: presence claims via the OCR text layer with visual
  spot-checks (sancti Servuli 4\*, sancti Wendelini 8\*, sancti Gohardi 7\* confirmed on
  scan), and every absence claim visually confirmed on the scan (clean bold numbers with
  asterisked neighbouring entries ruling out OCR dropout).
- *Italian (CEI) edition print*: all 23 claimed unasterisked entries visually confirmed
  as plain numbers on the scans (each adjacent to cleanly printed asterisked entries),
  and all 6 claimed asterisked entries confirmed (Rebecca 11\* and the Nam Định martyrs
  11\* visually; the remaining four via the OCR text layer, where asterisk presence is
  reliable). The workbook's CEI digitization is therefore fully corroborated for these
  entries: no transcription taint detected.

Asterisked in the Latin print, no asterisk in the CEI edition (23):
mr:0104-ferreolus (4\*), mr:0104-rigomerus (5\*), mr:0104-pharaildis (7\*),
mr:0122-ladislaus-batthyany-strattmann (15\*), mr:0502-boleslaus-strzelecki (12\*),
mr:0512-imelda-lambertini (10\*), mr:0524-servulus (4\*), mr:0611-bardo (4\*),
mr:0624-gohardus (7\*) — note: the earlier draft called this entry "Goardo" without a date;
it is Gohardus of Nantes at June 24, not Goar of the Rhine (July 6, plain 7.) nor
Agoardus (June 24, plain 4.), both of which were visually confirmed unasterisked —
mr:0711-leontius (5\*), mr:0718-tarsicia-mackiv (13\*), mr:0730-godeleva (6\*),
mr:0802-betharius (8\*), mr:0807-donatus-vesontione (7\*),
mr:0909-franciscus-garate-aranguren (10\*), mr:1021-wendelinus (8\*), mr:1026-eata (7\*),
mr:1103-libertinus (3\*), mr:1103-odrada (10\*), mr:1118-theofredus (6\*),
mr:1119-eudo (6\*), mr:1215-marinus (3\*), mr:1230-egwinus (7\*).

Plain in the Latin print, asterisked in the CEI edition (6):
mr:0323-rebecca-de-himlaya (11.), mr:0812-iacobus (11., Nam Định martyrs),
mr:0821-iosephus (11., Hưng Yên), mr:1201-domnolus (5.), mr:1203-lucius (5., Chur),
mr:1212-simon-phan (11., Phan Đắc Hòa).

**Slug correction**: the workbook ID mr:0206-paulus-mikus-et-socii is corrected on
extraction to mr:0206-paulus-miki-et-socii — surnames are not latinized unless an
already well-known Latin form exists (rule 5's example shows the intended form).

**Repaired source text**: the Word transcription's 3-20 v1 was truncated; the la cell was
restored from the print (Commemoratio sancti Archippi...). ID: mr:0320-archippus.

## Manual feast overrides (34)

- mr:0101-maria-dei-genetrix  (1/1 voce 1)
- mr:0103-nomen-iesu  (1/3 voce 1)
- mr:0106-epiphania-domini  (1/6 voce 1)
- mr:0125-conversio-sancti-pauli  (1/25 voce 1)
- mr:0202-praesentatio-domini  (2/2 voce 1)
- mr:0217-septem-fundatores-servorum-mariae  (2/17 voce 1)
- mr:0222-cathedra-sancti-petri  (2/22 voce 1)
- mr:0320-archippus  (3/20 voce 1)
- mr:0325-annuntiatio-domini  (3/25 voce 1)
- mr:0325-bonus-latro  (3/25 voce 2)
- mr:0531-visitatio-beatae-mariae-virginis  (5/31 voce 1)
- mr:0717-alexius  (7/17 voce 5)
- mr:0724-translatio-trium-magorum  (7/24 voce 13)
- mr:0728-martyres-thebaidis  (7/28 voce 3)
- mr:0805-dedicatio-basilicae-sanctae-mariae  (8/5 voce 1)
- mr:0806-transfiguratio-domini  (8/6 voce 1)
- mr:0815-assumptio-beatae-mariae-virginis  (8/15 voce 1)
- mr:0820-pius-x  (8/20 voce 9)
- mr:0822-maria-regina  (8/22 voce 1)
- mr:0908-nativitas-beatae-mariae-virginis  (9/8 voce 1)
- mr:0912-nomen-mariae  (9/12 voce 1)
- mr:0913-dedicatio-basilicarum-hierosolymis  (9/13 voce 3)
- mr:0914-exaltatio-sanctae-crucis  (9/14 voce 1)
- mr:0915-maria-perdolens  (9/15 voce 1)
- mr:1002-angeli-custodes  (10/2 voce 1)
- mr:1003-duo-ewaldi  (10/3 voce 7)
- mr:1101-omnes-sancti  (11/1 voce 1)
- mr:1102-omnium-fidelium-defunctorum  (11/2 voce 1)
- mr:1109-dedicatio-basilicae-lateranensis  (11/9 voce 1)
- mr:1118-dedicatio-basilicarum-petri-et-pauli  (11/18 voce 1)
- mr:1121-praesentatio-beatae-mariae-virginis  (11/21 voce 1)
- mr:1208-conceptio-immaculata-beatae-mariae-virginis  (12/8 voce 1)
- mr:1224-avi-iesu-christi  (12/24 voce 1)
- mr:1225-nativitas-domini  (12/25 voce 1)

## Anonymous groups — mechanical slugs, review recommended (39)

- mr:0114-monachi-raithi
  - *Incipit:* Commemorátio sanctórum monachórum, qui Raíthi et…
- mr:0205-plurimi-martyres-ponto
  - *Incipit:* In Ponto, commemorátio plurimórum sanctórum mártyrum…
- mr:0208-martyres-monachi-dii-constantinopolitani
  - *Incipit:* Commemorátio sanctórum mártyrum monachórum monastérii Dii…
- mr:0209-plurimi-martyres-alexandriae
  - *Incipit:* Item Alexandríæ, pássio plurimórum sanctórum mártyrum,…
- mr:0211-plurimi-martyres-numidia
  - *Incipit:* Commemorátio plurimórum sanctórum mártyrum, qui in…
- mr:0212-martyres-carthagine
  - *Incipit:* Carthágine, commemorátio sanctórum mártyrum Abitinénsium, qui,…
- mr:0219-monachi-martyres-palaestina
  - *Incipit:* Commemorátio sanctórum monachórum et aliórum mártyrum,…
- mr:0220-quinque-martyres-tyri
  - *Incipit:* Commemorátio beatórum quinque mártyrum, qui, sub…
- mr:0228-presbyteri-diaconi-plurimi-alexandriae
  - *Incipit:* Commemorátio sanctórum presbyterórum, diaconórum et aliórum…
- mr:0306-quadraginta-duo-martyres-syria
  - *Incipit:* In Sýria, pássio sanctórum quadragínta duórum…
- mr:0309-quadraginta-milites-sebastem
  - *Incipit:* Apud Sebástem in Arménia, pássio sanctórum…
- mr:0330-plurimi-martyres-constantinopoli
  - *Incipit:* Commemorátio sanctórum plurimórum mártyrum, qui Constantinópoli,…
- mr:0405-centum-undecim-viri-novem-mulieres-martyres
  - *Incipit:* Item, commemorátio centum úndecim virórum ac…
- mr:0405-martyres-regiis
  - *Incipit:* Régiis in Mauretánia, pássio sanctórum mártyrum,…
- mr:0407-ducenti-milites-martyres-sinope
  - *Incipit:* Sinópe in Ponto, sanctórum ducentórum mílitum…
- mr:0509-martyres-trecenti-decem-perside
  - *Incipit:* In Pérside, sanctórum mártyrum trecentórum et…
- mr:0516-quadraginta-quattuor-monachi-palaestina
  - *Incipit:* In Palæstína, pássio sanctórum quadragínta quáttuor…
- mr:0521-martyres-alexandriae
  - *Incipit:* Commemorátio sanctórum mártyrum utriúsque sexus, quos…
- mr:0523-martyres-cappadocia
  - *Incipit:* Commemorátio sanctórum mártyrum, qui in Cappadócia…
- mr:0523-martyres-mesopotamia
  - *Incipit:* Item commemorátio sanctórum mártyrum, qui eódem…
- mr:0524-triginta-octo-martyres-philippopoli
  - *Incipit:* Commemorátio sanctórum trigínta et octo mártyrum,…
- mr:0708-monachi-constantinopoli
  - *Incipit:* Constantinópoli, pássio sanctórum monachórum Abrahamitárum, qui,…
- mr:0801-septem-fratres-martyres-antiochiae
  - *Incipit:* Commemorátio passiónis sanctórum septem fratrum mártyrum,…
- mr:0809-martyres-constantinopoli
  - *Incipit:* Constantinópoli, commemorátio sanctórum mártyrum, qui, cum…
- mr:0810-martyres-alexandriae
  - *Incipit:* Commemorátio sanctórum mártyrum, qui Alexandríæ in…
- mr:0814-octingenti-martyres-hydrunti
  - *Incipit:* Hydrúnti in Apúlia, beatórum fere octingentórum…
- mr:0830-sexaginta-martyres-coloniae-sufetanae
  - *Incipit:* Commemorátio sanctórum sexagínta mártyrum, qui, Colóniæ…
- mr:1005-martyres-treviris
  - *Incipit:* Tréviris in Gállia Bélgica, commemorátio sanctórum…
- mr:1010-septem-martyres-presbyteri-septam
  - *Incipit:* Apud Septam in Mauritánia Tingitána, pássio…
- mr:1012-martyres-confessores-quattuor-sexaginta-africa
  - *Incipit:* Commemorátio sanctórum mártyrum et fídei confessórum…
- mr:1021-virgines-coloniam-agrippinam
  - *Incipit:* Apud Colóniam Agrippínam in Germánia, commemorátio…
- mr:1113-martyres-africa
  - *Incipit:* In Africa, commemorátio sanctórum mártyrum hispanórum…
- mr:1115-viginti-martyres-hippone-regio
  - *Incipit:* Hippóne Régio in Numídia, sanctórum vigínti…
- mr:1119-mulieres-virgines-viduae-quadraginta-martyres-heracleae
  - *Incipit:* Heracléæ in Thrácia, sanctárum mulíerum, vírginum…
- mr:1206-martyres-africa
  - *Incipit:* In Africa, commemorátio sanctórum mártyrum, témpore…
- mr:1216-plurimae-virgines-africa
  - *Incipit:* Commemorátio plurimárum sanctárum vírginum, quæ, in…
- mr:1217-quinquaginta-milites-eleutheropoli
  - *Incipit:* Eleutherópoli in Palæstína, pássio sanctórum quinquagínta…
- mr:1222-triginta-martyres-romae
  - *Incipit:* Romæ via Labicána in cœmetério ad…
- mr:1222-quadraginta-tres-monachi-raithi
  - *Incipit:* In Raíthi regióne in Ægýpto, sanctórum…

## Collision resolutions (36)

- 1/27 voce 2: iulianus → place sorae
- 1/27 voce 3: iulianus → place cenomanum
- 2/4 voce 5: aventinus → place castelloduni
- 2/4 voce 6: aventinus → place trecis
- 2/13 voce 4: stephanus → place lugduni
- 2/13 voce 5: stephanus → place reate
- 4/1 voce 6: hugo → place gratianopoli
- 4/1 voce 7: hugo → place cisterciensi-bonae
- 4/3 voce 4: ioannes → place neapoli
- 4/3 voce 9: ioannes → place pinnae
- 4/8 voce 3: dionysius → ordinal 2
- 4/8 voce 5: dionysius → place alexandriae
- 4/17 voce 9: robertus → place casae
- 4/17 voce 10: robertus → place molismensi
- 4/23 voce 1: georgius → lead-bare 
- 4/23 voce 6: georgius → place suellis
- 7/3 voce 2: anatolius → place laodiceae
- 7/3 voce 6: anatolius → place constantinopoli
- 8/7 voce 4: donatus → place aretii
- 8/7 voce 7: donatus → place vesontione
- 9/13 voce 8: amatus → place vosegos
- 9/13 voce 10: amatus → place broili
- 9/18 voce 3: ferreolus → place galliae-viennensi
- 9/18 voce 6: ferreolus → place lemovici
- 10/9 voce 5: domninus → place iuliam
- 10/9 voce 8: domninus → place tiferni-tiberini
- 10/23 voce 3: ioannes → place perside
- 10/23 voce 7: ioannes → place syracusis
- 11/11 voce 2: menna → place mareotidem
- 11/11 voce 4: menna → place samnii
- 11/17 voce 2: gregorius → place neocaesareae
- 11/17 voce 7: gregorius → place turonis
- 11/17 voce 11: hugo → place nucariae
- 11/17 voce 12: hugo → place lincolniae
- 11/21 voce 3: maurus → place parentii
- 11/21 voce 6: maurus → place caesenae

## Full-corpus asterisk sweep (July 2026)

All 4,641 workbook rows were matched by text similarity against the OCR text layers of
both printed editions (each row's Latin and Italian text against the numbered-entry
sequences parsed from the respective scans), and every printed entry number and asterisk
was compared against the registry. Rows that could not be matched confidently and every
flagged difference were triaged individually, with visual page-scan verification wherever
the OCR was ambiguous or a claim rested on the absence of a mark.

**Result: zero new asterisk discrepancies.** The 29 documented overrides were
re-validated on both editions; every other matched entry agrees with the registry.

**Unnumbered header eulogies**: 212 entries across 194 days are printed as unnumbered
drop-cap paragraphs in both editions — the header eulogies for celebrations with
liturgical rank that open a day (177 days with one, 16 days with two, and May 25 with
three: Bede + Gregory VII + Mary Magdalene de' Pazzi). The printed numbering counts them
implicitly, so entry numbers stay aligned. They are marked in the registry with an
`unnumbered` flag in the JSON and a parenthesized entry number in the monthly tables;
the per-day counts are derived mechanically from the sweep (`UNNUMBERED_LEADS` in the
extraction script) and validated against the ranked celebrations of the General Roman
Calendar. None carries an asterisk anywhere, consistent with the registry.

The sweep did surface four cross-edition **structural** differences (all verified on the
page scans of both editions):

- **mr:0610-marcus-antonius-durando** (formerly mr:1210-…): the Latin editio altera 2004
  places Bl. Marcantonio Durando at June 10 (entry 9\*); the Italian (CEI) edition places
  him at December 10 (entry 9\*). The MMDD anchor follows the Latin print, so the ID
  changes to mr:0610-marcus-antonius-durando.
- **mr:0712-proclus-et-hilarion**: entry 1 at July 12 in the CEI edition; absent from the
  Latin print, whose July 12 numbering begins at 2 with the gap left unrenumbered.
- **mr:0825-eusebius-et-socii**: entry 3 at August 25 in the CEI edition; absent from the
  Latin print, where the numbered entries begin at 3 (Genesius) after the two unnumbered
  memorias (Louis IX, Joseph Calasanz).
- **mr:0709-maria-a-iesu-crucifixo-petkovic**: entry 11\* at July 9 in the CEI edition;
  absent from the Latin print, whose July 9 ends at entry 10\*. (Bl. Marija Petković was
  beatified on 6 June 2003.)

Numbering conventions observed: the two editions renumber after a removed entry in some
places (Aug 25) and leave a gap in others (July 12); the leap-day elogia are printed
twice with independent numbering in both editions (Feb 28 entries 4–7 = Feb 29 entries
1–4), as already reflected in the registry.

**Slug correction (applied)**: the workbook ID mr:0331-domninus (3/31 voce 4) is
corrected on extraction to mr:0331-guido — the elogium's first-named subject is San
Guido, abbot; "Domninus" comes from the place name (Burgi Sancti Domníni, Borgo San
Donnino, today Fidenza). No collision on the day.

## Post-2004 official variations

The Dicastery's page for the Martyrologium Romanum
(cultodivino.va → pubblicazioni → libri liturgici → aliæ) lists a single official act
issued after the editio typica altera 2004:

> Congregatio de Cultu Divino et Disciplina Sacramentorum, Decretum *Postquam Summus
> Pontifex*, Variationes. XXI octobris 2021 (Prot. N. 394/21) in Notitiae 57 (2021), 222.

Inspection of the published text (Notitiae 57, p. 222) shows the Variationes touch only
the **Praenotanda**, not the elogia:

- **V. De Propriis Martyrologii, n. 38** — dioceses, nations and religious families may
  prepare a *Proprium Martyrologii seu Appendix Martyrologii* for their proper Saints and
  Blesseds (absent from the Martyrologium Romanum, or celebrated on a different day, at a
  different grade, or with a somewhat amplified elogium), to be transmitted to the
  Dicastery for review and confirmation.
- **VI. De aptationibus quæ Conferentiis Episcoporum competunt, n. 41** — in Conference
  editions, elogia proper to the whole nation by concession of the Holy See are placed
  first after the elogia of General-Calendar celebrations and printed in the same type,
  while regional or diocesan elogia always go in a particular Appendix; Conference
  edition texts are approved ad normam iuris and submitted to the Apostolic See for
  confirmation (the same holding, mutatis mutandis, for religious families).

**Impact on the registry: none.** No elogium is added, removed, repositioned or
re-graded by the decree, so no canonical ID is affected; the editio typica altera 2004
remains the anchor. The decree is nonetheless relevant to the registry's future scope:
the *Propria Martyrologii / Appendix* framework it regulates is the natural home for a
committee decision on whether (and under what namespace) eulogies of diocesan, national
and religious-family propria should receive canonical IDs, parallel to how the CLEDR
treats proper liturgical calendars.

## Proper eulogies and owner namespaces (proposal)

Principle: **a proprium that amplifies, moves or re-grades the eulogy of a saint
already in the universal Martyrology does not create a new identity** — n. 38's
"diverso die celebrentur vel alio gradu celebrationis peragantur vel quorum elogium…
amplificare visum est" describes per-proprium *attributes* of the existing `mr:` ID,
exactly as entry number and asterisk are per-edition attributes. Only eulogies absent
from the universal Martyrology receive proper IDs, with an owner segment:

- `mr:MMDD-slug` — universal (editio typica); the existing 4,639 IDs, unchanged;
- `mr:<iso2>:MMDD-slug` — national proprium; the bare two-letter alphabetic segment is
  reserved for ISO 3166-1 alpha-2 codes (`mr:it:…`), consistent with the country codes
  already used in this registry;
- `mr:cecdr/<circumscription>:MMDD-slug` — diocesan or eparchial proprium, keyed by the
  [CECDR](https://github.com/CatholicOS/cecdr) canonical ID without its prefix
  (`mr:cecdr/us-boston:…`);
- `mr:ciclsaldr/<institute>:MMDD-slug` — religious-family proprium, keyed by the
  [CICLSALDR](https://github.com/CatholicOS/ciclsaldr) canonical ID without its prefix
  (`mr:ciclsaldr/ofm:…`), owned by an institute or by a family grouping
  (`mr:ciclsaldr/familia-franciscana:…`).

`MMDD` in a proper ID anchors to the proprium's own text as confirmed by the Dicastery
(the confirmation n. 38 requires guarantees a citable official act). Owner segments are
syntactically unambiguous: four digits = placement, two alphabetic letters = ISO
nation, `registry/key` = a CatholicOS registry key. All of this is a draft for
committee review, to be decided together with the namespace prefixes of the three
registries (`mr:` / `circ:` / `icl:`).

## Deprecated IDs from historical editions (draft)

The digitization of the public-domain **1749 (Benedict XIV) edition** in the
[martyrology-api](https://github.com/CatholicOS/martyrology-api) was mechanically
aligned against this registry (July 2026): of its 2,938 elogia, 1,688 matched a
current ID on the same calendar day and 103 on a different day (saints repositioned by
the post-conciliar reform — e.g. Telesphorus Jan 5 → Jan 2, Simeon Stylites Jan 5 →
Jul 27), using name-stem and text-similarity evidence with per-match method and score
recorded in the edition's `alignment.json`.

The remaining **1,236 elogia with no identified counterpart in the editio altera 2004
received coined canonical IDs with `deprecated: true`**, listed in
`data/deprecated_ids.json` and merged into the registry (`entry_count` now counts
`current_count` + `deprecated_count`). Their `MMDD` anchors the placement in the
edition named by `attested_in`, and each carries a `subject_la` (the extracted
first-named subject in nominative display form).

Coined slugs follow the registry's own rules: **nominative lemma** of the first-named
subject (genitives converted via an empirical genitive→nominative dictionary mined
from the 4,639 current slugs paired with their 2004 Latin texts, plus declension
rules: mr:0101-martina, mr:0101-bonfilius, mr:0101-concordius), no honorifics;
feast-type entries take the feast phrase (mr:0101-circumcisio-domini; octaves and
vigils follow the manual-override convention, octava-sancti-stephani-protomartyris,
like conversio-sancti-pauli); anonymous groups follow rule 8, number + class + place
(mr:0101-triginta-milites-romae). Continuation fragments that the OCR split
mid-elogium (95 cases) are merged before alignment, so every ID corresponds to a real
elogium.

**Caveats**: both the alignment and the deprecated status are mechanical drafts. Some
"deprecated" entries may in fact have a 2004 counterpart the matcher missed (heavily
rewritten texts); some matches may be wrong; rare 3rd-declension lemmas may be
imperfect. The committee review path is: confirm high-score matches, adjudicate the
low-score band, and re-classify false deprecations as merges into current IDs.

## Eulogy subjects (i18n)

Every canonical ID carries a **subject** — the saint, blessed or celebration the
eulogy is directed to, in nominative display form — stored per language in
[`i18n/`](../i18n/) (generated by `scripts/extract_subjects.py`). All locale files carry the identical complete key set (all 5,875 IDs), with empty
strings for untranslated subjects. The Latin file is fully filled (honorific from the
sanctity marker of the 2004 text, suppressed for feasts, pluralized for pairs and
groups; name from the slug; deprecated IDs from their historical-edition extraction).
The Italian (4,047 filled) and English (2,943 filled) files are partial mechanical
extractions from the 2004-edition texts, kept only when verified against the slug, and
await translator completion. Subject and slug are
tightly coupled and edition-independent.

## Known caveats for the committee

- Rare genitives with no safe rule remain in genitive form (single-occurrence Greek
  and Germanic names); they are still unique and stable, but not always nominative.
- Surname/epithet ambiguity for tokens in -i is resolved by corpus frequency; a
  1-in-corpus Latin epithet may remain unconverted while surnames are protected.
- The namespace prefix `mr:` and the anchor-edition choice are placeholders for
  committee decision; changing either is a mechanical rewrite.
