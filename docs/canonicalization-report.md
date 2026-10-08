# Draft canonical IDs — Martyrologium Romanum (CRMEDR working document)

Generated mechanically from the Latin texts (editio altera 2004, 'elaborazione' transcription,
corrected against the Vatican print where noted). **All IDs are drafts for committee review.**

## Scheme

`mr:MMDD-slug` — MMDD anchors the entry's placement in the editio altera 2004;
the slug is the Latin nominative lemma of the first-named subject, ASCII-folded,
lowercase, honorific-free (no sanctus/beatus). The day is part of the identity: `MMDD`
is the day an edition prints the eulogy. Each edition's position within the day (entry
number, asterisk, unnumbered) is a per-edition attribute, not part of the identity; a
eulogy printed on another day has its own ID there, linked by `same_eulogy` (#49).

Rules applied, in order:
1. Personal names extracted after the first sanctity marker (sancti/beatae/sanctorum...);
   genitive converted to nominative by declension rules + a curated irregular map.
2. Religious-name titles after a/de remain uninflected (teresia-a-iesu, ignatius-de-loyola).
3. Papal ordinals rendered as roman numerals (pius-x, clemens-i); non-papal regnal
   ordinals remain Latin adjectives (ludovicus-nonus).
4. Cognomento epithets appended (petrus-chrysologus, albertus-magnus).
5. Two named subjects: both joined (cosmas-et-damianus), the second by its full name
   (ioannes-fisher-et-thomas-more). Three or more, or explicit 'et sociorum' or other
   companions (*et decem martyrum*): first-named + et-socii (paulus-miki-et-socii).
6. Marian titles: maria + invocation (maria-de-lourdes, maria-de-guadalupe).
7. Christological/liturgical feasts: manual override slugs (see below).
8. Anonymous groups: [number-]class-<place in the genitive>, "the martyrs *of* X"
   (quadraginta-milites-sebastes, martyres-alexandriae); a group known by a name or a
   demonym takes that name in the nominative plural (martyres-scillitani,
   monachi-abrahamitae).
9. Same-slug collisions within a day: the day's lead keeps the bare slug; numbered
   entries take the place of death (or see, in the genitive) or an epithet; never a number
   (mr:0408-dionysius-2 became mr:0408-dionysius-corinthi, #59).

## Special identity decisions

**Feb 28/29**: the four leap-day elogia printed twice in both IT and LA editions carry
ONE identity each, anchored at 0229; the Feb 28 rows bear the same ID:
- mr:0229-hilarius (also at Feb 28, voce 4)
- mr:0229-oswaldus (also at Feb 28, voce 5)
- mr:0229-antonia-de-florentia (also at Feb 28, voce 6)
- mr:0229-augustus-chapdelaine (also at Feb 28, voce 7)

**Entries absent from the "with IDs" workbook** (both present in the parallel-texts
workbook, whose reviewer comments document their numbering across editions):
- mr:0104-abrunculus — entry 2* in the Latin print (its entry is now 2 in the registry),
  absent from the Italian (CEI) edition and from Mons. Barba's Word transcription
- mr:0104-emmanuel-gonzalez-garcia — entry 12* in the Latin print (entry 12 in the
  registry), numbered 11* in the Italian (CEI) edition (`editions` entry 11) and in Mons.
  Barba's Word transcription (Bl. M. González García,
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
mr:0323-rebecca-de-himlaya (11.), mr:0812-iacobus-do-mai-nam-et-socii (11., Nam Định martyrs),
mr:0821-iosephus-dang-dinh-vien (11., Hưng Yên), mr:1201-domnolus (5.), mr:1203-lucius (5., Chur),
mr:1212-simon-phan-dac-hoa (11., Phan Đắc Hòa).

**Slug correction**: the workbook ID mr:0206-paulus-mikus-et-socii is corrected on
extraction to mr:0206-paulus-miki-et-socii — surnames are not latinized unless an
already well-known Latin form exists (rule 5's example shows the intended form).

**Repaired source text**: the Word transcription's 3-20 v1 was truncated; the la cell was
restored from the print (Commemoratio sancti Archippi...). ID: mr:0320-archippus.

## Manual feast overrides (34)

- mr:0101-maria-dei-genetrix  (1/1 voce 1)
- mr:0103-nomen-iesu  (1/3 voce 1)
- mr:0106-epiphania-domini  (1/6 voce 1)
- mr:0125-conversio-pauli-apostoli  (1/25 voce 1)
- mr:0202-praesentatio-domini  (2/2 voce 1)
- mr:0217-septem-fundatores-servorum-mariae  (2/17 voce 1)
- mr:0222-cathedra-petri-apostoli  (2/22 voce 1)
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
- mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum  (11/18 voce 1)
- mr:1121-praesentatio-beatae-mariae-virginis  (11/21 voce 1)
- mr:1208-conceptio-immaculata-beatae-mariae-virginis  (12/8 voce 1)
- mr:1224-avi-iesu-christi  (12/24 voce 1)
- mr:1225-nativitas-domini  (12/25 voce 1)

## Anonymous groups — mechanical slugs, review recommended (39)

- mr:0114-monachi-raithi
  - *Incipit:* Commemorátio sanctórum monachórum, qui Raíthi et…
- mr:0205-plurimi-martyres-ponti
  - *Incipit:* In Ponto, commemorátio plurimórum sanctórum mártyrum…
- mr:0208-martyres-monachi-dii-constantinopolitani
  - *Incipit:* Commemorátio sanctórum mártyrum monachórum monastérii Dii…
- mr:0209-plurimi-martyres-alexandriae
  - *Incipit:* Item Alexandríæ, pássio plurimórum sanctórum mártyrum,…
- mr:0211-plurimi-martyres-numidiae
  - *Incipit:* Commemorátio plurimórum sanctórum mártyrum, qui in…
- mr:0212-martyres-abitinenses
  - *Incipit:* Carthágine, commemorátio sanctórum mártyrum Abitinénsium, qui,…
- mr:0219-monachi-martyres-palaestinae
  - *Incipit:* Commemorátio sanctórum monachórum et aliórum mártyrum,…
- mr:0220-quinque-martyres-tyri
  - *Incipit:* Commemorátio beatórum quinque mártyrum, qui, sub…
- mr:0228-presbyteri-diaconi-plurimi-alexandriae
  - *Incipit:* Commemorátio sanctórum presbyterórum, diaconórum et aliórum…
- mr:0306-quadraginta-duo-martyres-syriae
  - *Incipit:* In Sýria, pássio sanctórum quadragínta duórum…
- mr:0309-quadraginta-milites-sebastes
  - *Incipit:* Apud Sebástem in Arménia, pássio sanctórum…
- mr:0330-plurimi-martyres-constantinopolis
  - *Incipit:* Commemorátio sanctórum plurimórum mártyrum, qui Constantinópoli,…
- mr:0405-centum-undecim-viri-novem-mulieres-martyres
  - *Incipit:* Item, commemorátio centum úndecim virórum ac…
- mr:0405-martyres-regiarum
  - *Incipit:* Régiis in Mauretánia, pássio sanctórum mártyrum,…
- mr:0407-ducenti-milites-martyres-sinopes
  - *Incipit:* Sinópe in Ponto, sanctórum ducentórum mílitum…
- mr:0509-trecenti-decem-martyres-persidis
  - *Incipit:* In Pérside, sanctórum mártyrum trecentórum et…
- mr:0516-quadraginta-quattuor-monachi-palaestinae
  - *Incipit:* In Palæstína, pássio sanctórum quadragínta quáttuor…
- mr:0521-martyres-alexandriae
  - *Incipit:* Commemorátio sanctórum mártyrum utriúsque sexus, quos…
- mr:0523-martyres-cappadociae
  - *Incipit:* Commemorátio sanctórum mártyrum, qui in Cappadócia…
- mr:0523-martyres-mesopotamiae
  - *Incipit:* Item commemorátio sanctórum mártyrum, qui eódem…
- mr:0524-triginta-octo-martyres-philippopolis
  - *Incipit:* Commemorátio sanctórum trigínta et octo mártyrum,…
- mr:0708-monachi-abrahamitae
  - *Incipit:* Constantinópoli, pássio sanctórum monachórum Abrahamitárum, qui,…
- mr:0801-septem-fratres-martyres-antiochiae
  - *Incipit:* Commemorátio passiónis sanctórum septem fratrum mártyrum,…
- mr:0809-martyres-constantinopolis
  - *Incipit:* Constantinópoli, commemorátio sanctórum mártyrum, qui, cum…
- mr:0810-martyres-alexandriae
  - *Incipit:* Commemorátio sanctórum mártyrum, qui Alexandríæ in…
- mr:0814-octingenti-martyres-hydrunti
  - *Incipit:* Hydrúnti in Apúlia, beatórum fere octingentórum…
- mr:0830-sexaginta-martyres-coloniae-sufetanae
  - *Incipit:* Commemorátio sanctórum sexagínta mártyrum, qui, Colóniæ…
- mr:1005-martyres-trevirorum
  - *Incipit:* Tréviris in Gállia Bélgica, commemorátio sanctórum…
- mr:1010-daniel-et-socii
  - *Incipit:* Apud Septam in Mauritánia Tingitána, pássio…
- mr:1012-martyres-et-confessores-africae
  - *Incipit:* Commemorátio sanctórum mártyrum et fídei confessórum…
- mr:1021-virgines-coloniae-agrippinae
  - *Incipit:* Apud Colóniam Agrippínam in Germánia, commemorátio…
- mr:1113-arcadius-et-socii
  - *Incipit:* In Africa, commemorátio sanctórum mártyrum hispanórum…
- mr:1115-viginti-martyres-hipponis-regii
  - *Incipit:* Hippóne Régio in Numídia, sanctórum vigínti…
- mr:1119-quadraginta-martyres-heracleae
  - *Incipit:* Heracléæ in Thrácia, sanctárum mulíerum, vírginum…
- mr:1206-martyres-africae
  - *Incipit:* In Africa, commemorátio sanctórum mártyrum, témpore…
- mr:1216-plurimae-virgines-africa
  - *Incipit:* Commemorátio plurimárum sanctárum vírginum, quæ, in…
- mr:1217-quinquaginta-milites-eleutheropolis
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

- **mr:0610-marcus-antonius-durando** / **mr:1210-marcus-antonius-durando**: the Latin
  editio altera 2004 (and the English edition) place Bl. Marcantonio Durando at June 10
  (entry 9\*); the Italian (CEI) edition places him at December 10 (entry 9\*). The one
  eulogy has two IDs, each anchored to its own day: `mr:0610-…` (Latin print, English) and
  `mr:1210-…` (CEI), linked as `same_eulogy`. See "Per-edition placements".
- **mr:0712-proclus-et-hilarion**: entry 1 at July 12 in the CEI edition; absent from the
  Latin print, whose July 12 numbering begins at 2 with the gap left unrenumbered.
- **mr:0825-eusebius-et-socii**: entry 3 at August 25 in the CEI edition; absent from the
  Latin print, where the numbered entries begin at 3 (Genesius) after the two unnumbered
  memorias (Louis IX, Joseph Calasanz).
- **mr:0709-maria-a-iesu-crucifixo**: entry 11\* at July 9 in the CEI edition;
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

**Slug correction (applied, October 2026, #20)**: the workbook ID
mr:1130-stephanus-fanus (11/30) is corrected on extraction to mr:1130-cuthbertus-mayne.
The slug had been coined from the place, "Sancti Stephani Fanum" (Launceston), not from
the first-named subject, St Cuthbert Mayne; surnames are not latinized. The `la` and
`en` subjects, which had been derived from the bad slug, are corrected too. As with the
earlier slug fixes (#5) this is a rename, not a deprecation. No collision on the day;
the only other Cuthbert is mr:0320-cuthbertus.

**Slug corrections (applied, October 2026, #25)**: 24 more workbook IDs had been
coined from the saint named in the opening place (a monastery, convent, town or
district named after a saint, often a monastery of St Mary), not from the subject,
which is the first lowercase *sancti/beati* after the place. They were found by
comparing each slug with the saints named in its opening place, then with the
subject after any place named after a saint. Renamed (not deprecated), each in
`ID_CORRECTIONS`:

| Workbook ID | Corrected ID | Subject |
| --- | --- | --- |
| mr:0130-benedictus-de-maretiolo | mr:0130-columba-marmion | Bl. Columba Marmion |
| mr:0205-caesarius | mr:0205-sabas-iunior | St Sabas the Younger |
| mr:0212-cornelius | mr:0212-benedictus-anianensis | St Benedict of Aniane |
| mr:0320-sabas | mr:0320-viginti-monachi-palaestinae | the twenty monks of Mar Saba (rule 8) |
| mr:0330-iulianus | mr:0330-iulius-alvarez | St Julius Álvarez |
| mr:0406-maria | mr:0406-catharina-de-pallantia | Bl. Catherine of Pallanza |
| mr:0412-ioseph | mr:0412-david-uribe | St David Uribe |
| mr:0413-maria-de-capella | mr:0413-ida-boloniensis | Bl. Ida of Boulogne (another Ida is mr:0413-ida) |
| mr:0419-bertinus | mr:0419-bernardus-paenitens | Bl. Bernard the Penitent |
| mr:0426-isidorus-de-duenas | mr:0426-raphael-arnaiz-baron | Bl. Raphael Arnáiz Barón |
| mr:0502-gallus | mr:0502-wiborada | St Wiborada |
| mr:0508-maria-della-serra | mr:0508-angelus-de-massatio | Bl. Angelo of Massaccio |
| mr:0524-hyacinthus | mr:0524-ludovicus-zephyrinus-moreau | Bl. Louis-Zéphirin Moreau |
| mr:0526-papulus | mr:0526-berengarius | St Berengar |
| mr:0603-maria-de-cadossa | mr:0603-conus | St Conus |
| mr:0620-iacobus-fodiensi | mr:0620-ioannes-de-mateola | St John of Matera (printed *de Matéola*) |
| mr:0705-maria-de-terreto | mr:0705-thomas | St Thomas, abbot |
| mr:0726-benedictus | mr:0726-simeon | St Simeon of Polirone |
| mr:0823-philippus | mr:0823-antonius-de-hieracio | St Anthony of Gerace |
| mr:1114-maria | mr:1114-siardus | St Siard |
| mr:1114-maria-de-gualdo-mazocca | mr:1114-ioannes-de-tupharia | Bl. John of Tufara |
| mr:1205-petrus-de-aquara | mr:1205-lucidus | St Lucidus |
| mr:1210-nicolaus-de-viotorito | mr:1210-lucas-de-insula | St Luke, bishop of Isola |

mr:1126-bonaventura (from "in convéntu Sancti Bonaventúræ") is St Leonard of Port
Maurice, who already had a deprecated ID on the day, attested in 1749:
mr:1126-leonardus-a-portu-mauritio. As for Postel and Hildegard, that ID becomes
current and the deprecated entry is removed; the 1749 and 1914 texts already carry
it. The 2004 Latin prints *Leonárdi de Portu Maurítio*; the ID keeps the older
*a Portu Mauritio* so that one ID spans the three editions. mr:0526-franciscus-patrizus
(a latinized surname) is corrected to mr:0526-franciscus-patrizi.

The wrong 2004 IDs had also misled the alignment of the historical editions
(martyrology-api), which is corrected there: the 1749 and 1914 eulogies of St Photina
and companions (20 March) and the 1749 feast of St Philip Benizi (23 August) had been
aligned to mr:0320-sabas and mr:0823-philippus; the 1914 Pigmenius (24 March, "in the
time of Julian the Apostate") to mr:0330-iulianus. Three deprecated IDs are coined:
mr:0320-photina-et-socii (1749), mr:0823-philippus-benizi (1749) and mr:0324-pigmenius
(1914 English); the 1914 Philip Benizi (23 August) is aligned to mr:0822-philippus-benizi.

The subjects follow the 2004 texts, each language its own edition (the Latin and the
Italian sometimes differ in *sanctus/beatus*). The same review corrected subjects
that had been taken from the place too: 19 Latin honorifics (e.g. mr:0726-camilla-gentili,
"Sanctus Camilla" -> "Beata Camilla Gentili"; mr:0104-christiana-menabuoi, from "In
Sancta Cruce", is *beata*), 16 Latin honorifics of the wrong gender or number
("Sanctus Agnes", "Sanctus Scillitani"), 14 Italian subjects that were the place
("Santa Croce in Val d’Arno") and 4 English ones that named the place's saint.

**Slug corrections (applied, October 2026, #33)**: 34 slugs had been coined from a
Latin **genitive** instead of the subject's nominative lemma (rule 1), from a misread
byname, or from a truncated name. The 2004 Latin prints the subject in the genitive
(*beáti Notkéri Bálbuli*); declined Latin words carry a stress accent there, which the
scan used to tell them from modern surnames (Fatati, Régis, Sanchís), left as printed.
Ablatives inside religious names (*a Vírgine Perdolénti*) and the place-locative
disambiguators (mr:0213-stephanus-lugduni, mr:0403-ioannes-neapoli) are kept.
mr:0603-ioannes-vigesimi-iii follows the papal-ordinal form (mr:0110-gregorius-x);
mr:0727-dormientium-ephesi becomes a rule-8 group, mr:0727-septem-dormientes-ephesi;
in mr:1212-alexandrini-epimachi-et-alexander "Alexandrinorum" is "of Alexandria", not a
person. Renamed (not deprecated), each in `ID_CORRECTIONS`; the Latin subjects follow
the slugs.

| Workbook ID | Corrected ID |
| --- | --- |
| mr:0406-notkerus-balbuli | mr:0406-notkerus-balbulus |
| mr:0727-dormientium-ephesi | mr:0727-septem-dormientes-ephesi |
| mr:0413-carpus-et-thyatirensis | mr:0413-carpus-et-socii |
| mr:0724-bor-et-gleb | mr:0724-boris-et-gleb |
| mr:0110-petrus-urseoli | mr:0110-petrus-urseolus |
| mr:0125-arthematis | mr:0125-arthemas |
| mr:0129-gilda-sapientis | mr:0129-gilda-sapiens |
| mr:0226-pietatis-a-cruce-ortiz-real | mr:0226-pietas-a-cruce |
| mr:0307-paulus-simplicis | mr:0307-paulus-simplex |
| mr:0424-gulielmus-firmati | mr:0424-gulielmus-firmatus |
| mr:0425-pasicratis-et-valentio | mr:0425-pasicrates-et-valentio |
| mr:0426-paschasius-radberti | mr:0426-paschasius-radbertus |
| mr:0505-sacerdotis | mr:0505-sacerdos |
| mr:0522-humilitatis | mr:0522-humilitas |
| mr:0603-ioannes-vigesimi-iii | mr:0603-ioannes-xxiii |
| mr:0705-athanasius-hierosolymitani | mr:0705-athanasius-hierosolymitanus |
| mr:0712-ioannes-gualberti | mr:0712-ioannes-gualbertus |
| mr:0713-myropis | mr:0713-myrope |
| mr:0713-ludovicus-armandi-iosephus-adam | mr:0713-ludovicus-armandus-iosephus-adam-et-bartholomaeus-jarrige-de-la-morelie-de-biars |
| mr:0828-carolus-arnaldi-hanus | mr:0828-carolus-arnaldus-hanus |
| mr:0831-raymundus-nonnati | mr:0831-raymundus-nonnatus |
| mr:0904-caletricis | mr:0904-caletricus |
| mr:0911-sacerdotis | mr:0911-sacerdos |
| mr:0914-ioannes-chrysostomi | mr:0914-ioannes-chrysostomus |
| mr:0916-martinus-sacerdotis | mr:0916-martinus-sacerdos |
| mr:1115-caius-coreani | mr:1115-caius-coreanus |
| mr:1120-gregorius-decapolitani | mr:1120-gregorius-decapolitanus |
| mr:1128-papinianus-vitensis-et-mansuetus-urusitani | mr:1128-papinianus-vitensis-et-mansuetus-urusitanus |
| mr:1128-iacobus-piceni | mr:1128-iacobus-picenus |
| mr:1204-ioannes-damasceni | mr:1204-ioannes-damascenus |
| mr:1212-alexandrini-epimachi-et-alexander | mr:1212-epimachus-et-alexander |
| mr:0417-robertus-molismensi | mr:0417-robertus-molismensis |
| mr:0918-ferreolus-galliae-viennensi | mr:0918-ferreolus-viennensis |
| mr:0401-hugo-cisterciensi-bonae | mr:0401-hugo-bonaevallensis |

**Multi-subject, truncated and group slugs (applied, October 2026, #40)**: 236 slugs
renamed (not deprecated), each in `ID_CORRECTIONS`; the Latin, Italian and English
subjects follow the slugs.
- 110 eulogies of a pair (*sanctórum [mártyrum] X … et Y*) and 82 of three or more had
  kept only the first-named subject; they take `-et-<second>` or `-et-socii` (rule 5).
  A companion named only by relation (mr:0626-salvius, "and his disciple") gives no
  second name and is kept. mr:0823-laurentius was a place-lead slug ("in the cemetery of
  St Lawrence"); its subjects are Abundius and Irenaeus.
- 14 single-subject slugs were cut short at a letter the fold did not decompose — the
  Vietnamese Đ, or the apostrophe of a Korean name (mr:0309-petrus-ch, *Ch’oe*). The
  full name is kept, every word of a multi-word surname included; Đ folds to `d`, a
  parenthetical alternate name is dropped (mr:0821-iosephus-dang-dinh-vien, *(Niên)*).
  The same completion is applied to the first name of five multi-subject slugs above.
- 30 anonymous-group slugs follow rule 8 as revised: the place in the genitive
  (*Sebastem* → *sebastes*, *Carthagine* → the named group *martyres-abitinenses*),
  `martyres-` for a demonym group (mr:0717-scillitani → mr:0717-martyres-scillitani),
  and mr:0630-sancta-romana-ecclesia → mr:0630-protomartyres-sanctae-romanae-ecclesiae,
  whose subject is the protomartyrs, not the Church.

<details><summary>Workbook-to-corrected table (236)</summary>

| Previous ID | Corrected ID |
| --- | --- |
| mr:0108-theophilus | mr:0108-theophilus-et-helladius |
| mr:0109-agatha-yi | mr:0109-agatha-yi-et-teresia-kim |
| mr:0112-tigrius | mr:0112-tigrius-et-eutropius |
| mr:0113-gumesindus | mr:0113-gumesindus-et-servusdei |
| mr:0123-clemens | mr:0123-clemens-et-agathangelus |
| mr:0124-gulielmus-ireland | mr:0124-gulielmus-ireland-et-ioannes-grove |
| mr:0125-praeiectus | mr:0125-praeiectus-et-amarinus |
| mr:0129-sarbelius | mr:0129-sarbelius-et-bebaia |
| mr:0201-conorus-o-devany | mr:0201-conorus-o-devany-et-patricius-o-lougham |
| mr:0204-philea | mr:0204-philea-et-philoromus |
| mr:0206-dorothea | mr:0206-dorothea-et-theophilus |
| mr:0207-anselmus-polanco | mr:0207-anselmus-polanco-et-philippus-ripoll |
| mr:0207-iacobus-sales | mr:0207-iacobus-sales-et-gulielmus-saultemouche |
| mr:0214-cyrillus | mr:0214-cyrillus-et-methodius |
| mr:0225-aloysius-versiglia | mr:0225-aloysius-versiglia-et-callistus-caravario |
| mr:0303-marinus | mr:0303-marinus-et-asterius |
| mr:0309-petrus-ch | mr:0309-petrus-choe-hyong-et-ioannes-baptista-chon-chang-un |
| mr:0311-marcus-chong-ui-ba | mr:0311-marcus-chong-ui-bae-et-alexius-u-se-yong |
| mr:0313-rudericus | mr:0313-rudericus-et-salomon |
| mr:0316-hilarius | mr:0316-hilarius-et-tatianus |
| mr:0318-ioannes-thules | mr:0318-ioannes-thules-et-rogerius-wrenno |
| mr:0326-montanus | mr:0326-montanus-et-maxima |
| mr:0402-didacus-aloysius-de-san-vitores | mr:0402-didacus-aloysius-de-san-vitores-et-petrus-calungsod |
| mr:0403-robertus-middleton | mr:0403-robertus-middleton-et-thurstanus-hunt |
| mr:0404-agathopodus | mr:0404-agathopodus-et-theodulus |
| mr:0407-eduardus-oldcorne | mr:0407-eduardus-oldcorne-et-radulphus-ashley |
| mr:0417-petrus | mr:0417-petrus-et-hermogenes |
| mr:0420-franciscus-page | mr:0420-franciscus-page-et-robertus-watkinson |
| mr:0502-vindemialis | mr:0502-vindemialis-et-longinus |
| mr:0506-marianus | mr:0506-marianus-et-iacobus |
| mr:0519-ioannes-de-cetina | mr:0519-ioannes-de-cetina-et-petrus-de-duenas |
| mr:0522-petrus-ab-assumptione | mr:0522-petrus-ab-assumptione-et-ioannes-baptista-machado |
| mr:0526-ioannes | mr:0526-ioannes-doan-trinh-hoan-et-matthaeus-nguyen-van-phuong |
| mr:0527-barbara-kim | mr:0527-barbara-kim-et-barbara-yi |
| mr:0530-gulielmus-scott | mr:0530-gulielmus-scott-et-richardus-newport |
| mr:0531-robertus-thorpe | mr:0531-robertus-thorpe-et-thomas-watkinson |
| mr:0602-marcellinus | mr:0602-marcellinus-et-petrus |
| mr:0604-antonius-zawistowski | mr:0604-antonius-zawistowski-et-stanislaus-starowieyski |
| mr:0610-thomas-green | mr:0610-thomas-green-et-gualterius-pierson |
| mr:0615-petrus-snow | mr:0615-petrus-snow-et-radulphus-grimston |
| mr:0622-ioannes-fisher | mr:0622-ioannes-fisher-et-thomas-more |
| mr:0625-dominicus-henares | mr:0625-dominicus-henares-et-franciscus-do-minh-chieu |
| mr:0626-nicolaus-konrad | mr:0626-nicolaus-konrad-et-vladimirus-pryjma |
| mr:0629-maria-du-tianshi | mr:0629-maria-du-tianshi-et-magdalena-du-fengju |
| mr:0701-ioannes-baptista-duverneuil | mr:0701-ioannes-baptista-duverneuil-et-petrus-aredius-labrouhe-de-laborderie |
| mr:0707-antoninus-fantosati | mr:0707-antoninus-fantosati-et-iosephus-maria-gambaro |
| mr:0707-rogerius-dickinson | mr:0707-rogerius-dickinson-et-radulphus-milner |
| mr:0710-maria-gertrudis-a-sancta-sophia-de-ripert | mr:0710-maria-gertrudis-a-sancta-sophia-et-agnes-a-iesu |
| mr:0711-placidus | mr:0711-placidus-et-sigisbertus |
| mr:0713-ludovicus-armandus-iosephus-adam | mr:0713-ludovicus-armandus-iosephus-adam-et-bartholomaeus-jarrige-de-la-morelie-de-biars |
| mr:0716-andreas-de-soveral | mr:0716-andreas-de-soveral-et-dominicus-carvalho |
| mr:0716-ioannes-sugar | mr:0716-ioannes-sugar-et-robertus-grissold |
| mr:0716-lang-yangzhi | mr:0716-lang-yangzhi-et-paulus-lang-fu |
| mr:0716-nicolaus-savouret | mr:0716-nicolaus-savouret-et-claudius-beguignot |
| mr:0717-zoerardus | mr:0717-zoerardus-et-benedictus |
| mr:0719-elisabeth-qin-bianzhi | mr:0719-elisabeth-qin-bianzhi-et-simon-qin-chunfu |
| mr:0722-philippus-evans | mr:0722-philippus-evans-et-ioannes-lloyd |
| mr:0723-petrus-ruiz | mr:0723-petrus-ruiz-de-los-panos-et-iosephus-sala-pico |
| mr:0726-eduardus-thwing | mr:0726-eduardus-thwing-et-robertus-nutter |
| mr:0726-marcellus-gaucherius-labigne-de-reignefort | mr:0726-marcellus-gaucherius-labigne-de-reignefort-et-petrus-iosephus-le-groing-de-la-romagere |
| mr:0726-vincentius-pinilla | mr:0726-vincentius-pinilla-et-emmanuel-martin-sierra |
| mr:0728-emmanuel-segura | mr:0728-emmanuel-segura-et-david-carlos |
| mr:0729-lazarus | mr:0729-lazarus-et-maria |
| mr:0731-dionysius-vicente-ramos | mr:0731-dionysius-vicente-ramos-et-franciscus-remon-jativa |
| mr:0731-petrus | mr:0731-petrus-doan-cong-quy-et-emmanuel-phung |
| mr:0801-dominicus-nguyen-van-hanh | mr:0801-dominicus-nguyen-van-hanh-et-bernardus-vu-van-due |
| mr:0803-alphonsus-lopez-lopez | mr:0803-alphonsus-lopez-lopez-et-michael-remon-salvador |
| mr:0809-faustinus-oteiza | mr:0809-faustinus-oteiza-et-florentinus-felipe |
| mr:0810-franciscus-drzewiecki | mr:0810-franciscus-drzewiecki-et-eduardus-grzymala |
| mr:0812-florianus-stepniak | mr:0812-florianus-stepniak-et-iosephus-straszewski |
| mr:0813-patricius-o-healy | mr:0813-patricius-o-healy-et-connus-o-rourke |
| mr:0814-dominicus-ibanez-de-erquicia | mr:0814-dominicus-ibanez-de-erquicia-et-franciscus-shoyemon |
| mr:0817-iacobus-kyuhei-gorobioye-tomonaga | mr:0817-iacobus-kyuhei-gorobioye-tomonaga-et-michael-kurobioye |
| mr:0823-florentinus-perez-romero | mr:0823-florentinus-perez-romero-et-urbanus-gil-saez |
| mr:0823-laurentius | mr:0823-abundius-et-irenaeus |
| mr:0827-ioannes-baptista-de-souzy | mr:0827-ioannes-baptista-de-souzy-et-udalricus-guillaume |
| mr:0829-ioannes-de-perusia | mr:0829-ioannes-de-perusia-et-petrus-de-saxoferrato |
| mr:0830-didacus-ventaja-milan | mr:0830-didacus-ventaja-milan-et-emmanuel-medina-olmos |
| mr:0905-petrus-nguyen-van-tu | mr:0905-petrus-nguyen-van-tu-et-iosephus-hoang-luong-canh |
| mr:0907-festus | mr:0907-festus-et-desiderius |
| mr:0907-randulphus-corby | mr:0907-randulphus-corby-et-ioannes-duckett |
| mr:0915-emila | mr:0915-emila-et-ieremias |
| mr:0916-rogellus | mr:0916-rogellus-et-servusdei |
| mr:0921-franciscus-jaccard | mr:0921-franciscus-jaccard-et-thomas-tran-van-thien |
| mr:0921-vincentius-galbis-girones | mr:0921-vincentius-galbis-girones-et-emmanuel-torro-garcia |
| mr:0922-vincentius-pelufo-corts | mr:0922-vincentius-pelufo-corts-et-iosepha-moscardo-montalva |
| mr:0924-gulielmus-spenser | mr:0924-gulielmus-spenser-et-robertus-hardesty |
| mr:0927-iosephus-fenollosa-alcayna | mr:0927-iosephus-fenollosa-alcayna-et-fidelis-climent-sanches |
| mr:0929-paulus-bori-puig | mr:0929-paulus-bori-puig-et-vincentius-sales-genoves |
| mr:1002-franciscus-carceller | mr:1002-franciscus-carceller-et-isidorus-bover-oliver |
| mr:1010-eulampius | mr:1010-eulampius-et-eulampia |
| mr:1016-amandus | mr:1016-amandus-et-iunianus |
| mr:1016-anicetus-koplinski | mr:1016-anicetus-koplinski-et-iosephus-jankowski |
| mr:1019-lucas-alphonsus-gorda | mr:1019-lucas-alphonsus-gorda-et-matthaeus-kohioye |
| mr:1022-philippus | mr:1022-philippus-et-hermes |
| mr:1023-ioannes-perside | mr:1023-ioannes-et-iacobus |
| mr:1025-martyrius | mr:1025-martyrius-et-marcianus |
| mr:1103-valentinus | mr:1103-valentinus-et-hilarius |
| mr:1104-nicandrus | mr:1104-nicandrus-et-hermes |
| mr:1110-narses | mr:1110-narses-et-iosephus |
| mr:1113-florentius | mr:1113-florentius-et-amantius |
| mr:1115-guria | mr:1115-guria-et-samona |
| mr:1115-marinus | mr:1115-marinus-et-anianus |
| mr:1119-elisaeus-garcia | mr:1119-elisaeus-garcia-et-alexander-planas-sauri |
| mr:1126-hugo-taylor | mr:1126-hugo-taylor-et-marmaducus-bowes |
| mr:1126-thomas | mr:1126-thomas-dinh-viet-du-et-dominicus-nguyen-van-xuyen |
| mr:1129-dionysius-a-nativitate-berthelot | mr:1129-dionysius-a-nativitate-et-redemptus-a-cruce |
| mr:1210-antonius-martin-hernandez | mr:1210-antonius-martin-hernandez-et-augustinus-garcia-calvo |
| mr:1210-edmundus-gennings | mr:1210-edmundus-gennings-et-swithinus-wells |
| mr:1229-henricus-ioannes-requena | mr:1229-henricus-ioannes-requena-et-iosephus-perpina-nacher |
| mr:0121-fructuosus | mr:0121-fructuosus-et-socii |
| mr:0128-agatha-lin-zhao | mr:0128-agatha-lin-zhao-et-socii |
| mr:0201-paulus-hong-yong-ju | mr:0201-paulus-hong-yong-ju-et-socii |
| mr:0215-isicus | mr:0215-isicus-et-socii |
| mr:0304-christophorus-bales | mr:0304-christophorus-bales-et-socii |
| mr:0307-simeon-berneux | mr:0307-simeon-berneux-et-socii |
| mr:0312-mygdo | mr:0312-mygdo-et-socii |
| mr:0313-macedonius | mr:0313-macedonius-et-socii |
| mr:0323-victorianus | mr:0323-victorianus-et-socii |
| mr:0330-antonius-daveluy | mr:0330-antonius-daveluy-et-socii |
| mr:0401-venantius | mr:0401-venantius-et-socii |
| mr:0407-theodorus | mr:0407-theodorus-et-socii |
| mr:0416-optatus | mr:0416-optatus-et-socii |
| mr:0417-donnanus | mr:0417-donnanus-et-socii |
| mr:0417-elias | mr:0417-elias-et-socii |
| mr:0428-paulus-pham-khac-khoan | mr:0428-paulus-pham-khac-khoan-et-socii |
| mr:0430-amator | mr:0430-amator-et-socii |
| mr:0501-torquatus | mr:0501-torquatus-et-socii |
| mr:0524-augustinus-yi-kwang-hon | mr:0524-augustinus-yi-kwang-hon-et-socii |
| mr:0529-gulielmus-arnaud | mr:0529-gulielmus-arnaud-et-socii |
| mr:0529-sisinnius | mr:0529-sisinnius-et-socii |
| mr:0601-alphonsus-navarrete | mr:0601-alphonsus-navarrete-et-socii |
| mr:0601-ischyrion | mr:0601-ischyrion-et-socii |
| mr:0602-pothinus | mr:0602-pothinus-et-socii |
| mr:0607-petrus | mr:0607-petrus-et-socii |
| mr:0614-anastasius | mr:0614-anastasius-et-socii |
| mr:0616-aureus | mr:0616-aureus-et-socii |
| mr:0616-dominicus-nguyen | mr:0616-dominicus-nguyen-et-socii |
| mr:0629-paulus-wu-juan | mr:0629-paulus-wu-juan-et-socii |
| mr:0702-liberatus | mr:0702-liberatus-et-socii |
| mr:0704-gulielmus-andleby | mr:0704-gulielmus-andleby-et-socii |
| mr:0704-ioannes-cornelius | mr:0704-ioannes-cornelius-et-socii |
| mr:0713-alexander | mr:0713-alexander-et-socii |
| mr:0715-catulinus | mr:0715-catulinus-et-socii |
| mr:0715-philippus | mr:0715-philippus-et-socii |
| mr:0716-reinildis | mr:0716-reinildis-et-socii |
| mr:0720-maria-zhao-guozhus | mr:0720-maria-zhao-guozhi-et-socii |
| mr:0722-anna-wang | mr:0722-anna-wang-et-socii |
| mr:0725-fridericus-rubio-alvarez | mr:0725-fridericus-rubio-alvarez-et-socii |
| mr:0725-petrus-a-corde-redondo | mr:0725-petrus-a-corde-et-socii |
| mr:0727-georgius | mr:0727-georgius-et-socii |
| mr:0729-ludovicus-bertran | mr:0729-ludovicus-bertran-et-socii |
| mr:0730-iosephus-maria-muro-sanmiguel | mr:0730-iosephus-maria-muro-sanmiguel-et-socii |
| mr:0801-maria-stella-a-sanctissimo-sacramento-mardosewicz | mr:0801-maria-stella-a-sanctissimo-sacramento-et-socii |
| mr:0804-iosephus-batalla-parramon | mr:0804-iosephus-batalla-parramon-et-socii |
| mr:0807-martinus-a-sancto-felice-woodcock | mr:0807-ioannes-woodcock-et-socii |
| mr:0810-claudius-iosephus-jouffret-de-bonnefont | mr:0810-claudius-iosephus-jouffret-de-bonnefont-et-socii |
| mr:0812-iacobus | mr:0812-iacobus-do-mai-nam-et-socii |
| mr:0812-porcarius | mr:0812-porcarius-et-socii |
| mr:0815-aloysius-batis-sainz | mr:0815-aloysius-batis-sainz-et-socii |
| mr:0816-simon-bokusai-kyota | mr:0816-simon-bokusai-kyota-et-socii |
| mr:0821-bassa | mr:0821-bassa-et-socii |
| mr:0821-bernardus | mr:0821-bernardus-et-socii |
| mr:0823-constantinus-carbonell-sempere | mr:0823-constantinus-carbonell-sempere-et-socii |
| mr:0825-michael-carvalho | mr:0825-michael-carvalho-et-socii |
| mr:0827-marcellinus | mr:0827-marcellinus-et-socii |
| mr:0901-petrus-rivera | mr:0901-petrus-rivera-et-socii |
| mr:0907-marcus-crisini | mr:0907-marcus-crisini-et-socii |
| mr:0907-thomas-tsuji | mr:0907-thomas-tsuji-et-socii |
| mr:0908-thomas-palaser | mr:0908-thomas-palaser-et-socii |
| mr:0911-gaspar-koteda | mr:0911-gaspar-koteda-et-socii |
| mr:0912-apollinaris-franco | mr:0912-apollinaris-franco-et-socii |
| mr:0916-laureanus-ferrer-cardet | mr:0916-laureanus-ferrer-cardet-et-socii |
| mr:0921-laurentius-imbert | mr:0921-laurentius-imbert-et-socii |
| mr:0923-sophia-ximenez-ximenez | mr:0923-sophia-ximenez-ximenez-et-socii |
| mr:0925-ioannes-petrus-bengoa-aranguren | mr:0925-ioannes-petrus-bengoa-aranguren-et-socii |
| mr:0928-ioannes-shozaburo | mr:0928-ioannes-shozaburo-et-socii |
| mr:1010-septem-martyres-presbyteri-septam | mr:1010-daniel-et-socii |
| mr:1018-proculus | mr:1018-proculus-et-socii |
| mr:1025-maria-teresia-ferragud-roig | mr:1025-maria-teresia-ferragud-roig-et-socii |
| mr:1028-franciscus-serrano | mr:1028-franciscus-serrano-et-socii |
| mr:1101-petrus-paulus-navarro | mr:1101-petrus-paulus-navarro-et-socii |
| mr:1108-iosephus-nguyen | mr:1108-iosephus-nguyen-dinh-nghi-et-socii |
| mr:1113-martyres-africa | mr:1113-arcadius-et-socii |
| mr:1115-hugo-faringdon | mr:1115-hugo-faringdon-et-socii |
| mr:1115-richardus-whiting | mr:1115-richardus-whiting-et-socii |
| mr:1118-leonardus-kimura | mr:1118-leonardus-kimura-et-socii |
| mr:1122-salvator-lilli | mr:1122-salvator-lilli-et-socii |
| mr:1124-petrus-dumoulin-borie | mr:1124-petrus-dumoulin-borie-et-socii |
| mr:1204-franciscus-galvez | mr:1204-franciscus-galvez-et-socii |
| mr:1209-richardus | mr:1209-richardus-de-los-rios-fabregat-et-socii |
| mr:1222-chaeremon | mr:1222-chaeremon-et-socii |
| mr:0509-iosephus | mr:0509-iosephus-do-quang-hien |
| mr:0522-michael-ho | mr:0522-michael-ho-dinh-hy |
| mr:0525-petrus | mr:0525-petrus-doan-van-van |
| mr:0603-petrus | mr:0603-petrus-dong |
| mr:0617-petrus | mr:0617-petrus-da |
| mr:0630-vincentius | mr:0630-vincentius-do-yen |
| mr:0703-iosephus-nguyen | mr:0703-iosephus-nguyen-dinh-uyen |
| mr:0718-dominicus-nicolaus | mr:0718-dominicus-nicolaus-dinh-dat |
| mr:0821-iosephus | mr:0821-iosephus-dang-dinh-vien |
| mr:0912-franciscus-ch | mr:0912-franciscus-choe-kyong-hwan |
| mr:1021-petrus-yu-tae-ch | mr:1021-petrus-yu-tae-chol |
| mr:1024-iosephus-le | mr:1024-iosephus-le-dang-thi |
| mr:1028-ioannes | mr:1028-ioannes-dat |
| mr:1212-simon-phan | mr:1212-simon-phan-dac-hoa |
| mr:0212-martyres-carthagine | mr:0212-martyres-abitinenses |
| mr:0219-monachi-martyres-palaestina | mr:0219-monachi-martyres-palaestinae |
| mr:0306-quadraginta-duo-martyres-syria | mr:0306-quadraginta-duo-martyres-syriae |
| mr:0309-quadraginta-milites-sebastem | mr:0309-quadraginta-milites-sebastes |
| mr:0320-viginti-monachi-palaestina | mr:0320-viginti-monachi-palaestinae |
| mr:0321-alexandrini | mr:0321-martyres-alexandrini |
| mr:0330-plurimi-martyres-constantinopoli | mr:0330-plurimi-martyres-constantinopolis |
| mr:0405-martyres-regiis | mr:0405-martyres-regiarum |
| mr:0407-ducenti-milites-martyres-sinope | mr:0407-ducenti-milites-martyres-sinopes |
| mr:0509-martyres-trecenti-decem-perside | mr:0509-trecenti-decem-martyres-persidis |
| mr:0516-quadraginta-quattuor-monachi-palaestina | mr:0516-quadraginta-quattuor-monachi-palaestinae |
| mr:0523-martyres-cappadocia | mr:0523-martyres-cappadociae |
| mr:0524-triginta-octo-martyres-philippopoli | mr:0524-triginta-octo-martyres-philippopolis |
| mr:0630-sancta-romana-ecclesia | mr:0630-protomartyres-sanctae-romanae-ecclesiae |
| mr:0708-monachi-constantinopoli | mr:0708-monachi-abrahamitae |
| mr:0717-scillitani | mr:0717-martyres-scillitani |
| mr:0722-massilitani | mr:0722-martyres-massilitani |
| mr:0809-martyres-constantinopoli | mr:0809-martyres-constantinopolis |
| mr:0818-massa-candida | mr:0818-martyres-massae-candidae |
| mr:1005-martyres-treviris | mr:1005-martyres-trevirorum |
| mr:1012-martyres-confessores-quattuor-sexaginta-africa | mr:1012-martyres-et-confessores-africae |
| mr:1017-volitani | mr:1017-martyres-volitani |
| mr:1021-virgines-coloniam-agrippinam | mr:1021-virgines-coloniae-agrippinae |
| mr:1115-viginti-martyres-hippone-regio | mr:1115-viginti-martyres-hipponis-regii |
| mr:1119-mulieres-virgines-viduae-quadraginta-martyres-heracleae | mr:1119-quadraginta-martyres-heracleae |
| mr:1206-martyres-africa | mr:1206-martyres-africae |
| mr:1217-quinquaginta-milites-eleutheropoli | mr:1217-quinquaginta-milites-eleutheropolis |
| mr:0523-martyres-mesopotamia | mr:0523-martyres-mesopotamiae |
| mr:0205-plurimi-martyres-ponto | mr:0205-plurimi-martyres-ponti |
| mr:0211-plurimi-martyres-numidia | mr:0211-plurimi-martyres-numidiae |

</details>

## Per-edition placements

An entry's main placement (`month`, `day`, `entry`, `asterisk`) follows the Latin editio
altera 2004 print. Where another edition differs, the entry carries an `editions` object
keyed by edition ID (`martyrologium_romanum_2004`, `martyrologium_romanum_2004_it_IT`,
`martyrologium_romanum_2004_en_unofficial`), holding only the differences: `entry` (that
edition's own number), `asterisk` (that edition's own marker) and `absent: true` (the
edition does not print the eulogy at all) and `unnumbered` (that edition prints it
without a number). `same_eulogy` lists the IDs of the same
eulogy printed on a different day in another edition (a symmetric link).

Four days are numbered differently in the Latin print and in the CEI edition (56 current
entries carry `editions`):

- **4 January**: Abrunculus is 2 (absent from the CEI), so Gregorius is 3 (CEI 2) ...
  Emmanuel González García 12 (CEI 11).
- **10 June**: Durando is 9 (absent from the CEI at this day; the CEI has it at 10
  December), so Eduardus Poppe is 10 (CEI 9).
- **25 August**: Eusebius et socii is 3 in the CEI only (absent from the Latin print and
  the English edition), so Genesius is 3 (CEI 4) ... Aloysius Urbano Lanaspa 13 (CEI 14).
- **10 December**: Durando is 9 in the CEI only (absent from the Latin print and the
  English edition), so Gundisalvus Vines Masip is 9 (CEI 10) and Antonius Martin Hernandez
  et Augustinus Garcia Calvo 10 (CEI 11).

26 existing IDs changed entry number on those days (the only new ID is
mr:1210-marcus-antonius-durando). The 29 asterisk discrepancies between the Latin print
and the CEI (see the sweep above) are recorded as CEI overrides (`editions` ->
`martyrologium_romanum_2004_it_IT` -> `asterisk`); the explanatory notes remain on the
entries.

**Deprecated IDs merged into current IDs (applied, October 2026, #45)**: 21 eulogies
of the 1749 edition had a coined deprecated ID although they are the same eulogy as a
current ID on the same day, whose slug extends the deprecated one: the alignment had
not matched them (mr:0211-maria is the apparition at Lourdes, mr:0211-maria-de-lourdes;
the digitized 1749 copy is a later printing, which already has it). As for
mr:1126-leonardus-a-portu-mauritio (#25), each deprecated entry is removed and the
1749 and 1914 texts are re-keyed to the current ID (martyrology-api); the current ID and
its subjects are unchanged. Kept: mr:0827-rufus-et-carpophorus (a separate eulogy of two
martyrs) and same-day homonyms (mr:0124-timotheus, mr:0513-maria, mr:0629-maria,
mr:0917-franciscus).

| Removed deprecated ID | Current ID |
| --- | --- |
| mr:0211-maria | mr:0211-maria-de-lourdes |
| mr:0731-ignatius | mr:0731-ignatius-de-loyola |
| mr:1015-teresia | mr:1015-teresia-a-iesu |
| mr:1110-leo | mr:1110-leo-i |
| mr:0419-leo | mr:0419-leo-ix |
| mr:1115-albertus | mr:1115-albertus-magnus |
| mr:1116-gertrudis | mr:1116-gertrudis-magna |
| mr:0323-turibius | mr:0323-turibius-de-mogrovejo |
| mr:0517-paschalis | mr:0517-paschalis-baylon |
| mr:0406-petrus | mr:0406-petrus-veronensis |
| mr:0924-gerardus | mr:0924-gerardus-sagredo |
| mr:0930-gregorius | mr:0930-gregorius-illuminator |
| mr:0312-theophanes | mr:0312-theophanes-chronographus |
| mr:0107-canutus | mr:0107-canutus-lavard |
| mr:1126-silvester | mr:1126-silvester-gozzolini |
| mr:0220-eucherius-aurelianensis | mr:0220-eucherius |
| mr:0228-presbyteri-diaconi | mr:0228-presbyteri-diaconi-plurimi-alexandriae |
| mr:0615-vitus-et-socii | mr:0615-vitus |
| mr:0917-petrus-de-arbues-caesaraugustae | mr:0917-petrus-de-arbues |
| mr:1018-paulus-a-cruce-romae | mr:1018-paulus-a-cruce |
| mr:1018-petrus-de-alcantara-arenis | mr:1018-petrus-de-alcantara |

**February 20 (applied, October 2026, #47)**: the historical editions had several
eulogies of the day under the wrong ID.
- St Eleutherius of Tournai, the current mr:0220-eleutherius, is renamed
  mr:0220-eleutherius-tornaci (in `ID_CORRECTIONS`), told apart by his see from the
  other Eleutherii of the day. In the 1749 edition his eulogy (*Tornaci, in Galliis,
  sancti Eleutherii, Episcopi et Confessoris*) had been run into the end of the
  mr:0220-eucherius text by the OCR; it is split out and keyed to him, as is the 1914
  text.
- *Constantinopoli sancti Eleutherii, Episcopi et Martyris* (1749, 1914), which the
  alignment had keyed to the Tournai eulogy, is a different saint with no 2004
  eulogy: a new deprecated mr:0220-eleutherius-constantinopoli.
- *In Perside natalis sancti Eleutherii, Episcopi, et aliorum centum viginti octo*
  (1749) had the truncated deprecated ID mr:0220-eleutherius-pe; it becomes
  mr:0220-eleutherius-et-socii (rule 5). The 1749 print names Eleutherius on this day,
  so the eulogy keeps its own ID; its registry `note` records that it is probably the
  eulogy of Sadoth and 128 companions (mr:0218-sadoth-et-socii), as the 1914 edition,
  which names Sadoth, has it.
- The 1749 and 1914 eulogy keyed mr:0220-tyrannion commemorates the countless martyrs
  of Tyre under Veturius, naming Tyrannio among the bishops who encouraged them: it is
  re-keyed to mr:0220-quinque-martyres-tyri. mr:0220-tyrannion (Antioch) keeps its
  slug: its honorific is singular, and Zenobius, named with him, has his own eulogy
  (mr:1029-zenobius).

**The Ursulines of Orange, July 9 (applied, October 2026, #77)**: the Latin 2004 prints
*beatárum Melániæ et Maríæ Annæ Magdalénæ de Guilhermier atque Maríæ Annæ Margarítæ ab
Angelis de Rocher*. The other Orange eulogies give the baptismal name in brackets after the
religious name (*Agnétis a Iesu (Sýlviæ) de Romillon*), and "et" stands where that bracket
would be: Melania is the religious name of Maria Anna Magdalena de Guilhermier (Sister
Sainte-Mélanie), and the eulogy commemorates two martyrs, guillotined at Orange on 9 July 1794.
The workbook ID, mr:0709-melania-et-maria-anna-magdalena-de-guilhermier, had taken the one
woman for the pair and left out the second. It becomes
mr:0709-melania-et-maria-anna-margarita-ab-angelis, named by the religious names like
mr:0710-maria-gertrudis-a-sancta-sophia-et-agnes-a-iesu (`ID_CORRECTIONS`, kept identical to
CatholicOS/martyrology-texts). Edition notes record the error in the Latin, the unofficial
English ("Mélanie and Mary Anne Magdalen") and the CEI ("Melania Marianna, Maddalena de
Guilhermier").

**Eulogies printed on another day (applied, October 2026, #49)**: the day is part of the
identity. The 1749 and 1914 alignments had keyed 331 eulogies (211 distinct, read one by
one against the 2004 text) to an ID of another day. Each now has an ID of the day it is
printed on:
- 131 are the same eulogy as the 2004 one, moved: a new deprecated ID on the historical
  day with the 2004 slug (mr:1220-ammon-et-socii for mr:0601-ammon-et-socii), linked to it
  both ways by `same_eulogy`; 6 more 1914 eulogies link the same way to a deprecated 1749
  ID of another day.
- 9 are another saint who has a 2004 eulogy on another day (Stephen Harding, John Francis
  Regis, John of Lycopolis, the martyrs of Ceuta, ...): a new deprecated ID with the
  saint's own slug, linked to that eulogy.
- 54 are another saint, a namesake the aligner had matched (Liberata of Como had been
  keyed to mr:0427-liberalis), with no 2004 eulogy: a new deprecated ID, no link.
- 9 are an ID of the same day (Anselm of Lucca, Hilary of Arles, Landelin, Nilus, Albert
  of Trapani, Hesperus and Zoe, Pope Eutychian, Philip Benizi's 1749 ID, and the 1914
  Christmas proclamation, which the OCR had split in two): re-keyed, no new ID.
- Two garbled 1749 IDs are re-minted. mr:0523-martyru is Quinctianus, Lucius and Julian of
  Africa, whom the 1914 alignment had keyed to the different current eulogy
  mr:0523-lucius-et-socii (Lucius, Montanus and companions of Carthage): both editions now
  key mr:0523-quinctianus-et-socii. mr:0504-triginta-martyres-inmetallo is the thirty-nine
  martyrs of the mines of Phaeno, a eulogy of its own in 1749 and 1914 after that of Silvanus
  of Gaza, with whom the 2004 edition commemorates them (mr:0504-silvanus-et-socii): both
  editions now key mr:0504-triginta-novem-martyres-phaenonis (rule 8), with a note.

A slug already taken on the day takes a place or byname (mr:0111-salvius-ambiani,
mr:0524-vincentius-portuensis, mr:0926-eusebius-papa). The deprecated entries carry their
links in `data/deprecated_ids.json`; `extract_registry.py` records each link back on the
counterpart and validates every link (another day, both ways). The full table is in #49.

**More deprecated IDs merged into current IDs (applied, October 2026, #49)**: 42 more
1749 eulogies had a coined deprecated ID although they are the same eulogy as a current ID
on the same day, whose slug the deprecated one extends or declines (mr:0413-ursi for
mr:0413-ursus, Ursus of Ravenna; mr:0525-leo-in for mr:0525-leo). They are the merges the
deprecated-ID sweep's audit had accepted, each read again against the 2004 text. As in #45,
each deprecated entry is removed and the 1749 text (and the 1914 one, where printed) is
re-keyed to the current ID. The 1749 texts of mr:0518-ericus and mr:0528-iustus still carry
the following eulogies of their day, run in by the OCR.

| Removed deprecated ID | Current ID |
| --- | --- |
| mr:0110-paulus-thebaide | mr:0110-paulus |
| mr:0114-datius-mediolani | mr:0114-datius |
| mr:0115-maurus-in | mr:0115-maurus |
| mr:0116-marcellus-primus-romae | mr:0116-marcellus-i |
| mr:0222-petrus-damianus-cardinalis | mr:0222-petrus-damianus |
| mr:0312-petrus-ibidem | mr:0312-petrus |
| mr:0413-ursi | mr:0413-ursus |
| mr:0422-caji | mr:0422-caius |
| mr:0425-marcus-evangelista-hic | mr:0425-marcus-evangelista |
| mr:0510-job-propheta | mr:0510-iob |
| mr:0518-ericus-upsali | mr:0518-ericus |
| mr:0519-ivo-lohaneti | mr:0519-ivo |
| mr:0525-leo-in | mr:0525-leo |
| mr:0528-justus | mr:0528-iustus |
| mr:0629-syri | mr:0629-syrus |
| mr:0720-paulus-cordubae | mr:0720-paulus |
| mr:0729-olavus-norvegia | mr:0729-olavus |
| mr:0729-lupi | mr:0729-lupus |
| mr:0730-ursi | mr:0730-ursus |
| mr:0731-fabius-caesareae | mr:0731-fabius |
| mr:0816-rochus-montem | mr:0816-rochus |
| mr:0819-magnus-anagniae | mr:0819-magnus |
| mr:0823-luppus-item | mr:0823-luppus |
| mr:0825-ludovicus-noni | mr:0825-ludovicus-nonus |
| mr:0827-rufi | mr:0827-rufus |
| mr:0829-sebbus-anglia | mr:0829-sebbus |
| mr:0901-lupi | mr:0901-lupus |
| mr:0903-gregorius-magnus-item | mr:0903-gregorius-magnus |
| mr:0908-petrus-claver-carthagine | mr:0908-petrus-claver |
| mr:0923-lini | mr:0923-linus |
| mr:0927-caji | mr:0927-caius |
| mr:1006-fideus-agenni | mr:1006-fideus |
| mr:1007-marcus-romae | mr:1007-marcus |
| mr:1016-lullus-moguntiae | mr:1016-lullus |
| mr:1022-donatus-scotus-tuscia | mr:1022-donatus-scotus |
| mr:1026-fulcus-papiae | mr:1026-fulcus |
| mr:1102-justus | mr:1102-iustus |
| mr:1110-justus | mr:1110-iustus |
| mr:1209-syri | mr:1209-syrus |
| mr:1209-petrus-fourier-graji | mr:1209-petrus-fourier |
| mr:1216-ado-viennae | mr:1216-ado |
| mr:1221-petrus-canisius-friburgi | mr:1221-petrus-canisius |

**Historical keys read against their texts: rubrics and misaligned keys (applied, October
2026, #51)**: every eulogy of the 1749 and 1914 editions was read against the key it carries
(1,225 findings, reviewed in martyrology-frontend's `/review` by class). This first part
applies two classes:
- **Rubrics.** Five keys held a rubric, an instruction to the reader, not a eulogy (the
  1749 *Quod sequitur, legitur in tono Lectionis consueto* of Christmas, the leap-year
  notes of 23 February in both editions, the 1749 note on All Souls falling on a Sunday,
  which had been keyed mr:1102-domninus). They move to the day's `rubricae` in the edition
  files, each placed after the eulogy it follows (or at the head of the day); a key that
  held only a rubric is dropped (mr:1225-quodsequitur-legitur-in and
  mr:0223-matthia-apostolus are removed). The 1914 Milburga keeps its eulogy; only the
  leap-year rubric appended to it moves.
- **Misaligned keys.** 172 placements carried the key of another eulogy, usually a saint
  named in the text but not its subject (Septiminus, Januarius and Felix keyed by their
  parents mr:0828-bonifatius-et-thecla; Macrina keyed by her teacher
  mr:0114-gregorius-thaumaturgus; the Transfiguration keyed mr:0806-dominicus), or a
  namesake of another see (Marcellus of Trier on the 2004 Marcellus of Chalon). Each is
  re-keyed: 28 placements to the current ID of the eulogy, the rest to a deprecated ID of
  the day, 77 of them new. A 2004 eulogy whose historical text had been keyed elsewhere
  gets its own text back (mr:1101-caesarius, mr:1205-crispina-thagorensis,
  mr:1210-eulalia). One 1749 key holding two eulogies is split (mr:0311-constantinus), and
  mr:0224-cyprianus is re-minted mr:0224-montanus-et-socii.
- **Same eulogy, subject changed by 2004.** Where the 2004 edition kept a historical eulogy
  but changed its subject (it reduced a group: Cyrinus, Primus and Theogenes to Theogenes;
  it corrected the saint or the place: Euphrasius in Africa to Euphrasius of Clermont,
  Maximus of Apamea to Maximus of Cumae), the historical eulogy keeps an ID of its own and
  is linked to the current one by `same_eulogy`, on the same day. `validate_editions` now
  accepts a same-day link when one side is deprecated; between two current IDs it is still
  an error. The 1914 English, which fuses Ingenuinus and Albuinus of Brixen, is linked to
  both.

Eleven deprecated IDs no longer key any eulogy and are removed (among them
mr:0114-gregorius-thaumaturgus, mr:0828-bonifatius-et-thecla with its wrong link to
mr:0830-bonifatius-et-thecla, mr:1101-caesarius-tarracinae, mr:1205-crispina,
mr:1210-eulalia-emeritae, mr:1025-milites-quadraginta-sex). The positions (`entry`) of the
deprecated IDs follow the re-keyed days. The run-in eulogies, the garbled slugs and the
remaining same-eulogy links and notes follow in later parts of #51.

**Run-in eulogies split (applied, October 2026, #51 part 2)**: the OCR of both historical
editions had lost the paragraph break between eulogies, so one key held two or more of them
(406 keys: 336 in 1749, 70 in 1914; mr:1224-vigilia-nativitatis-domini held the vigil and
John of Kęty, mr:0424-maria-a-sancta-euphrasia held Bova and Doda, Euphrasia
Pelletier and the Conversion of Augustine). Each key is cut where the next eulogy begins,
and each part takes the ID of its eulogy: the ID the other edition already gives it, a
current ID of the day, or a new deprecated ID (28). Where the key's own eulogy is
not the first part (mr:0316-abraham opened with Patricius), the first part takes its own ID
and the key stays with its eulogy. The
texts are only cut, never changed: every day of both editions still reads the same
characters. A split part that links to a eulogy of another day carries the link
(mr:0429-robertus-molismensis to mr:0417-robertus-molismensis). mr:1031-alfonsus-rodriguez-coadjutoris
no longer keys a eulogy (its text is the current mr:1031-alphonsus-rodriguez) and is removed.

**Garbled deprecated slugs re-minted (applied, October 2026, #51 part 3)**: 388 deprecated
IDs (415 reviewed cards) coined from OCR fragments, function words, genitives, truncations or *j* spellings
take the rule-built slug of their eulogy's subject, read against the text: mr:0418-a →
mr:0418-apollonius, mr:1118-eodem-die-sanc → mr:1118-oriculus-et-socii,
mr:0314-in-africa-s → mr:0314-petrus-et-aphrodisius, mr:0107-julianus → mr:0107-iulianus.
The rules of #52 and #56 apply to them: prophets and apostles keep the epithet
(mr:0704-osee-et-aggaeus-prophetae, mr:0224-matthias-apostolus), and feast phrases drop the
honorific (mr:1129-vigilia-andreae-apostoli, mr:0102-octava-stephani-protomartyris) except in
a church's name (mr:0801-dedicatio-sancti-petri-apostoli-ad-vincula). Thirteen garbled IDs
are the same eulogy as an ID parts 1–2 coined or a current one, and merge into it
(mr:0302-octoginta-martyres-campania into mr:0302-octoginta-martyres-campaniae,
mr:0813-maximus-abbatus into mr:0813-maximus-confessor). Two re-minted slugs that had already
named another eulogy take the place of death instead (rule 9): mr:1022-philippus-firmi,
mr:1110-leo-milleduni. A eulogy that is the same as one of another day carries its
`same_eulogy` link (79 new links). mr:0922-iraidis is retired (the 1914 key of the same
eulogy, mr:0922-irais-et-socii, remains). The Latin subjects follow the new slugs.

**Same-eulogy IDs merged and linked (applied, October 2026, #51 part 4)**: 51 deprecated IDs
key a eulogy that already has an ID of the same day, under another spelling or a garbled
slug, and merge into it (mr:0110-willhelmus into mr:0110-gulielmus, mr:0806-dominicus-bononiae
into mr:0806-dominicus, mr:1101-festivitas-omnium-sanctorum-quam into mr:1101-omnes-sancti);
the IDs merged into keep their subjects. 46 `same_eulogy` links are added, among them the
renamed celebrations of the same day (mr:0101-circumcisio-domini to mr:0101-maria-dei-genetrix)
and eulogies whose subject the editio altera changed (mr:0510-quartus-et-quinctus to
mr:0510-iv-et-v). mr:0220-sadoth-et-socii (1914) keeps its ID, as mr:0220-eleutherius-et-socii
(1749) keeps the name it prints (#47), and the two are linked. Four deprecated IDs whose
counterpart is uncertain carry a note instead (mr:0123-agathangelus).

**Links and notes (applied, October 2026, #51 part 5)**: the last set of the audit links
historical eulogies to the eulogy they continue on another day or under another subject, and
records the errors of the sources as curator notes. An error of one edition's text is a note on
that edition only, in the new `edition_notes` field (`EDITION_NOTES` for current IDs): most are
errors of the unofficial 1914 English against the 1749 Latin (Brixia rendered Brixen at
mr:0127-angela-merici, Domitian for Diocletian at mr:0824-tatio, Pettau rendered Poitiers at
mr:1102-victorinus), two concern the 1749 print (a dropped line at mr:0821-privatus). Remarks on
the eulogy itself stay in `note` (`ENTRY_NOTES`): Candidus and Candida at mr:1003-candida. Three Latin subjects are corrected (Sancta Fides,
Sancta Marina, Sanctus Ioannes Therestus).

**The Italian 2004 against the Latin 2004 (October 2026)**: every eulogy of the Italian (CEI)
edition was read against the Latin print. The discrepancies of substance found with high
confidence are curator notes on the edition that errs, published for review: on the Italian
(Holsatia rendered Alsazia at mr:0217-evermodus, Vasconia rendered Guascogna at
mr:0223-raphaela-de-villalonga-ybarra, Christ "seduto" for "stantem" at mr:1226-stephanus) or,
twice, on the Latin (sub Iacobo rege Primo at mr:0829-richardus-herst; the misprint dístulit for
diffúdit at mr:0612-laurentius-maria-a-sancto-francisco-xaverio, in `data/misprints.json`). The
Italian's rank of a feast for the patrons of Italy and of Europe (Festa for Memoria) is its own
calendar, not an error. The findings of lower confidence await review.

**The unofficial English 2004 against the Latin 2004 (October 2026)**: the same reading of the
unofficial English, with the Italian as a second witness. Its high-confidence errors are curator
notes on the English: "rebuilt" for aedificare, Gallia Lugdunensis rendered "Lyon France",
look-alike places (Pontoise rendered Pont-Sainte-Maxence, Senlis rendered Autun), senses reversed
(mr:1022-abercius, mr:0720-aurelius), misreadings ("confessed" for confossa at
mr:0706-maria-goretti, "twice" from albis at mr:1028-genesius). Faults of the digitized copy
rather than of the translation (footnote markers left in the text, an encoding slip of "d",
broken words, run-in eulogies) are corrected in the texts, not noted.

**Current IDs renamed (applied, October 2026, #52)**: 27 current slugs, in all four
repositories (`ID_CORRECTIONS` keeps them on regeneration):
- Five misnamed their eulogy: mr:0905-v → mr:0905-quintus (truncated);
  mr:0809-laurentius → mr:0809-romanus (the slug had taken the cemetery's name, *in
  coemeterio sancti Laurentii*; the eulogy is St Romanus, so the 1914 deprecated
  mr:0809-romanus, the same eulogy, merges into it); mr:0629-petrus-et-paulus-simon →
  mr:0629-petrus-et-paulus (*Simon* opens the next sentence; -apostoli since #56); mr:1028-fidel →
  mr:1028-fidelis and mr:0424-fidel-de-sigmaringa → mr:0424-fidelis-de-sigmaringa (the
  genitive stem for the nominative).
- **Prophets** keep the word in the slug, `-propheta` (`-prophetae` for two or more), so that
  they are told apart at a glance, with the nominative lemma: the writing prophets
  (mr:1017-osea → mr:1017-osee-propheta, mr:0921-iona → mr:0921-ionas-propheta,
  mr:1218-malachia → mr:1218-malachias-propheta, ...), Elias, Elisaeus, Samuel and Moyses,
  Agabus of the New Testament, mr:1229-david-rex-et-propheta (*regis et prophetae*) and
  mr:0203-simeon-et-anna-prophetissa (only Anna is called *prophetissa*). The Latin subject
  follows ("Sanctus Amos Propheta"). Deprecated prophet IDs follow the same rule in #51.

**Apostles and feast phrases (applied, October 2026, #56)**: as for the prophets, the
apostles keep the epithet in the slug, `-apostolus` (`-apostoli` for two), in the nominative:
the twelve, Matthias, and Paul, whom the Martyrology calls *Apostolus*
(mr:0514-matthias-apostolus, mr:1028-simon-et-iudas-apostoli,
mr:0629-petrus-et-paulus-apostoli). A feast phrase keeps the print's epithet in the
genitive, but, like every other slug, drops the honorific *sancti/sanctae/sanctorum*:
mr:0125-conversio-pauli-apostoli, mr:0222-cathedra-petri-apostoli,
mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum. The honorific stays where it is
part of a name: a church's (mr:0805-dedicatio-basilicae-sanctae-mariae), the Holy Cross
(mr:0914-exaltatio-sanctae-crucis), All Saints (*omnium sanctorum*). The Latin subject keeps
the printed form ("Cathedra Sancti Petri Apostoli"). Thirteen current IDs are renamed;
the deprecated feast and apostle IDs follow in #51.
The two evangelists who were not apostles keep their epithet the same way (#59):
mr:0425-marcus-evangelista, mr:1018-lucas-evangelista. The 1749 and 1914 translation of St Mark,
coined as a person (mr:0131-marcus-evangelista), becomes the feast phrase
mr:0131-translatio-marci-evangelistae. mr:0116-marcellus-primus becomes mr:0116-marcellus-i: papal
ordinals are roman numerals (rule 3). The last numeric disambiguator, mr:0408-dionysius-2, becomes
mr:0408-dionysius-corinthi (rule 9). In a feast naming several saints, only the first-named keeps
the epithet, so as not to lengthen the slug (mr:0509-translatio-andreae-apostoli-lucae-et-timothei).

**One name form per saint (applied, October 2026, #63)**: an ID names the saint the way they are
conventionally known, in one form: the religious name, with its title or place left uninflected
(rule 2; mr:0923-pius-de-pietrelcina, mr:0809-teresia-benedicta-a-cruce, mr:0808-maria-a-cruce), or
the given name and surname (mr:0730-leopoldus-mandic), never a mix of the two. When a surname is
used, no place is needed unless ambiguity remains. Surnames that contain *de*, *la* or *y* stay
whole (Galvão de França, Jarrige de la Morélie). 153 current IDs are renamed after a reviewed table
(85 candidates already used one form and keep theirs); their Latin subjects follow.

## Country-code corrections (September 2026)

`country` is the ISO 3166-1 alpha-2 code of the modern country of the place of the
elogium: the place-lead when there is one, otherwise the place of death. When the
printed text names the wrong modern country, the actual location wins. A review of
the elogia against their codes (issue #8) found **34 wrong codes**, now corrected
on extraction via `COUNTRY_CORRECTIONS` in `scripts/extract_registry.py`. Most
errors come from a homonymous place resolved to the wrong country: Guadalajara
(Jalisco vs. Castile), Eger (Cheb in Bohemia vs. Hungary), Nizza Monferrato vs.
Nice, and Catalan Montserrat coded `MS` (the British overseas territory). Four
corrections go against the printed text: mr:0504-florianus → AT (Lorch/Enns; the
text says "nell'odierna Germania"), mr:0304-casimirus → BY (Grodno; the text says
"in Lituania"), mr:0603-morandus → FR (Altkirch in Alsace) and mr:0827-gebhardus →
DE (Petershausen, Konstanz); the last two texts say "odierna Svizzera". Two entries
are left as they are: mr:1011-philippus stays `PS` (Caesarea Maritima), because
the workbook uses `PS` for the whole Holy Land (90 current entries) and changing
one entry would break that convention. mr:0814-arnulphus stays `BE` (Oudenburg),
although the text says "Altenburg nelle Fiandre, ora in Germania".

## Typology (September 2026)

Each current entry carries `typology`: **what the date of the elogium marks**.
Liturgical rank (*sollemnitas / festum / memoria*) is a different axis and is not
recorded here. Values: `dies_natalis` (the day of death or martyrdom, or the fallback when the
text states no other event),
`depositio` (burial), `translatio` (moving of relics), `inventio` (finding of
relics), `dedicatio` (dedication of a church or altar, including a saint's feast kept on
the anniversary of the dedication of a church in their honour, "in die
dedicationis"), `ordinatio` (episcopal
ordination), `celebratio` (the date is fixed by a liturgical celebration, not by
an event: feasts of the Lord and of Mary, the Chair of Peter, the Holy Cross,
the Angels, All Saints, and saints' memorials placed away from their death day)
and `commemoratio` (a commemoration with no event behind the date).

Tags are derived from the Latin editio altera 2004 by
`scripts/extract_typology.py` into `data/typology.json`. The first rule that
applies wins: hand overrides (`TYPOLOGY_OVERRIDES`); a dedication day stated in
the text ("in die dedicationis", "die anniversaria dedicationis"); off-day memorials, resolved
from the "cuius memoria … agitur" cross-references on the dies natalis; the
explicit `FEAST_IDS`; the first marker word in the lead of the elogium (before
the first relative pronoun that follows the subject's honorific, and not directly
after an honorific, where it is a name, nor after *postridie / pridie*, where it
names a neighbouring day's event); otherwise `dies_natalis`, the unmarked convention of the 2004 edition.
`docs/typology-report.md` lists every tag other than `dies_natalis` with the rule
that produced it.

Counts: dies_natalis 4,163, commemoratio 323, depositio 80, celebratio 60,
dedicatio 6, translatio 5, ordinatio 2, inventio 0. Deprecated entries carry no
typology yet. Memorials whose text doesn't say what their date marks keep
`dies_natalis` (e.g. mr:0319-ioseph, mr:0703-thomas-apostolus, mr:0726-ioachim-et-anna,
mr:0827-monica), pending committee review.

## Places (September 2026)

Current entries may carry `places`: the places the elogium states, each quoted
exactly as printed in the Latin editio altera 2004 (`la`) and given a role:
`death`, `burial`, `translation`, `dedication`, `cult` (where the saint is
venerated or commemorated), `birth`, `ministry` (see or field of work). Place
designations are factual and are the one piece of elogium text the repository
quotes.

The **opening place** is extracted by `scripts/extract_places.py`: the text before
the first lowercase honorific or marker word (the print capitalizes a saint inside
a place name, "in monasterio Sancti N.", but not the subject's honorific), without
a trailing "eodem die et anno". Its role follows `typology` (dies_natalis → death,
depositio → burial, translatio/inventio → translation, dedicatio → dedication,
ordinatio → ministry, celebratio/commemoratio → cult). A leading *Item* is dropped;
*Ibidem* and a bare *Item* take the place of the nearest earlier entry of the same
day, named in `via`. "Item commemoratio …" means "also, the commemoration of", so
it has no opening place.

**Body places** (birth, see, burial or death elsewhere) are hand-curated in
`data/places_curated.json`; `docs/places-report.md` lists the candidate entries
whose text holds a role cue. A later step resolves each distinct place to a
Wikidata item and a modern country (#12).

Each place may also carry `it`: the same place designation quoted from the Italian
(CEI) edition, which often gives the modern name and country ("A Ramosch in Rezia,
nel territorio dell'odierna Svizzera") — a hint for resolving the modern place, not
a verified fact (see the country-code corrections above). The Latin decides whether
a place exists; a bare Latin back-reference takes its root's `it`. In the Italian
phrase a comma segment is kept only when it is a locative or a modern-country
hint, and a leading *Sempre / Ancora* ("also") is dropped.

An opening place is cut at a comma that starts a relative clause (*quod, quam,
quo, qui, quae*), a reign (*sub N. imperatore*) or a time phrase (*in eadem
persecutione*, "… post annis"), since only the place designation is quoted.

A place named after a saint can open the elogium with a capitalized honorific
("Sancti Trudonis Fani in Brabantia" = Sint-Truiden, "Sancti Iacobi in Chilia" =
Santiago): when the first word after the first comma is a lowercase honorific or
marker ("…, transitus sancti N."), the text before that comma is the place, not a
drop-cap memorial. In the Italian phrase a naming clause ("chiamata poi Saint
Albans") is kept, as its Latin counterpart is ("postea ab eo Oswestria nuncupato").

Counts: 4,266 entries with places (4,265 opening places and 1 curated), 3 unresolved
back-references (two *Ibidem* after a memorial whose place is stated only in its
body, and one bare *Item* after an "Item commemoratio" entry), 548 curation
candidates; 4,262 places with an Italian phrase.

**Misprints in the 2004 prints (verified)**, recorded in `data/misprints.json` for
footnoting when the texts are displayed; place extraction treats each as the word
intended:
- Latin editio altera, September 27, entry 11\* (mr:0927-francisca-xaveria-fenollosa-alcayna):
  "betárum mártyrum" for *beatárum* (the subjects are women), verified on the page
  image and in its OCR layer.
- Latin editio altera and Italian (CEI) edition, October 4, entry 8\*
  (mr:1004-alaphridus-pellicer-munoz), also inside the quoted place designation
  (`places[].la` and `places[].it` keep the printed form): "Bellrreguart" for
  *Bellreguart* in the Latin (the Spanish name) and for *Bellreguard* in the Italian
  (the Valencian, official name, as in the English translation); the CEI edition
  copied the Latin typo.
- Italian (CEI) edition, October 13 (mr:1013-comganus): "desposizione" for
  *deposizione*.
- Italian (CEI) edition, October 14 (mr:1014-venantius): "comemorazione" for
  *commemorazione*.
- Italian (CEI) edition, also inside quoted place designations (`places[].it` keeps
  the printed form):
  - March 5 (mr:0305-phoca): "nell’odiena" for *nell’odierna*;
  - July 4 (mr:0704-ioannes-cornelius-et-socii): "un Inghilterra" for *in Inghilterra*;
  - August 7, entry 13\* (mr:0807-ioannes-woodcock-et-socii): "Inghiltera" for
    *Inghilterra*;
  - September 6 (mr:0906-bertrandus-de-garrigues): "Mel" for *Nel*;
  - September 17 (mr:0917-ioannes-ventura-solsona): "vicno" for *vicino*;
  - September 22 (mr:0922-mauritius-et-socii): "nell territorio" for *nel territorio*;
  - October 7 (mr:1007-ioannes-hunot): "prospicente" for *prospiciente*.

A record holds the misprinted word, or the shortest phrase of up to three words that
makes it unique in the text ("un Inghilterra"); it occurs exactly once there, as whole
words.

**Duplicated entries (verified)**, recorded under `duplicated_entries` in the same
file: an edition prints a whole eulogy a second time on another day. The copy has no
identity of its own and is left out of the texts and the registry; the record names
the eulogy, the edition, the day of the copy and the numbered entry it precedes.
- Italian (CEI) edition, April 6 (p. 305): the drop-cap eulogy of St Vincent Ferrer
  (mr:0405-vincentius-ferrer, April 5) is repeated word for word as an unnumbered
  header before entry 1. April 6 is numbered from 1 as usual, so its numbering is
  unaffected.

### Gazetteer (October 2026)

Each distinct place designation (the `la` of `data/places.json`) is resolved once
in `data/gazetteer.json` to the most specific place that has a stable Wikidata
item, usually the settlement or territory: *Romæ apud sanctum Petrum* resolves to
Rome; a monastery resolves to its own item when Wikidata has one. Each entry has
the QID, the item's label and the place's modern country (ISO 3166-1 alpha-2), with
two conventions: the whole Holy Land is `PS`, as in the registry's own `country`, and
a dependent territory with its own code takes it (Réunion `RE`, Guam `GU`, Puerto
Rico `PR`). Reconciling it with each entry's `country` is a later step.

A place is `auto` only when exactly one Wikidata candidate passes every rule:
its Italian label or alias is the head toponym of every Italian phrase of the
place; a Latin label or alias matches a nominative of the Latin head word, or its
Latin Place Names ID (P9314) slug is that word's form; it has one current country (P17), which agrees with every
modern country the Italian names and every region it states; and it is a place
(P31 through P279* to settlement, administrative entity, monastery, church,
archaeological site, island, mountain, region, cave, castle or country). When no
Italian phrase of the place names a region or country, the item must be in Italy
(the CEI edition names none for Italian places), unless it is itself a country;
this keeps foreign namesakes out (Ragusa in Sicily is not Dubrovnik). A stated
region with coordinates must lie within 500 km of the place (Hadrianopolis in
Paphlagonia is not Edirne).
`FORCE_REVIEW` in `scripts/build_gazetteer.py` lists places that pass every rule
but are known to be wrong because the Italian and Wikidata agree on another place
(*In Cornúbia Armóricæ* is Cornouaille in Brittany, not Cornwall). Every other place
goes to the review change-set `data/gazetteer_review.json` and is decided in
martyrology-frontend (`reviewed`, or `unresolved` with a note). Places awaiting
review have no key.

Where the printed Italian explicitly names the wrong modern country ("nell'odierna
X", "oggi in X", "ora in X"), the actual location wins and the entry records the
printed claim in `text_says`, with the Italian phrase it comes from (e.g.
Lorch/Enns, "nell'odierna Germania", is in Austria). It is derived from the
phrases and the place's country, not chosen. A bare "in Siria" or "in Armenia" is
not such a claim, since it may name the ancient region: for Antioch three phrases
say "oggi in Turchia" and one says only "in Siria", and nothing is recorded.

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
aligned against this registry (July 2026): of its 2,842 elogia (after merging OCR-split
continuation fragments), 1,495 matched a current ID on the same calendar day and 128 on
a different day (saints repositioned by the post-conciliar reform — e.g. Telesphorus
Jan 5 → Jan 2, Cosmas & Damian Sep 27 → Sep 26), using name-stem and text-similarity
evidence with per-match method and score recorded in the edition's `alignment.json`.

The remaining **1,219 elogia with no identified counterpart in the editio altera 2004
received coined canonical IDs with `deprecated: true`**, listed in
`data/deprecated_ids.json` and merged into the registry. A subsequent alignment of
the public-domain **1914 unofficial English edition** coined a further **225**
deprecated IDs (`attested_in: martyrologium_romanum_1914_en_unofficial`). The
**1630 (Urban VIII) edition**, Baronius's annotated Vatican printing, was then
transcribed from a two-pass proofread TEI (October 2026) and aligned Latin-to-Latin
against the IDs of each day (its 1749 and 2004 texts, or the subject name for IDs
attested only in the 1914 English; an ID's name must be in the text): of its 2,812
elogia, 2,770 matched an ID of the same day and 42 were settled by reviewed overrides —
spelling variants and other names of the same subject the name check rejects (the 1630
*Lucinius* of Angers under the 1914-attested `mr:0213-licinius`, now linked to
`mr:1101-licinius`; *Peregrinus* under `mr:0613-cetheus`, *Dominica* under
`mr:0706-cyriaca`, *Margarita* under `mr:0720-marina`). **6 of these IDs are new
deprecated IDs** (`attested_in: martyrologium_romanum_1630`): eulogies that 1630 prints
on another day than any other edition (`mr:0105-domnio`, `mr:0714-henricus`,
`mr:0816-hyacinthus`, `mr:0820-stephanus`, `mr:0824-vigilia-bartholomaei-apostoli`,
`mr:0825-bartholomaeus-apostolus`), each with its twins' slug and linked by `same_eulogy`.
After later corrections (#25, #44, #45, #47, #49, #51, #52, #56) the registry holds **6,256** entries (`entry_count` =
`current_count` + `deprecated_count`) — **4,640 current + 1,616 deprecated**. Their `MMDD` anchors the placement in the
edition named by `attested_in`. The Latin subject for every ID (current and
deprecated) lives in `i18n/la.json`, the single source of truth for subjects;
each deprecated entry additionally carries a `country` (ISO 3166-1 alpha-2 of the
modern country of the elogium's place, or `null`), inferred from its elogium as
for current entries.

Coined slugs follow the registry's own rules: **nominative lemma** of the first-named
subject (genitives converted via an empirical genitive→nominative dictionary mined
from the 4,639 current slugs paired with their 2004 Latin texts, plus declension
rules: mr:0101-martina, mr:0101-bonfilius, mr:0101-concordius), no honorifics;
feast-type entries take the feast phrase (mr:0101-circumcisio-domini; octaves and
vigils follow the manual-override convention, honorific-free since #51/#56,
octava-stephani-protomartyris, like conversio-pauli-apostoli); **genuinely anonymous** groups follow rule 8, number +
class + place (mr:0101-triginta-milites-romae, mr:1103-martyres-caesaraugustae for the
"innumerable Martyrs" of Saragossa). Continuation fragments that the OCR split
mid-elogium are merged before alignment, so every ID corresponds to a real elogium.

**Group eulogies — first-named subject (July 2026 correction).** An early coining pass
mis-slugged multi-martyr eulogies with the *place* name (e.g. `mr:0103-martyres-cilicia`
for what is actually "Zosimus and Athanasius"), because the extractor stopped at the
intervening genitive class-word (*Martyrum*, *fratrum*) before reaching the names. These
were rebuilt to the registry's own convention — the first-named subject in nominative
lemma, with `-et-<second>` for a named pair and `-et-socii` for three or more
(`mr:0103-zosimus-et-athanasius`, `mr:0102-argeus-et-socii`). Of the 271 affected
entries, **17 already existed as current 2004 IDs** (the same saints, sometimes shifted
a few days by the reform) and were de-coined to those IDs; **233 became correctly-slugged
deprecations**; **21 are genuinely anonymous** ("plurimorum … Martyrum", numbered legions)
and keep a `martyres-<place>` slug. Two non-martyr entries swept in by the buggy lead
token were also corrected: the Christmas Proclamation (mis-slugged `martyres-anno`) was
consolidated under `mr:1225-nativitas-domini`, and St Sacerdos of Limoges under
`mr:0504-sacerdos` / `mr:0912-sacerdos`.

**Caveats**: both the alignment and the deprecated status are mechanical drafts. Some
"deprecated" entries may still have a 2004 counterpart the matcher missed (heavily
rewritten texts); some cross-day matches may be wrong; rare 3rd-declension lemmas may be
imperfect. The committee review path is: confirm high-score matches, adjudicate the
low-score band, and re-classify any remaining false deprecations as merges into current IDs.

## Eulogy subjects (i18n)

Every canonical ID carries a **subject** — the saint, blessed or celebration the
eulogy is directed to, in nominative display form — stored per language in
[`i18n/`](../i18n/) (generated by `scripts/extract_subjects.py`). All locale files carry the identical complete key set (all 6,256 IDs), with empty
strings for untranslated subjects. The Latin file is fully filled (honorific from the
sanctity marker of the 2004 text, suppressed for feasts, pluralized for pairs and
groups; name from the slug; deprecated IDs from their historical-edition extraction).
The Italian (4,825 filled) and English (6,158 filled) files are partial extractions
from the 2004-edition texts (English also drawing deprecated subjects from the aligned
1914 edition), kept only when verified against the slug, and await translator
completion. Subject and slug are
tightly coupled and edition-independent.

**Complete vernacular subjects (October 2026, #61).** Many English and Italian subjects had kept only the bare name
("Saint Paul" for Paul of the Cross, "Saint Gregory" for Gregory of Nyssa, "Saint Peter" for the Chair of Peter).
In a reviewed pass, 415 labels were completed with what tells the subject apart: a byname or place ("Saint Gregory of
Nyssa"), a papal ordinal ("Saint Pius V"), a feast's own name ("The Chair of Saint Peter the Apostle"), and the
epithets the IDs now carry ("Saint Amos the Prophet", "Saint Thomas the Apostle", "Saint Mark the Evangelist"; in
Italian "Sant’Amos Profeta"). English labels use the conventional English names of the prophets (Hosea, Haggai, not
Osee, Aggaeus). Two curator notes record where the unofficial English text errs: "the Youth" for Theophilus the
Younger, and "Leo III the Isaurian" for Leo VI in the eulogy of Anthony Cauleas.

**Italian subject labels (October 2026, #75).** 537 Italian labels are corrected. Every `-et-socii` eulogy now
follows the Latin "Sancti N. et socii": plural honorific, the first-named subject, "e compagni" ("e compagne" for
women), with no count ("e dodici compagni") and no second name ("Santi Caritone e compagni"); 181 of the 297 labels
change, 166 of which had lost the "e compagni". A descriptor before a name is dropped ("Santi martiri Vittorino" -> "Santi Vittorino"),
except in anonymous groups ("Santi martiri Scillitani"). Names cut at a particle are completed ("San Luigi Maria
Grignion de Montfort", not "… Grignion de"), as are surnames the slug carries ("Beata Maria Teresa Fasce"), but a
religious-name label does not gain the surname the slug leaves out (rule of one name form). The CEI prints a stress
mark on the names it Italianizes (Argéo, Teógene, Sant’Ágabo): it is not their spelling and is removed (Argeo);
final accents (Gesù, Natività) and the accents of names left untranslated (García, Brébeuf, Nguyễn), which the Latin
text prints the same way, are kept. Also corrected: 16 pair labels that had lost their second name ("Santi Cornelio
e Cipriano"), 16 Vietnamese names garbled in an earlier copy of the CEI text ("Nguyñên" -> "Nguyễn"), and 9 labels
taken from the wrong words (mr:0302-agnes "Santa Chiara nel monastero da lei" -> "Sant’Agnese"). `extract_subjects.py`
now runs a name on through surname particles, skips a bracketed baptismal name and a leading descriptor, and
normalizes each Italian label with `it_label`.

**Review of the Italian and English subjects (October 2026, #31).** The extraction
had taken the first saint named anywhere in the text when it fell within its first 60
characters, which is usually a saint in the opening place, a church or an order ("San
Paolo sulla via Ostiense", "Saint Augustine" from "Order of Saint Augustine"). It also
missed the elided "sant’Eutizio" and let lowercase words pass as names ("una santa
vita"). Three detectors (the mention aligned with the Latin subject, the first mention
after the opening place, and honorifics that contradict the text) flagged 346 IDs;
each was read against its 2004 text, and 180 subjects were corrected (99 Italian, 81
English, after settling a few conventions): e.g. mr:0628-irenaeus "San Girolamo" ->
"Sant’Ireneo", mr:0724-bor-et-gleb "Saint Sigolena" -> "Saints Boris and Gleb". Each
language follows its own edition's honorific; names are as printed, nominative, without
titles; groups take "e compagni/e compagne" and "and companions"; English feasts keep
their leading "The". `extract_subjects.py` now prefers the mention that names the slug,
then the one aligned with the Latin subject, skips Italian honorifics capitalized
mid-text, and no longer has the 60-character escape; on the reviewed IDs it gets the
right person for 294 Italian and 277 English subjects (163 and 203 before). A full
rerun still overwrites curated values, so its output is diffed, not committed as is.

## Known caveats for the committee

- Rare genitives with no safe rule remain in genitive form (single-occurrence Greek
  and Germanic names); they are still unique and stable, but not always nominative.
- Surname/epithet ambiguity for tokens in -i is resolved by corpus frequency; a
  1-in-corpus Latin epithet may remain unconverted while surnames are protected.
- The namespace prefix `mr:` and the anchor-edition choice are placeholders for
  committee decision; changing either is a mechanical rewrite.
