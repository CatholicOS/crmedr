#!/usr/bin/env python3
"""Extract the CRMDR canonical ID registry from the private digitization workbook.

The workbook ("Roman Martyrology LA IT EN with IDs.xlsx") contains the full
Latin, Italian and English texts of the eulogies of the Roman Martyrology
(editio altera 2004). Those texts are copyrighted and are NOT extracted here:
this script reads only the non-copyrightable structural metadata — the
canonical ID, calendar placement (month/day/entry), the asterisk marker, and
the country associated with the place of the elogium — and writes:

  data/martyrology_ids.json   machine-readable registry
  registry/MM-<month>.md      human-readable per-month tables

Usage:
  python3 extract_registry.py /path/to/"Roman Martyrology LA IT EN with IDs.xlsx" [repo_root]

Requires: openpyxl
"""

import json
import sys
from pathlib import Path

from extract_places import ROLE_OF_TYPOLOGY
from extract_typology import RECOVERY

MONTH_SHEETS = [
    "GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO",
    "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE",
]
MONTH_NAMES_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# IDs in the workbook that violate the canonicalization rules and are
# corrected on extraction. Surnames are not latinized unless an already
# well-known Latin form exists: "Miki" is a Japanese surname with no such form.
ID_CORRECTIONS = {
    "mr:0206-paulus-mikus-et-socii": "mr:0206-paulus-miki-et-socii",
    # The elogium's first-named subject is San Guido, abbot; "Domninus" comes
    # from the place name (Burgi Sancti Domnini, Borgo San Donnino, today
    # Fidenza). Rule 1: the slug is the first-named subject.
    "mr:0331-domninus": "mr:0331-guido",
    # Polish ł/Ł (U+0142/U+0141) is a precomposed letter, not base l + a
    # combining stroke, so NFKD normalization leaves it intact and the
    # diacritic-folding step that produced the workbook slugs dropped it to a
    # blank, splitting the surname (paw-owski). The standard ASCII
    # transliteration is a plain l (Pawłowski -> pawlowski). The folding logic
    # is fixed in extract_subjects.py; these entries correct the slugs the
    # buggy fold already baked into the workbook.
    "mr:0109-iosephus-paw-owski-et-casimirus-grelewskus": "mr:0109-iosephus-pawlowski-et-casimirus-grelewskus",
    "mr:0219-iosephus-zap-ata": "mr:0219-iosephus-zaplata",
    "mr:0308-vincentius-kad-ubek": "mr:0308-vincentius-kadlubek",
    "mr:0331-natalia-tu-asiewicz": "mr:0331-natalia-tulasiewicz",
    "mr:0719-achilles-pucha-a-et-hermannus-stepien": "mr:0719-achilles-puchala-et-hermannus-stepien",
    "mr:0731-michael-ozieb-owski": "mr:0731-michael-ozieblowski",
    "mr:0908-ladislaus-b-adzinski": "mr:0908-ladislaus-bladzinski",
    "mr:1014-stanislaus-mysakowski-et-franciscus-ros-aniec": "mr:1014-stanislaus-mysakowski-et-franciscus-roslaniec",
    "mr:1216-honoratus-de-bia-a-podlaska-kazminsky": "mr:1216-florentius-kazminsky",
    "mr:1219-maria-eva-de-providentia-noiszewska-et-maria-martha-de-iesu-wo-owsk": "mr:1219-maria-eva-de-providentia-et-maria-martha-de-iesu",
    # Short romanized surnames were latinized in the workbook slugs by stripping
    # the final vowel and appending -us (Di -> dus, Li -> lus, Yi -> yus,
    # Xi -> xus, Bùi -> buus, Miki -> mikus). Rule: surnames are not latinized,
    # so the romanized form is preserved as printed in the elogium. (The Feb 6
    # Paul Miki memorial is already corrected above; mr:0205 is the Feb 5 pridie
    # anticipation the earlier correction missed.)
    "mr:0109-agatha-yus": "mr:0109-agatha-yi-et-teresia-kim",
    "mr:0110-aegidius-dus-bello": "mr:0110-aegidius-di-bello",
    "mr:0121-ioannes-yus-yun-il": "mr:0121-ioannes-yi-yun-il",
    "mr:0205-paulus-mikus-et-socii": "mr:0205-paulus-miki-et-socii",
    "mr:0219-lucia-yus-zhenmei": "mr:0219-lucia-yi-zhenmei",
    "mr:0524-augustinus-yus-kwang-hon": "mr:0524-augustinus-yi-kwang-hon-et-socii",
    "mr:0601-hannibalis-maria-dus-francia": "mr:0601-hannibalis-maria-di-francia",
    "mr:0613-augustinus-phan-viet-huy-et-nicolaus-buus-viet-the": "mr:0613-augustinus-phan-viet-huy-et-nicolaus-bui-viet-the",
    "mr:0630-raymundus-lus-quanzhen-et-petrus-lus-quanhui": "mr:0630-raymundus-li-quanzhen-et-petrus-li-quanhui",
    "mr:0720-magdalena-yus-yong-hui-et-socii": "mr:0720-magdalena-yi-yong-hui-et-socii",
    "mr:0720-xus-guizi": "mr:0720-xi-guizi",
    "mr:1125-petrus-yus-ho-yong": "mr:1125-petrus-yi-ho-yong",
    "mr:1219-franciscus-xaverius-ha-trong-mau-et-dominicus-buus-van-uy": "mr:1219-franciscus-xaverius-ha-trong-mau-et-dominicus-bui-van-uy",
    # Byname disambiguation: Gregory of Nyssa (well known by that byname)
    # shares Jan 10 with Pope Gregory X (mr:0110-gregorius-x). Rule 1's bare
    # first-named subject "gregorius" is ambiguous here, so the byname is kept.
    "mr:0110-gregorius": "mr:0110-gregorius-nyssenus",
    # Place-name lead slugs: the workbook coined these from the *place* named
    # first in the elogium (a locus whose name embeds a saint, e.g. "Burgi
    # Sancti Sepulcri", "Fanum Sancti Aegidii", "in coenobio Sancti Salvatoris
    # Vicecomitis"), not from the elogium's actual subject. Rule 1: the slug is
    # the first-named *subject*. Corrected to the subject's Latin nominative lemma.
    "mr:0115-aegidius": "mr:0115-petrus-de-castronovo",
    "mr:0120-bernardus": "mr:0120-michael-iwene-tansi",
    "mr:0127-vitalis": "mr:0127-manfredus-settala",
    "mr:0131-victor": "mr:0131-eusebius",
    "mr:0215-sepulcrus": "mr:0215-angelus-scarpetti",
    "mr:0216-petrus": "mr:0216-philippa-mareri",
    "mr:0220-trudo-fanus": "mr:0220-eucherius",
    "mr:0304-salvator-visconti": "mr:0304-eulalia-viel",
    "mr:0312-geminianus": "mr:0312-fina",
    "mr:0318-salvator-visconti": "mr:0318-amata-le-bouteiller",
    "mr:0406-elias-de-aulinis": "mr:0406-philaretus",
    "mr:0428-laurentius": "mr:0428-maria-ludovica-a-iesu",
    "mr:0606-annemundus": "mr:0606-marcellinus-champagnat",
    "mr:0716-crucis": "mr:0716-bartholomaeus-a-martyribus",
    "mr:0724-trudo-fanus": "mr:0724-christina-mirabilis",
    "mr:0818-iacobus": "mr:0818-albertus-hurtado-cruchaga",
    "mr:0829-iulia": "mr:0829-teresia-bracco",
    "mr:0928-felix-de-codines": "mr:0928-franciscus-xaverius-ponsa-casallarch",
    "mr:1025-antonius": "mr:1025-thaddaeus-machar",
    "mr:1101-sepulcrus": "mr:1101-rainerius-aretinus",
    # "Sancti Stephani Fanum" is Launceston; the subject is St Cuthbert Mayne
    # (surnames are not latinized).
    "mr:1130-stephanus-fanus": "mr:1130-cuthbertus-mayne",
    # #25: fifteen more place-name-lead slugs, found by comparing each slug with the
    # saints named in its opening place (data/places.json). The opening place is a
    # monastery, convent, town or district named after a saint; the subject is the
    # first lowercase sancti/beati after it.
    "mr:0130-benedictus-de-maretiolo": "mr:0130-columba-marmion",
    "mr:0212-cornelius": "mr:0212-benedictus-anianensis",
    "mr:0330-iulianus": "mr:0330-iulius-alvarez",
    "mr:0412-ioseph": "mr:0412-david-uribe",
    # "paenitens" keeps him apart from the better-known Bernards.
    "mr:0419-bertinus": "mr:0419-bernardus-paenitens",
    "mr:0426-isidorus-de-duenas": "mr:0426-raphael-arnaiz-baron",
    "mr:0502-gallus": "mr:0502-wiborada",
    "mr:0524-hyacinthus": "mr:0524-ludovicus-zephyrinus-moreau",
    "mr:0526-papulus": "mr:0526-berengarius",
    "mr:0620-iacobus-fodiensi": "mr:0620-ioannes-de-mateola",
    "mr:0726-benedictus": "mr:0726-simeon",
    "mr:0823-philippus": "mr:0823-antonius-de-hieracio",
    "mr:1205-petrus-de-aquara": "mr:1205-lucidus",
    # "episcopi Insulae": St Luke, bishop of Isola (Capo Rizzuto).
    "mr:1210-nicolaus-de-viotorito": "mr:1210-lucas-de-insula",
    # #25, found by a second scan (the subject after a place named after a saint,
    # mostly a monastery of St Mary).
    "mr:0205-caesarius": "mr:0205-sabas-iunior",
    "mr:0406-maria": "mr:0406-catharina-de-pallantia",
    # Another Ida (of Vallis Rosarum) is mr:0413-ida.
    "mr:0413-maria-de-capella": "mr:0413-ida-boloniensis",
    "mr:0508-maria-della-serra": "mr:0508-angelus-de-massatio",
    "mr:0603-maria-de-cadossa": "mr:0603-conus",
    "mr:0705-maria-de-terreto": "mr:0705-thomas",
    "mr:1114-maria": "mr:1114-siardus",
    "mr:1114-maria-de-gualdo-mazocca": "mr:1114-ioannes-de-tupharia",
    # The twenty monks of the laura of St Sabas: an anonymous group (rule 8).
    "mr:0320-sabas": "mr:0320-viginti-monachi-palaestinae",
    # Over-latinized surname: Bl. Francesco Patrizi (#25).
    "mr:0526-franciscus-patrizus": "mr:0526-franciscus-patrizi",
    # #33: slugs coined from a Latin genitive, a misread byname or a truncated name;
    # the slug is the subject's nominative lemma (rule 1), a papal ordinal as a
    # Roman numeral, an anonymous group by rule 8.
    "mr:0406-notkerus-balbuli": "mr:0406-notkerus-balbulus",
    "mr:0727-dormientium-ephesi": "mr:0727-septem-dormientes-ephesi",
    "mr:0413-carpus-et-thyatirensis": "mr:0413-carpus-et-socii",
    "mr:0724-bor-et-gleb": "mr:0724-boris-et-gleb",
    "mr:0110-petrus-urseoli": "mr:0110-petrus-urseolus",
    "mr:0125-arthematis": "mr:0125-arthemas",
    "mr:0129-gilda-sapientis": "mr:0129-gilda-sapiens",
    "mr:0226-pietatis-a-cruce-ortiz-real": "mr:0226-thomasina-ortiz-real",
    "mr:0307-paulus-simplicis": "mr:0307-paulus-simplex",
    "mr:0424-gulielmus-firmati": "mr:0424-gulielmus-firmatus",
    "mr:0425-pasicratis-et-valentio": "mr:0425-pasicrates-et-valentio",
    "mr:0426-paschasius-radberti": "mr:0426-paschasius-radbertus",
    "mr:0505-sacerdotis": "mr:0505-sacerdos",
    "mr:0522-humilitatis": "mr:0522-humilitas",
    "mr:0603-ioannes-vigesimi-iii": "mr:0603-ioannes-xxiii",
    "mr:0705-athanasius-hierosolymitani": "mr:0705-athanasius-hierosolymitanus",
    "mr:0712-ioannes-gualberti": "mr:0712-ioannes-gualbertus",
    "mr:0713-myropis": "mr:0713-myrope",
    "mr:0713-ludovicus-armandi-iosephus-adam": "mr:0713-ludovicus-armandus-iosephus-adam-et-bartholomaeus-jarrige-de-la-morelie-de-biars",
    "mr:0828-carolus-arnaldi-hanus": "mr:0828-carolus-arnaldus-hanus",
    "mr:0831-raymundus-nonnati": "mr:0831-raymundus-nonnatus",
    "mr:0904-caletricis": "mr:0904-caletricus",
    "mr:0911-sacerdotis": "mr:0911-sacerdos",
    "mr:0914-ioannes-chrysostomi": "mr:0914-ioannes-chrysostomus",
    "mr:0916-martinus-sacerdotis": "mr:0916-martinus-sacerdos",
    "mr:1115-caius-coreani": "mr:1115-caius-coreanus",
    "mr:1120-gregorius-decapolitani": "mr:1120-gregorius-decapolitanus",
    "mr:1128-papinianus-vitensis-et-mansuetus-urusitani": "mr:1128-papinianus-vitensis-et-mansuetus-urusitanus",
    "mr:1128-iacobus-piceni": "mr:1128-iacobus-picenus",
    "mr:1204-ioannes-damasceni": "mr:1204-ioannes-damascenus",
    "mr:1212-alexandrini-epimachi-et-alexander": "mr:1212-epimachus-et-alexander",
    "mr:0417-robertus-molismensi": "mr:0417-robertus-molismensis",
    "mr:0918-ferreolus-galliae-viennensi": "mr:0918-ferreolus-viennensis",
    "mr:0401-hugo-cisterciensi-bonae": "mr:0401-hugo-bonaevallensis",
    # Same place-name-lead bug, but the true subject already had a (wrongly)
    # deprecated ID at the same day: Postel (d. 1846) and Hildegard both have
    # 2004 elogia, so they are current, not attested-only-in-history. The
    # spurious deprecated IDs are removed from deprecated_ids.json and the
    # current place-slug entries re-slugged to the proper subject.
    "mr:0716-salvator-visconti": "mr:0716-maria-magdalena-postel",
    "mr:0917-rupertus": "mr:0917-hildegardis",
    # #25: the convent "Sancti Bonaventurae in Palatino" gave the slug; the subject,
    # St Leonard of Port Maurice, already had a deprecated ID on the day (attested
    # in 1749), which becomes current.
    "mr:1126-bonaventura": "mr:1126-leonardus-a-portu-mauritio",
    # #40: multi-subject slugs that named only the first subject take -et-<second>
    # for a pair and -et-socii for three or more (rule 5); single-subject slugs cut
    # short at a letter the fold did not decompose (Vietnamese Đ, apostrophes) are
    # completed; anonymous groups follow rule 8 as [number-]class-<place in the
    # genitive>, with martyres- + nominative plural for a named group. Kept in sync
    # with CatholicOS/martyrology-texts.
    "mr:0108-theophilus": "mr:0108-theophilus-et-helladius",
    "mr:0112-tigrius": "mr:0112-tigrius-et-eutropius",
    "mr:0113-gumesindus": "mr:0113-gumesindus-et-servusdei",
    "mr:0123-clemens": "mr:0123-clemens-et-agathangelus",
    "mr:0124-gulielmus-ireland": "mr:0124-gulielmus-ireland-et-ioannes-grove",
    "mr:0125-praeiectus": "mr:0125-praeiectus-et-amarinus",
    "mr:0129-sarbelius": "mr:0129-sarbelius-et-bebaia",
    "mr:0201-conorus-o-devany": "mr:0201-conorus-o-devany-et-patricius-o-lougham",
    "mr:0204-philea": "mr:0204-philea-et-philoromus",
    "mr:0206-dorothea": "mr:0206-dorothea-et-theophilus",
    "mr:0207-anselmus-polanco": "mr:0207-anselmus-polanco-et-philippus-ripoll",
    "mr:0207-iacobus-sales": "mr:0207-iacobus-sales-et-gulielmus-saultemouche",
    "mr:0214-cyrillus": "mr:0214-cyrillus-et-methodius",
    "mr:0225-aloysius-versiglia": "mr:0225-aloysius-versiglia-et-callistus-caravario",
    "mr:0303-marinus": "mr:0303-marinus-et-asterius",
    "mr:0309-petrus-ch": "mr:0309-petrus-choe-hyong-et-ioannes-baptista-chon-chang-un",
    "mr:0311-marcus-chong-ui-ba": "mr:0311-marcus-chong-ui-bae-et-alexius-u-se-yong",
    "mr:0313-rudericus": "mr:0313-rudericus-et-salomon",
    "mr:0316-hilarius": "mr:0316-hilarius-et-tatianus",
    "mr:0318-ioannes-thules": "mr:0318-ioannes-thules-et-rogerius-wrenno",
    "mr:0326-montanus": "mr:0326-montanus-et-maxima",
    "mr:0402-didacus-aloysius-de-san-vitores": "mr:0402-didacus-aloysius-de-san-vitores-et-petrus-calungsod",
    "mr:0403-robertus-middleton": "mr:0403-robertus-middleton-et-thurstanus-hunt",
    "mr:0404-agathopodus": "mr:0404-agathopodus-et-theodulus",
    "mr:0407-eduardus-oldcorne": "mr:0407-eduardus-oldcorne-et-radulphus-ashley",
    "mr:0417-petrus": "mr:0417-petrus-et-hermogenes",
    "mr:0420-franciscus-page": "mr:0420-franciscus-page-et-robertus-watkinson",
    "mr:0502-vindemialis": "mr:0502-vindemialis-et-longinus",
    "mr:0506-marianus": "mr:0506-marianus-et-iacobus",
    "mr:0519-ioannes-de-cetina": "mr:0519-ioannes-de-cetina-et-petrus-de-duenas",
    "mr:0522-petrus-ab-assumptione": "mr:0522-petrus-ab-assumptione-et-ioannes-baptista-machado",
    "mr:0526-ioannes": "mr:0526-ioannes-doan-trinh-hoan-et-matthaeus-nguyen-van-phuong",
    "mr:0527-barbara-kim": "mr:0527-barbara-kim-et-barbara-yi",
    "mr:0530-gulielmus-scott": "mr:0530-gulielmus-scott-et-richardus-newport",
    "mr:0531-robertus-thorpe": "mr:0531-robertus-thorpe-et-thomas-watkinson",
    "mr:0602-marcellinus": "mr:0602-marcellinus-et-petrus",
    "mr:0604-antonius-zawistowski": "mr:0604-antonius-zawistowski-et-stanislaus-starowieyski",
    "mr:0610-thomas-green": "mr:0610-thomas-green-et-gualterius-pierson",
    "mr:0615-petrus-snow": "mr:0615-petrus-snow-et-radulphus-grimston",
    "mr:0622-ioannes-fisher": "mr:0622-ioannes-fisher-et-thomas-more",
    "mr:0625-dominicus-henares": "mr:0625-dominicus-henares-et-franciscus-do-minh-chieu",
    "mr:0626-nicolaus-konrad": "mr:0626-nicolaus-konrad-et-vladimirus-pryjma",
    "mr:0629-maria-du-tianshi": "mr:0629-maria-du-tianshi-et-magdalena-du-fengju",
    "mr:0701-ioannes-baptista-duverneuil": "mr:0701-ioannes-baptista-duverneuil-et-petrus-aredius-labrouhe-de-laborderie",
    "mr:0707-antoninus-fantosati": "mr:0707-antoninus-fantosati-et-iosephus-maria-gambaro",
    "mr:0707-rogerius-dickinson": "mr:0707-rogerius-dickinson-et-radulphus-milner",
    "mr:0710-maria-gertrudis-a-sancta-sophia-de-ripert": "mr:0710-maria-gertrudis-a-sancta-sophia-et-sylvia-de-romillon",
    "mr:0711-placidus": "mr:0711-placidus-et-sigisbertus",
    "mr:0716-andreas-de-soveral": "mr:0716-andreas-de-soveral-et-dominicus-carvalho",
    "mr:0716-ioannes-sugar": "mr:0716-ioannes-sugar-et-robertus-grissold",
    "mr:0716-lang-yangzhi": "mr:0716-lang-yangzhi-et-paulus-lang-fu",
    "mr:0716-nicolaus-savouret": "mr:0716-nicolaus-savouret-et-claudius-beguignot",
    "mr:0717-zoerardus": "mr:0717-zoerardus-et-benedictus",
    "mr:0719-elisabeth-qin-bianzhi": "mr:0719-elisabeth-qin-bianzhi-et-simon-qin-chunfu",
    "mr:0722-philippus-evans": "mr:0722-philippus-evans-et-ioannes-lloyd",
    "mr:0723-petrus-ruiz": "mr:0723-petrus-ruiz-de-los-panos-et-iosephus-sala-pico",
    "mr:0726-eduardus-thwing": "mr:0726-eduardus-thwing-et-robertus-nutter",
    "mr:0726-marcellus-gaucherius-labigne-de-reignefort": "mr:0726-marcellus-gaucherius-labigne-de-reignefort-et-petrus-iosephus-le-groing-de-la-romagere",
    "mr:0726-vincentius-pinilla": "mr:0726-vincentius-pinilla-et-emmanuel-martin-sierra",
    "mr:0728-emmanuel-segura": "mr:0728-emmanuel-segura-et-david-carlos",
    "mr:0729-lazarus": "mr:0729-lazarus-et-maria",
    "mr:0731-dionysius-vicente-ramos": "mr:0731-dionysius-vicente-ramos-et-franciscus-remon-jativa",
    "mr:0731-petrus": "mr:0731-petrus-doan-cong-quy-et-emmanuel-phung",
    "mr:0801-dominicus-nguyen-van-hanh": "mr:0801-dominicus-nguyen-van-hanh-et-bernardus-vu-van-due",
    "mr:0803-alphonsus-lopez-lopez": "mr:0803-alphonsus-lopez-lopez-et-michael-remon-salvador",
    "mr:0809-faustinus-oteiza": "mr:0809-faustinus-oteiza-et-florentinus-felipe",
    "mr:0810-franciscus-drzewiecki": "mr:0810-franciscus-drzewiecki-et-eduardus-grzymala",
    "mr:0812-florianus-stepniak": "mr:0812-florianus-stepniak-et-iosephus-straszewski",
    "mr:0813-patricius-o-healy": "mr:0813-patricius-o-healy-et-connus-o-rourke",
    "mr:0814-dominicus-ibanez-de-erquicia": "mr:0814-dominicus-ibanez-de-erquicia-et-franciscus-shoyemon",
    "mr:0817-iacobus-kyuhei-gorobioye-tomonaga": "mr:0817-iacobus-kyuhei-gorobioye-tomonaga-et-michael-kurobioye",
    "mr:0823-florentinus-perez-romero": "mr:0823-florentinus-perez-romero-et-urbanus-gil-saez",
    "mr:0823-laurentius": "mr:0823-abundius-et-irenaeus",
    "mr:0827-ioannes-baptista-de-souzy": "mr:0827-ioannes-baptista-de-souzy-et-udalricus-guillaume",
    "mr:0829-ioannes-de-perusia": "mr:0829-ioannes-de-perusia-et-petrus-de-saxoferrato",
    "mr:0830-didacus-ventaja-milan": "mr:0830-didacus-ventaja-milan-et-emmanuel-medina-olmos",
    "mr:0905-petrus-nguyen-van-tu": "mr:0905-petrus-nguyen-van-tu-et-iosephus-hoang-luong-canh",
    "mr:0907-festus": "mr:0907-festus-et-desiderius",
    "mr:0907-randulphus-corby": "mr:0907-randulphus-corby-et-ioannes-duckett",
    "mr:0915-emila": "mr:0915-emila-et-ieremias",
    "mr:0916-rogellus": "mr:0916-rogellus-et-servusdei",
    "mr:0921-franciscus-jaccard": "mr:0921-franciscus-jaccard-et-thomas-tran-van-thien",
    "mr:0921-vincentius-galbis-girones": "mr:0921-vincentius-galbis-girones-et-emmanuel-torro-garcia",
    "mr:0922-vincentius-pelufo-corts": "mr:0922-vincentius-pelufo-corts-et-iosepha-moscardo-montalva",
    "mr:0924-gulielmus-spenser": "mr:0924-gulielmus-spenser-et-robertus-hardesty",
    "mr:0927-iosephus-fenollosa-alcayna": "mr:0927-iosephus-fenollosa-alcayna-et-fidelis-climent-sanches",
    "mr:0929-paulus-bori-puig": "mr:0929-paulus-bori-puig-et-vincentius-sales-genoves",
    "mr:1002-franciscus-carceller": "mr:1002-franciscus-carceller-et-isidorus-bover-oliver",
    "mr:1010-eulampius": "mr:1010-eulampius-et-eulampia",
    "mr:1016-amandus": "mr:1016-amandus-et-iunianus",
    "mr:1016-anicetus-koplinski": "mr:1016-anicetus-koplinski-et-iosephus-jankowski",
    "mr:1019-lucas-alphonsus-gorda": "mr:1019-lucas-alphonsus-gorda-et-matthaeus-kohioye",
    "mr:1022-philippus": "mr:1022-philippus-et-hermes",
    "mr:1023-ioannes-perside": "mr:1023-ioannes-et-iacobus",
    "mr:1025-martyrius": "mr:1025-martyrius-et-marcianus",
    "mr:1103-valentinus": "mr:1103-valentinus-et-hilarius",
    "mr:1104-nicandrus": "mr:1104-nicandrus-et-hermes",
    "mr:1110-narses": "mr:1110-narses-et-iosephus",
    "mr:1113-florentius": "mr:1113-florentius-et-amantius",
    "mr:1115-guria": "mr:1115-guria-et-samona",
    "mr:1115-marinus": "mr:1115-marinus-et-anianus",
    "mr:1119-elisaeus-garcia": "mr:1119-elisaeus-garcia-et-alexander-planas-sauri",
    "mr:1126-hugo-taylor": "mr:1126-hugo-taylor-et-marmaducus-bowes",
    "mr:1126-thomas": "mr:1126-thomas-dinh-viet-du-et-dominicus-nguyen-van-xuyen",
    "mr:1129-dionysius-a-nativitate-berthelot": "mr:1129-petrus-berthelot-et-thomas-rodriguez",
    "mr:1210-antonius-martin-hernandez": "mr:1210-antonius-martin-hernandez-et-augustinus-garcia-calvo",
    "mr:1210-edmundus-gennings": "mr:1210-edmundus-gennings-et-swithinus-wells",
    "mr:1229-henricus-ioannes-requena": "mr:1229-henricus-ioannes-requena-et-iosephus-perpina-nacher",
    "mr:0121-fructuosus": "mr:0121-fructuosus-et-socii",
    "mr:0128-agatha-lin-zhao": "mr:0128-agatha-lin-zhao-et-socii",
    "mr:0201-paulus-hong-yong-ju": "mr:0201-paulus-hong-yong-ju-et-socii",
    "mr:0215-isicus": "mr:0215-isicus-et-socii",
    "mr:0304-christophorus-bales": "mr:0304-christophorus-bales-et-socii",
    "mr:0307-simeon-berneux": "mr:0307-simeon-berneux-et-socii",
    "mr:0312-mygdo": "mr:0312-mygdo-et-socii",
    "mr:0313-macedonius": "mr:0313-macedonius-et-socii",
    "mr:0323-victorianus": "mr:0323-victorianus-et-socii",
    "mr:0330-antonius-daveluy": "mr:0330-antonius-daveluy-et-socii",
    "mr:0401-venantius": "mr:0401-venantius-et-socii",
    "mr:0407-theodorus": "mr:0407-theodorus-et-socii",
    "mr:0416-optatus": "mr:0416-optatus-et-socii",
    "mr:0417-donnanus": "mr:0417-donnanus-et-socii",
    "mr:0417-elias": "mr:0417-elias-et-socii",
    "mr:0428-paulus-pham-khac-khoan": "mr:0428-paulus-pham-khac-khoan-et-socii",
    "mr:0430-amator": "mr:0430-amator-et-socii",
    "mr:0501-torquatus": "mr:0501-torquatus-et-socii",
    "mr:0529-gulielmus-arnaud": "mr:0529-gulielmus-arnaud-et-socii",
    "mr:0529-sisinnius": "mr:0529-sisinnius-et-socii",
    "mr:0601-alphonsus-navarrete": "mr:0601-alphonsus-navarrete-et-socii",
    "mr:0601-ischyrion": "mr:0601-ischyrion-et-socii",
    "mr:0602-pothinus": "mr:0602-pothinus-et-socii",
    "mr:0607-petrus": "mr:0607-petrus-et-socii",
    "mr:0614-anastasius": "mr:0614-anastasius-et-socii",
    "mr:0616-aureus": "mr:0616-aureus-et-socii",
    "mr:0616-dominicus-nguyen": "mr:0616-dominicus-nguyen-et-socii",
    "mr:0629-paulus-wu-juan": "mr:0629-paulus-wu-juan-et-socii",
    "mr:0702-liberatus": "mr:0702-liberatus-et-socii",
    "mr:0704-gulielmus-andleby": "mr:0704-gulielmus-andleby-et-socii",
    "mr:0704-ioannes-cornelius": "mr:0704-ioannes-cornelius-et-socii",
    "mr:0713-alexander": "mr:0713-alexander-et-socii",
    "mr:0715-catulinus": "mr:0715-catulinus-et-socii",
    "mr:0715-philippus": "mr:0715-philippus-et-socii",
    "mr:0716-reinildis": "mr:0716-reinildis-et-socii",
    "mr:0720-maria-zhao-guozhus": "mr:0720-maria-zhao-guozhi-et-socii",
    "mr:0722-anna-wang": "mr:0722-anna-wang-et-socii",
    "mr:0725-fridericus-rubio-alvarez": "mr:0725-carolus-rubio-alvarez-et-socii",
    "mr:0725-petrus-a-corde-redondo": "mr:0725-petrus-a-corde-et-socii",
    "mr:0727-georgius": "mr:0727-georgius-et-socii",
    "mr:0729-ludovicus-bertran": "mr:0729-ludovicus-bertran-et-socii",
    "mr:0730-iosephus-maria-muro-sanmiguel": "mr:0730-iosephus-maria-muro-sanmiguel-et-socii",
    "mr:0801-maria-stella-a-sanctissimo-sacramento-mardosewicz": "mr:0801-adelheidis-mardosewicz-et-socii",
    "mr:0804-iosephus-batalla-parramon": "mr:0804-iosephus-batalla-parramon-et-socii",
    "mr:0807-martinus-a-sancto-felice-woodcock": "mr:0807-ioannes-woodcock-et-socii",
    "mr:0810-claudius-iosephus-jouffret-de-bonnefont": "mr:0810-claudius-iosephus-jouffret-de-bonnefont-et-socii",
    "mr:0812-iacobus": "mr:0812-iacobus-do-mai-nam-et-socii",
    "mr:0812-porcarius": "mr:0812-porcarius-et-socii",
    "mr:0815-aloysius-batis-sainz": "mr:0815-aloysius-batis-sainz-et-socii",
    "mr:0816-simon-bokusai-kyota": "mr:0816-simon-bokusai-kyota-et-socii",
    "mr:0821-bassa": "mr:0821-bassa-et-socii",
    "mr:0821-bernardus": "mr:0821-bernardus-et-socii",
    "mr:0823-constantinus-carbonell-sempere": "mr:0823-constantinus-carbonell-sempere-et-socii",
    "mr:0825-michael-carvalho": "mr:0825-michael-carvalho-et-socii",
    "mr:0827-marcellinus": "mr:0827-marcellinus-et-socii",
    "mr:0901-petrus-rivera": "mr:0901-petrus-rivera-et-socii",
    "mr:0907-marcus-crisini": "mr:0907-marcus-crisini-et-socii",
    "mr:0907-thomas-tsuji": "mr:0907-thomas-tsuji-et-socii",
    "mr:0908-thomas-palaser": "mr:0908-thomas-palaser-et-socii",
    "mr:0911-gaspar-koteda": "mr:0911-gaspar-koteda-et-socii",
    "mr:0912-apollinaris-franco": "mr:0912-apollinaris-franco-et-socii",
    "mr:0916-laureanus-ferrer-cardet": "mr:0916-salvator-ferrer-cardet-et-socii",
    "mr:0921-laurentius-imbert": "mr:0921-laurentius-imbert-et-socii",
    "mr:0923-sophia-ximenez-ximenez": "mr:0923-sophia-ximenez-ximenez-et-socii",
    "mr:0925-ioannes-petrus-bengoa-aranguren": "mr:0925-iosephus-bengoa-aranguren-et-socii",
    "mr:0928-ioannes-shozaburo": "mr:0928-ioannes-shozaburo-et-socii",
    "mr:1010-septem-martyres-presbyteri-septam": "mr:1010-daniel-et-socii",
    "mr:1018-proculus": "mr:1018-proculus-et-socii",
    "mr:1025-maria-teresia-ferragud-roig": "mr:1025-maria-teresia-ferragud-roig-et-socii",
    "mr:1028-franciscus-serrano": "mr:1028-franciscus-serrano-et-socii",
    "mr:1101-petrus-paulus-navarro": "mr:1101-petrus-paulus-navarro-et-socii",
    "mr:1108-iosephus-nguyen": "mr:1108-iosephus-nguyen-dinh-nghi-et-socii",
    "mr:1113-martyres-africa": "mr:1113-arcadius-et-socii",
    "mr:1115-hugo-faringdon": "mr:1115-hugo-faringdon-et-socii",
    "mr:1115-richardus-whiting": "mr:1115-richardus-whiting-et-socii",
    "mr:1118-leonardus-kimura": "mr:1118-leonardus-kimura-et-socii",
    "mr:1122-salvator-lilli": "mr:1122-salvator-lilli-et-socii",
    "mr:1124-petrus-dumoulin-borie": "mr:1124-petrus-dumoulin-borie-et-socii",
    "mr:1204-franciscus-galvez": "mr:1204-franciscus-galvez-et-socii",
    "mr:1209-richardus": "mr:1209-richardus-de-los-rios-fabregat-et-socii",
    "mr:1222-chaeremon": "mr:1222-chaeremon-et-socii",
    "mr:0509-iosephus": "mr:0509-iosephus-do-quang-hien",
    "mr:0522-michael-ho": "mr:0522-michael-ho-dinh-hy",
    "mr:0525-petrus": "mr:0525-petrus-doan-van-van",
    "mr:0603-petrus": "mr:0603-petrus-dong",
    "mr:0617-petrus": "mr:0617-petrus-da",
    "mr:0630-vincentius": "mr:0630-vincentius-do-yen",
    "mr:0703-iosephus-nguyen": "mr:0703-iosephus-nguyen-dinh-uyen",
    "mr:0718-dominicus-nicolaus": "mr:0718-dominicus-nicolaus-dinh-dat",
    "mr:0821-iosephus": "mr:0821-iosephus-dang-dinh-vien",
    "mr:0912-franciscus-ch": "mr:0912-franciscus-choe-kyong-hwan",
    "mr:1021-petrus-yu-tae-ch": "mr:1021-petrus-yu-tae-chol",
    "mr:1024-iosephus-le": "mr:1024-iosephus-le-dang-thi",
    "mr:1028-ioannes": "mr:1028-ioannes-dat",
    "mr:1212-simon-phan": "mr:1212-simon-phan-dac-hoa",
    "mr:0205-plurimi-martyres-ponto": "mr:0205-plurimi-martyres-ponti",
    "mr:0211-plurimi-martyres-numidia": "mr:0211-plurimi-martyres-numidiae",
    "mr:0212-martyres-carthagine": "mr:0212-martyres-abitinenses",
    "mr:0219-monachi-martyres-palaestina": "mr:0219-monachi-martyres-palaestinae",
    "mr:0306-quadraginta-duo-martyres-syria": "mr:0306-quadraginta-duo-martyres-syriae",
    "mr:0309-quadraginta-milites-sebastem": "mr:0309-quadraginta-milites-sebastes",
    "mr:0321-alexandrini": "mr:0321-martyres-alexandrini",
    "mr:0330-plurimi-martyres-constantinopoli": "mr:0330-plurimi-martyres-constantinopolis",
    "mr:0405-martyres-regiis": "mr:0405-martyres-regiarum",
    "mr:0407-ducenti-milites-martyres-sinope": "mr:0407-ducenti-milites-martyres-sinopes",
    "mr:0509-martyres-trecenti-decem-perside": "mr:0509-trecenti-decem-martyres-persidis",
    "mr:0516-quadraginta-quattuor-monachi-palaestina": "mr:0516-quadraginta-quattuor-monachi-palaestinae",
    "mr:0523-martyres-cappadocia": "mr:0523-martyres-cappadociae",
    "mr:0523-martyres-mesopotamia": "mr:0523-martyres-mesopotamiae",
    "mr:0524-triginta-octo-martyres-philippopoli": "mr:0524-triginta-octo-martyres-philippopolis",
    "mr:0630-sancta-romana-ecclesia": "mr:0630-protomartyres-sanctae-romanae-ecclesiae",
    "mr:0708-monachi-constantinopoli": "mr:0708-monachi-abrahamitae",
    "mr:0717-scillitani": "mr:0717-martyres-scillitani",
    "mr:0722-massilitani": "mr:0722-martyres-massilitani",
    "mr:0809-martyres-constantinopoli": "mr:0809-martyres-constantinopolis",
    "mr:0818-massa-candida": "mr:0818-martyres-massae-candidae",
    "mr:1005-martyres-treviris": "mr:1005-martyres-trevirorum",
    "mr:1012-martyres-confessores-quattuor-sexaginta-africa": "mr:1012-martyres-et-confessores-africae",
    "mr:1017-volitani": "mr:1017-martyres-volitani",
    "mr:1021-virgines-coloniam-agrippinam": "mr:1021-virgines-coloniae-agrippinae",
    "mr:1115-viginti-martyres-hippone-regio": "mr:1115-viginti-martyres-hipponis-regii",
    "mr:1119-mulieres-virgines-viduae-quadraginta-martyres-heracleae": "mr:1119-quadraginta-martyres-heracleae",
    "mr:1206-martyres-africa": "mr:1206-martyres-africae",
    "mr:1217-quinquaginta-milites-eleutheropoli": "mr:1217-quinquaginta-milites-eleutheropolis",
    # #47: St Eleutherius of Tournai is told apart from the other Eleutherii of
    # February 20 (Constantinople and Persia, deprecated IDs of the 1749 edition) by
    # his see. Kept in sync with CatholicOS/martyrology-texts.
    "mr:0220-eleutherius": "mr:0220-eleutherius-tornaci",
    # #77: the 2004 Latin's "et" splits Sister Mélanie (Maria Anna Magdalena de
    # Guilhermier) in two; the eulogy's second martyr is Maria Anna Margarita ab
    # Angelis de Rocher. Named by the religious names, like mr:0710. Kept in sync
    # with CatholicOS/martyrology-texts.
    "mr:0709-melania-et-maria-anna-magdalena-de-guilhermier": "mr:0709-melania-et-maria-anna-margarita-ab-angelis",

    # #52: slugs that misnamed the 2004 eulogy (a truncated name, the cemetery's name,
    # the next sentence's word, a genitive stem), and the prophets, which keep
    # -propheta (-prophetissa, -rex-et-propheta) in the nominative.
    "mr:0905-v": "mr:0905-quintus",
    "mr:0809-laurentius": "mr:0809-romanus",
    "mr:0629-petrus-et-paulus-simon": "mr:0629-petrus-et-paulus-apostoli",
    "mr:1028-fidel": "mr:1028-fidelis",
    "mr:0424-fidel-de-sigmaringa": "mr:0424-fidelis-de-sigmaringa",
    "mr:0408-agabus": "mr:0408-agabus-propheta",
    "mr:0501-ieremias": "mr:0501-ieremias-propheta",
    "mr:0509-isaias": "mr:0509-isaias-propheta",
    "mr:0614-elisaeus": "mr:0614-elisaeus-propheta",
    "mr:0615-amos": "mr:0615-amos-propheta",
    "mr:0720-elias-thesbita": "mr:0720-elias-thesbita-propheta",
    "mr:0723-ezechiel": "mr:0723-ezechiel-propheta",
    "mr:0820-samuel": "mr:0820-samuel-propheta",
    "mr:0904-moyses": "mr:0904-moyses-propheta",
    "mr:0906-zacharias": "mr:0906-zacharias-propheta",
    "mr:0921-iona": "mr:0921-ionas-propheta",
    "mr:1017-osea": "mr:1017-osee-propheta",
    "mr:1019-ioel": "mr:1019-ioel-propheta",
    "mr:1119-abdia": "mr:1119-abdias-propheta",
    "mr:1201-nahum": "mr:1201-nahum-propheta",
    "mr:1202-habacuc": "mr:1202-habacuc-propheta",
    "mr:1203-sophonia": "mr:1203-sophonias-propheta",
    "mr:1216-aggaeus": "mr:1216-aggaeus-propheta",
    "mr:1218-malachia": "mr:1218-malachias-propheta",
    "mr:1221-michaea": "mr:1221-michaeas-propheta",
    "mr:1229-david": "mr:1229-david-rex-et-propheta",
    "mr:0203-simeon-et-anna": "mr:0203-simeon-et-anna-prophetissa",

    # #56: the apostles keep -apostolus / -apostoli (Paul too), and feast phrases drop
    # the honorific (cathedra-petri-apostoli, conversio-pauli-apostoli).
    "mr:0125-conversio-sancti-pauli": "mr:0125-conversio-pauli-apostoli",
    "mr:0222-cathedra-sancti-petri": "mr:0222-cathedra-petri-apostoli",
    "mr:0503-philippus-et-iacobus": "mr:0503-philippus-et-iacobus-apostoli",
    "mr:0514-matthias": "mr:0514-matthias-apostolus",
    "mr:0703-thomas": "mr:0703-thomas-apostolus",
    "mr:0725-iacobus": "mr:0725-iacobus-apostolus",
    "mr:0824-bartholomaeus": "mr:0824-bartholomaeus-apostolus",
    "mr:0921-matthaeus": "mr:0921-matthaeus-apostolus-et-evangelista",
    "mr:1028-simon-et-iudas": "mr:1028-simon-et-iudas-apostoli",
    "mr:1118-dedicatio-basilicarum-petri-et-pauli": "mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum",
    "mr:1130-andreas": "mr:1130-andreas-apostolus",
    "mr:1227-ioannes": "mr:1227-ioannes-apostolus-et-evangelista",

    # #59: the evangelists Mark and Luke keep -evangelista.
    "mr:0425-marcus": "mr:0425-marcus-evangelista",
    "mr:1018-lucas": "mr:1018-lucas-evangelista",

    # #59: papal ordinals are roman numerals (rule 3).
    "mr:0116-marcellus-primus": "mr:0116-marcellus-i",
    # a same-day namesake takes his see, not a number (rule 9)
    "mr:0408-dionysius-2": "mr:0408-dionysius-corinthi",

    # #63: one conventional name form per saint (religious name OR name + surname).
    "mr:0105-carolus-a-sancto-andrea-houben": "mr:0105-ioannes-andreas-houben",
    "mr:0106-raphaela-maria-a-sacro-corde-porras-ayllon": "mr:0106-raphaela-maria-a-sacro-corde",
    "mr:0109-maria-teresia-a-iesu-le-clerc": "mr:0109-alexia-le-clerc",
    "mr:0110-anna-ab-angelis-monteagudo": "mr:0110-anna-ab-angelis",
    "mr:0111-thomas-de-cora-placidi": "mr:0111-franciscus-antonius-placidi",
    "mr:0113-veronica-de-binasco-negroni": "mr:0113-veronica-de-binasco",
    "mr:0114-odoricus-de-portu-naonis-mattiuzzi": "mr:0114-odoricus-de-portu-naonis",
    "mr:0118-andreas-de-piscaria-grego": "mr:0118-andreas-de-piscaria",
    "mr:0120-maria-christina-ab-immaculata-brando": "mr:0120-adalheidis-brando",
    "mr:0201-ioanna-francisca-a-visitatione-michelotti": "mr:0201-anna-michelotti",
    "mr:0202-simon-de-cassia-fidati": "mr:0202-simon-de-cassia",
    "mr:0203-maria-a-sancto-ignatio-thevenet": "mr:0203-claudina-thevenet",
    "mr:0207-aegidius-maria-a-sancto-ioseph-pontillo": "mr:0207-aegidius-maria-a-sancto-ioseph",
    "mr:0207-ioannes-de-triora-lantrua": "mr:0207-ioannes-de-triora",
    "mr:0207-maria-a-providentia-smet": "mr:0207-eugenia-smet",
    "mr:0214-ioannes-baptista-a-conceptione-garcia": "mr:0214-ioannes-baptista-a-conceptione",
    "mr:0219-conradus-de-placentia-confalonieri": "mr:0219-conradus-confalonieri",
    "mr:0224-constantius-de-fabriano-servoli": "mr:0224-constantius-de-fabriano",
    "mr:0226-paula-a-sancto-iosepho-de-calasanz-montal-fornes": "mr:0226-paula-a-sancto-iosepho-de-calasanz",
    "mr:0227-francisca-anna-a-virgine-perdolenti-cirer-carbonell": "mr:0227-francisca-anna-a-virgine-perdolenti",
    "mr:0227-gabriel-a-virgine-perdolenti-possenti": "mr:0227-gabriel-a-virgine-perdolenti",
    "mr:0227-maria-a-iesu-deluil-martiny": "mr:0227-maria-a-iesu",
    "mr:0227-maria-a-caritate-spiritus-sancti-brader": "mr:0227-carolina-brader",
    "mr:0302-angela-a-cruce-guerrero-gonzalez": "mr:0302-angela-a-cruce",
    "mr:0303-innocentius-de-berzo-scalvinoni": "mr:0303-ioannes-scalvinoni",
    "mr:0305-ieremias-de-valachia-kostistik": "mr:0305-ioannes-kostistik",
    "mr:0305-ioannes-iosephus-a-cruce-calosirto": "mr:0305-carolus-caietanus-calosirto",
    "mr:0310-elias-a-succursu-nieves-del-castillo": "mr:0310-matthaeus-elias-nieves-del-castillo",
    "mr:0311-ioannes-baptista-de-fabriano-righi": "mr:0311-ioannes-baptista-de-fabriano",
    "mr:0318-salvator-de-horta-grionesos": "mr:0318-salvator-de-horta",
    "mr:0319-ioannes-de-parma-buralli": "mr:0319-ioannes-de-parma",
    "mr:0319-marcus-de-marchio-de-montegallo": "mr:0319-marcus-de-montegallo",
    "mr:0320-franciscus-a-iesu-maria-ioseph-palau-y-quer": "mr:0320-franciscus-a-iesu-maria-ioseph",
    "mr:0320-maria-iosepha-a-corde-iesu-sancho-de-guerra": "mr:0320-maria-iosepha-a-corde-iesu",
    "mr:0324-didacus-iosephus-de-gadibus-lopez-caamano": "mr:0324-franciscus-iosephus-lopez-caamano",
    "mr:0330-petrus-de-vallisoleto-regalado": "mr:0330-petrus-regalado",
    "mr:0330-ludovicus-de-casaurea-palmentieri": "mr:0330-ludovicus-de-casaurea",
    "mr:0402-maria-a-sancto-ioseph-alvarado": "mr:0402-laura-alvarado",
    "mr:0403-gandulfus-de-binasco-sacchi": "mr:0403-gandulfus-de-binasco",
    "mr:0408-dominicus-a-sanctissimo-sacramento-iturrate": "mr:0408-dominicus-a-sanctissimo-sacramento",
    "mr:0410-marcus-de-bononia-fantuzzi": "mr:0410-marcus-de-bononia",
    "mr:0411-angelus-de-clavasio-carletti": "mr:0411-antonius-carletti",
    "mr:0412-teresia-a-iesu-fernandez-solar": "mr:0412-ioanna-fernandez-solar",
    "mr:0417-maria-anna-a-iesu-navarro-de-guevara": "mr:0417-maria-anna-a-iesu",
    "mr:0418-maria-ab-incarnatione-avrillot": "mr:0418-barbara-avrillot",
    "mr:0420-simon-de-tuderto-rinalducci": "mr:0420-simon-de-tuderto",
    "mr:0421-conradus-de-parzham-birndorfer": "mr:0421-conradus-de-parzham",
    "mr:0423-teresia-maria-a-cruce-manetti": "mr:0423-teresia-maria-a-cruce",
    "mr:0424-maria-a-sancta-euphrasia-pelletier": "mr:0424-rosa-virginia-pelletier",
    "mr:0427-iacobus-de-iadere-varinguer": "mr:0427-iacobus-de-iadere",
    "mr:0430-maria-ab-incarnatione-guyart-martin": "mr:0430-maria-ab-incarnatione",
    "mr:0508-maria-catharina-a-sancto-augustino-symon-de-longprey": "mr:0508-catharina-symon-de-longprey",
    "mr:0509-maria-teresia-a-iesu-gerhardinger": "mr:0509-carolina-gerhardinger",
    "mr:0519-ioannes-a-sancto-dominico-martinez": "mr:0519-ioannes-a-sancto-dominico",
    "mr:0531-marianus-de-roccacasale-di-nicolantonio": "mr:0531-dominicus-di-nicolantonio",
    "mr:0606-laurentius-de-villamagna-de-masculis": "mr:0606-laurentius-de-villamagna",
    "mr:0608-maria-a-divino-corde-iesu-droste": "mr:0608-maria-a-divino-corde-iesu",
    "mr:0608-nicolaus-de-gesturi-medda": "mr:0608-ioannes-medda",
    "mr:0611-ioannes-a-sancto-facundo-gonzalez-de-castrillo": "mr:0611-ioannes-a-sancto-facundo",
    "mr:0611-rosa-francisca-maria-a-doloribus-molas-vallve": "mr:0611-maria-rosa-molas-vallve",
    "mr:0612-laurentius-maria-a-sancto-francisco-xaverio-salvi": "mr:0612-laurentius-maria-a-sancto-francisco-xaverio",
    "mr:0612-mercedis-maria-a-iesu-molina": "mr:0612-mercedis-maria-a-iesu",
    "mr:0612-maria-candida-ab-eucharistia-barba": "mr:0612-maria-candida-ab-eucharistia",
    "mr:0706-nazaria-a-sancta-teresia-march-mesa": "mr:0706-nazaria-a-sancta-teresia",
    "mr:0707-iphigenia-a-sancto-matthaeo-de-gaillard-de-la-valdene": "mr:0707-francisca-maria-suzanna-de-gaillard-de-la-valdene",
    "mr:0709-paulina-a-corde-iesu-agonizante-visintainer": "mr:0709-paulina-a-corde-iesu-agonizante",
    "mr:0709-maria-a-iesu-crucifixo-petkovic": "mr:0709-maria-a-iesu-crucifixo",
    "mr:0711-rosalia-clotildis-a-sancta-pelagia-bes-et-socii": "mr:0711-rosalia-clotildis-a-sancta-pelagia-et-socii",
    "mr:0712-rosa-a-sancto-xaverio-tallien-et-socii": "mr:0712-magdalena-teresia-tallien-et-socii",
    "mr:0713-magdalena-a-matre-dei-verchiere-et-socii": "mr:0713-elisabeth-verchiere-et-socii",
    "mr:0716-amata-a-iesu-de-gordon-et-socii": "mr:0716-maria-rosa-de-gordon-et-socii",
    "mr:0717-teresia-a-sancto-augustino-lidoine-et-socii": "mr:0717-maria-magdalena-claudina-lidoine-et-socii",
    "mr:0720-rita-a-virgine-perdolenti-a-corde-iesu-pujalte-y-sanchez-et-francisca-a-corde-iesu-aldea-y-araujo": "mr:0720-rita-a-virgine-perdolenti-a-corde-iesu-et-francisca-a-corde-iesu",
    "mr:0722-augustinus-de-bugella-fangi": "mr:0722-augustinus-de-bugella",
    "mr:0724-ioannes-de-tossiniano-tavelli": "mr:0724-ioannes-de-tossiniano",
    "mr:0724-modestinus-a-iesu-et-maria-mazzarello": "mr:0724-dominicus-mazzarello",
    "mr:0724-maria-a-columna-a-sancto-francisco-borgia-martinez-garcia-et-socii": "mr:0724-iacoba-martinez-garcia-et-socii",
    "mr:0725-petrus-de-molliano-corradini": "mr:0725-petrus-de-molliano",
    "mr:0726-maria-margarita-a-sancto-augustino-bonnet-et-socii": "mr:0726-maria-margarita-a-sancto-augustino-et-socii",
    "mr:0727-maria-clemens-a-iesu-crucifixo-staszewska": "mr:0727-maria-clemens-a-iesu-crucifixo",
    "mr:0728-alphonsa-ab-immaculata-conceptione-muttathupadathu": "mr:0728-anna-muttathupadathu",
    "mr:0730-leopoldus-de-castronovo-mandic": "mr:0730-leopoldus-mandic",
    "mr:0730-maria-vincentia-a-sancta-dorothea-chavez-orozco": "mr:0730-maria-vincentia-a-sancta-dorothea",
    "mr:0730-maria-a-iesu-sacramentato-venegas-de-la-torre": "mr:0730-maria-a-iesu-sacramentato",
    "mr:0806-maria-francisca-a-iesu-rubatto": "mr:0806-anna-maria-rubatto",
    "mr:0807-agathangelus-de-vindocino-nourry-et-cassianus-de-nannetibus-vaz-lopez-netto": "mr:0807-franciscus-nourry-et-gundisalvus-vaz-lopez-netto",
    "mr:0808-maria-a-cruce-mackillop": "mr:0808-maria-helena-mackillop",
    "mr:0808-maria-a-iesu-infante-baldillou-y-bullit-et-socii": "mr:0808-maria-a-iesu-infante-et-socii",
    "mr:0809-teresia-benedicta-a-cruce-stein": "mr:0809-editha-stein",
    "mr:0809-candida-maria-a-iesu-cipitria": "mr:0809-ioanna-iosepha-cipitria",
    "mr:0810-archangelus-de-calataphino-piacentini": "mr:0810-archangelus-de-calataphino",
    "mr:0813-marcus-de-aviano-cristofori": "mr:0813-marcus-de-aviano",
    "mr:0814-sanctus-de-urbino-brancorsini": "mr:0814-sanctus-de-urbino",
    "mr:0815-maria-a-sacrario-a-sancto-aloysio-gonzaga-moragas-cantarero": "mr:0815-elvira-moragas-cantarero",
    "mr:0816-petra-a-sancto-ioseph-perez-florido": "mr:0816-anna-iosepha-perez-florido",
    "mr:0819-elvira-a-nativitate-dominae-nostrae-torrentalle-paraire-et-socii": "mr:0819-elvira-a-nativitate-dominae-nostrae-et-socii",
    "mr:0823-ioannes-maria-a-cruce-garcia-mendez": "mr:0823-marianus-garcia-mendez",
    "mr:0824-maria-michaela-a-sanctissimo-sacramento-desmaisieres": "mr:0824-maria-michaela-a-sanctissimo-sacramento",
    "mr:0824-maria-ab-incarnatione-rosal": "mr:0824-maria-vincentia-rosal",
    "mr:0826-maria-a-iesu-crucifixo-baouardy": "mr:0826-maria-baouardy",
    "mr:0826-teresia-a-iesu-jornet-ibars": "mr:0826-teresia-jornet-ibars",
    "mr:0827-dominicus-a-matre-dei-barberi": "mr:0827-dominicus-barberi",
    "mr:0829-maria-a-cruce-jugan": "mr:0829-ioanna-jugan",
    "mr:0903-birgitta-a-iesu-morello": "mr:0903-birgitta-a-iesu",
    "mr:0907-ascensio-a-sancto-iosepho-calasanz-lloret-marco": "mr:0907-ascensio-a-sancto-iosepho-calasanz",
    "mr:0908-iosepha-a-sancto-ioanne-a-deo-ruano-garcia-et-maria-a-doloribus-a-sancta-eulalia-puig-bonany": "mr:0908-iosepha-a-sancto-ioanne-a-deo-et-maria-a-doloribus-a-sancta-eulalia",
    "mr:0911-bonaventura-de-barcinone-gran": "mr:0911-michael-gran",
    "mr:0911-petrus-de-alcantara-villanueva-larrayoz": "mr:0911-petrus-de-alcantara",
    "mr:0913-maria-a-iesu-lopez-de-rivas": "mr:0913-maria-a-iesu",
    "mr:0919-maria-a-iesu-de-la-yglesia-y-de-varo-et-socii": "mr:0919-maria-a-iesu-et-socii",
    "mr:0921-marcus-de-mutina-scalabrini": "mr:0921-marcus-de-mutina",
    "mr:0922-ignatius-de-sandone-belvisotti": "mr:0922-laurentius-mauritius-belvisotti",
    "mr:0923-pius-de-pietrelcina-forgione": "mr:0923-pius-de-pietrelcina",
    "mr:0926-maria-a-refugio-rosat-balasch-et-maria-a-calvario-romero-clariana": "mr:0926-teresia-rosat-balasch-et-iosepha-romero-clariana",
    "mr:0928-laurentius-de-manila-ruiz-et-socii": "mr:0928-laurentius-ruiz-et-socii",
    "mr:0928-bernardinus-de-feltria-tomitano": "mr:0928-bernardinus-de-feltria",
    "mr:1006-isidorus-a-sancto-ioseph-de-loor": "mr:1006-isidorus-a-sancto-ioseph",
    "mr:1009-innocentius-ab-immaculata-canoura-arnau-et-socii": "mr:1009-emmanuel-canoura-arnau-et-socii",
    "mr:1011-iacobus-de-ulma-griesinger": "mr:1011-iacobus-de-ulma",
    "mr:1012-seraphinus-de-monte-granario-de-nicola": "mr:1012-felix-de-nicola",
    "mr:1017-maria-natalia-a-sancto-ludovico-vanot-et-socii": "mr:1017-maria-ludovica-iosepha-vanot-et-socii",
    "mr:1019-agnes-a-iesu-galand": "mr:1019-agnes-a-iesu",
    "mr:1021-laura-a-sancta-catharina-senensi-montoya-y-upegui": "mr:1021-laura-montoya-y-upegui",
    "mr:1023-maria-clotildis-angela-a-sancto-francisco-borgia-paillot-et-socii": "mr:1023-clotildis-iosepha-paillot-et-socii",
    "mr:1031-thomas-de-florentia-bellaci": "mr:1031-thomas-de-florentia",
    "mr:1102-pius-a-sancto-aloysio-campidelli": "mr:1102-pius-a-sancto-aloysio",
    "mr:1109-elisabeth-a-sanctissima-trinitate-catez": "mr:1109-elisabeth-a-sanctissima-trinitate",
    "mr:1113-maria-a-patrocinio-a-sancto-ioanne-giner-gomis": "mr:1113-maria-a-patrocinio-a-sancto-ioanne",
    "mr:1115-maria-a-passione-de-chappotin-de-neuville": "mr:1115-helena-de-chappotin-de-neuville",
    "mr:1115-raphael-a-sancto-ioseph-kalinowski": "mr:1115-iosephus-kalinowski",
    "mr:1118-grimoaldus-a-purificatione-santamaria": "mr:1118-ferdinandus-santamaria",
    "mr:1118-maria-a-refugio-hinojosa-y-naveros-et-socii": "mr:1118-maria-gabriela-hinojosa-y-naveros-et-socii",
    "mr:1120-angela-a-sancto-ioseph-lloret-marti-et-socii": "mr:1120-francisca-lloret-marti-et-socii",
    "mr:1121-maria-a-iesu-bono-pastore-de-siedliska": "mr:1121-francisca-de-siedliska",
    "mr:1124-nicetha-a-sancta-prudentia-plaja-xifra-et-socii": "mr:1124-nicetha-a-sancta-prudentia-et-socii",
    "mr:1127-bernardinus-de-fossa-amici": "mr:1127-ioannes-amici",
    "mr:1130-ioannes-de-vercellis-garbella": "mr:1130-ioannes-de-vercellis",
    "mr:1209-bernardus-maria-a-iesu-silvestrelli": "mr:1209-caesar-silvestrelli",
    "mr:1211-mirabilia-a-iesu-pidal-y-chico-de-guzman": "mr:1211-mirabilia-a-iesu",
    "mr:1216-maria-ab-angelis-fontanella": "mr:1216-marianna-fontanella",
    "mr:1217-mathildis-a-sacro-corde-tellez-robles": "mr:1217-mathildis-a-sacro-corde",
    "mr:1223-antonius-a-sancta-anna-galvao-de-franca": "mr:1223-antonius-galvao-de-franca",
    "mr:1225-maria-ab-apostolis-von-wullenweber": "mr:1225-maria-teresia-von-wullenweber",
    # #84: the Korean given name of St John Pak Hu-jae is printed undeclined
    # ("Ioánnis Pak Hu-jae"); its -ae is not a Latin genitive ending.
    "mr:0903-ioannes-pak-hu-ja-et-socii": "mr:0903-ioannes-pak-hu-jae-et-socii",
    # Old Testament figures keep their title in the ID, as the prophets (-propheta), the
    # apostles (-apostolus) and mr:1229-david-rex-et-propheta: the 2004 Latin calls Abraham
    # patriarcha, Gideon iudex, Melchizedek rex et sacerdos, Aaron sacerdos.
    "mr:1009-abraham": "mr:1009-abraham-patriarcha",
    "mr:0926-gedeon": "mr:0926-gedeon-iudex",
    "mr:0826-melchisedech": "mr:0826-melchisedech-rex-et-sacerdos",
    "mr:0701-aaron": "mr:0701-aaron-sacerdos",
    # Matthew and John keep both titles the 2004 Latin gives them: "Apóstoli et Evangelístæ".
    "mr:0921-matthaeus-apostolus": "mr:0921-matthaeus-apostolus-et-evangelista",
    "mr:1227-ioannes-apostolus": "mr:1227-ioannes-apostolus-et-evangelista",
    # #95: the eulogy names two martyrs, Francisca Xaveria Fenollosa Alcayna and Herminia Martínez Amigó.
    "mr:0927-francisca-xaveria-fenollosa-alcayna": "mr:0927-francisca-xaveria-fenollosa-alcayna-et-herminia-martinez-amigo",
    # #113: the feast of the three archangels, not a saint and his companions.
    "mr:0929-michael-et-socii": "mr:0929-michael-gabriel-et-raphael-archangeli",
    # #116: consecrated persons are named by their secular name (the religious name is the person's
    # other form), unless the religious name is the one they are known by.
    "mr:0102-maria-anna-soureau-blondin": "mr:0102-maria-stella-soureau-blondin",
    "mr:0104-christiana-menabuoi": "mr:0104-oringa-menabuoi",
    "mr:0105-carolus-a-sancto-andrea": "mr:0105-ioannes-andreas-houben",
    "mr:0107-maria-teresia-haze": "mr:0107-ioanna-haze",
    "mr:0109-maria-teresia-a-iesu": "mr:0109-alexia-le-clerc",
    "mr:0110-francisca-salesia-aviat": "mr:0110-leonia-aviat",
    "mr:0111-thomas-de-cora": "mr:0111-franciscus-antonius-placidi",
    "mr:0118-christina-ciccarelli": "mr:0118-matthia-ciccarelli",
    "mr:0118-maria-teresia-fasce": "mr:0118-maria-ioanna-fasce",
    "mr:0120-cyprianus-iwene-tansi": "mr:0120-michael-iwene-tansi",
    "mr:0120-maria-christina-ab-immaculata": "mr:0120-adalheidis-brando",
    "mr:0124-timotheus-giaccardo": "mr:0124-iosephus-giaccardo",
    "mr:0125-archangela-girlani": "mr:0125-eleonora-girlani",
    "mr:0125-maria-antonia-grillo": "mr:0125-teresia-grillo",
    "mr:0126-augustinus-erlandsson": "mr:0126-eystein-erlandsson",
    "mr:0128-olympia-bida": "mr:0128-olga-bida",
    "mr:0130-mucianus-maria-wiaux": "mr:0130-aloysius-wiaux",
    "mr:0201-ioanna-francisca-a-visitatione": "mr:0201-anna-michelotti",
    "mr:0203-maria-a-sancto-ignatio": "mr:0203-claudina-thevenet",
    "mr:0207-maria-a-providentia": "mr:0207-eugenia-smet",
    "mr:0207-rosalia-rendu": "mr:0207-ioanna-maria-rendu",
    "mr:0209-michael-febres-cordero": "mr:0209-franciscus-aloysius-febres-cordero",
    "mr:0211-tobias-borras-romeu": "mr:0211-franciscus-borras-romeu",
    "mr:0213-christina-camozzi": "mr:0213-augustina-camozzi",
    "mr:0213-eustochius-bellinus": "mr:0213-lucretia-bellini",
    "mr:0218-gertrudis-comensoli": "mr:0218-catharina-comensoli",
    "mr:0221-maria-henrica-dominicus": "mr:0221-anna-catharina-dominici",
    "mr:0222-maria-a-iesu": "mr:0222-aemilia-d-oultremont",
    "mr:0223-iosephina-vannini": "mr:0223-iuditta-adelheidis-vannini",
    "mr:0225-maria-adeodata-pisani": "mr:0225-maria-teresia-pisani",
    "mr:0226-pietas-a-cruce": "mr:0226-thomasina-ortiz-real",
    "mr:0227-maria-a-caritate-spiritus-sancti": "mr:0227-carolina-brader",
    "mr:0303-innocentius-de-berzo": "mr:0303-ioannes-scalvinoni",
    "mr:0303-teresia-eustochius-verzeri": "mr:0303-ignatia-verzeri",
    "mr:0304-placida-viel": "mr:0304-eulalia-viel",
    "mr:0305-ieremias-de-valachia": "mr:0305-ioannes-kostistik",
    "mr:0305-ioannes-iosephus-a-cruce": "mr:0305-carolus-caietanus-calosirto",
    "mr:0310-elias-a-succursu": "mr:0310-matthaeus-elias-nieves-del-castillo",
    "mr:0318-martha-le-bouteiller": "mr:0318-amata-le-bouteiller",
    "mr:0324-didacus-iosephus-de-gadibus": "mr:0324-franciscus-iosephus-lopez-caamano",
    "mr:0325-iosaphata-hordashevska": "mr:0325-michaelina-hordashevska",
    "mr:0330-maria-restituta-kafka": "mr:0330-helena-kafka",
    "mr:0402-maria-a-sancto-ioseph": "mr:0402-laura-alvarado",
    "mr:0405-maria-crescentia-hoss": "mr:0405-anna-hoss",
    "mr:0411-angelus-de-clavasio": "mr:0411-antonius-carletti",
    "mr:0412-teresia-a-iesu": "mr:0412-ioanna-fernandez-solar",
    "mr:0413-scubilio-rousseau": "mr:0413-ioannes-bernardus-rousseau",
    "mr:0418-maria-ab-incarnatione": "mr:0418-barbara-avrillot",
    "mr:0420-clara-bosatta": "mr:0420-dina-bosatta",
    "mr:0424-benedictus-menni": "mr:0424-angelus-menni",
    "mr:0424-maria-a-sancta-euphrasia": "mr:0424-rosa-virginia-pelletier",
    "mr:0501-richardus-pampuri": "mr:0501-herminius-philippus-pampuri",
    "mr:0508-maria-catharina-a-sancto-augustino": "mr:0508-catharina-symon-de-longprey",
    "mr:0508-ulrica-nisch": "mr:0508-francisca-nisch",
    "mr:0509-maria-teresia-a-iesu": "mr:0509-carolina-gerhardinger",
    "mr:0518-blandina-merten": "mr:0518-maria-magdalena-merten",
    "mr:0519-ioannes-baptista-xaverius-loir": "mr:0519-ioannes-ludovicus-loir",
    "mr:0519-maria-bernarda-butler": "mr:0519-verena-butler",
    "mr:0525-iacobus-philippus-bertonus": "mr:0525-andreas-bertoni",
    "mr:0529-ursula-ledochowska": "mr:0529-iulia-ledochowska",
    "mr:0531-baptista-varano": "mr:0531-camilla-varano",
    "mr:0531-felix-amoroso": "mr:0531-iacobus-amoroso",
    "mr:0531-marianus-de-roccacasale": "mr:0531-dominicus-di-nicolantonio",
    "mr:0603-didacus-oddi": "mr:0603-iosephus-oddi",
    "mr:0608-nicolaus-de-gesturi": "mr:0608-ioannes-medda",
    "mr:0611-rosa-francisca-maria-a-doloribus": "mr:0611-maria-rosa-molas-vallve",
    "mr:0612-florida-cevoli": "mr:0612-lucretia-helena-cevoli",
    "mr:0616-maria-teresia-scherer": "mr:0616-anna-maria-catharina-scherer",
    "mr:0623-maria-raphaela-cimatti": "mr:0623-sanctina-cimatti",
    "mr:0624-maria-a-guadalupe-garcia-zavala": "mr:0624-anastasia-garcia-zavala",
    "mr:0706-augustinus-iosephus-desgardin": "mr:0706-elias-desgardin",
    "mr:0706-susanna-agatha-de-loye": "mr:0706-maria-rosa-de-loye",
    "mr:0707-iphigenia-a-sancto-matthaeo": "mr:0707-francisca-maria-suzanna-de-gaillard-de-la-valdene",
    "mr:0710-maria-gertrudis-a-sancta-sophia-et-agnes-a-iesu": "mr:0710-maria-gertrudis-a-sancta-sophia-et-sylvia-de-romillon",
    "mr:0712-rosa-a-sancto-xaverio-et-socii": "mr:0712-magdalena-teresia-tallien-et-socii",
    "mr:0713-magdalena-a-matre-dei-et-socii": "mr:0713-elisabeth-verchiere-et-socii",
    "mr:0716-amata-a-iesu-et-socii": "mr:0716-maria-rosa-de-gordon-et-socii",
    "mr:0717-paulus-gojdich": "mr:0717-petrus-gojdich",
    "mr:0717-teresia-a-sancto-augustino-et-socii": "mr:0717-maria-magdalena-claudina-lidoine-et-socii",
    "mr:0718-tarsicia-mackiv": "mr:0718-olga-mackiv",
    "mr:0723-germanus-a-iesu-et-socii": "mr:0723-emmanuel-perez-gimenez-et-socii",
    "mr:0723-nicephorus-a-iesu-et-socii": "mr:0723-vincentius-diez-tejerina-et-socii",
    "mr:0724-maria-a-columna-a-sancto-francisco-borgia-et-socii": "mr:0724-iacoba-martinez-garcia-et-socii",
    "mr:0724-modestinus-a-iesu-et-maria": "mr:0724-dominicus-mazzarello",
    "mr:0725-fridericus-rubio-alvarez-et-socii": "mr:0725-carolus-rubio-alvarez-et-socii",
    "mr:0728-alphonsa-ab-immaculata-conceptione": "mr:0728-anna-muttathupadathu",
    "mr:0728-iacobus-hilarius-barbal-cosan": "mr:0728-emmanuel-barbal-cosan",
    "mr:0730-braulio-maria-corres-diaz-de-cerio-et-socii": "mr:0730-paulus-corres-diaz-de-cerio-et-socii",
    "mr:0731-sidonia-schelingova": "mr:0731-caecilia-schelingova",
    "mr:0801-benvenutus-de-miguel-arahal": "mr:0801-iosephus-de-miguel-arahal",
    "mr:0801-maria-stella-a-sanctissimo-sacramento-et-socii": "mr:0801-adelheidis-mardosewicz-et-socii",
    "mr:0806-maria-francisca-a-iesu": "mr:0806-anna-maria-rubatto",
    "mr:0807-agathangelus-de-vindocino-et-cassianus-de-nannetibus": "mr:0807-franciscus-nourry-et-gundisalvus-vaz-lopez-netto",
    "mr:0808-maria-a-cruce": "mr:0808-maria-helena-mackillop",
    "mr:0808-maria-margarita-caiani": "mr:0808-maria-anna-rosa-caiani",
    "mr:0809-candida-maria-a-iesu": "mr:0809-ioanna-iosepha-cipitria",
    "mr:0809-germanus-garrigues-hernandez": "mr:0809-iosephus-maria-garrigues-hernandez",
    "mr:0809-teresia-benedicta-a-cruce": "mr:0809-editha-stein",
    "mr:0811-ioannes-georgius-rhem": "mr:0811-iacobus-rhem",
    "mr:0812-flavius-argueso-gonzalez": "mr:0812-atilanus-argueso-gonzalez",
    "mr:0813-benildus-romancon": "mr:0813-petrus-romancon",
    "mr:0815-claudius-granzotto": "mr:0815-richardus-granzotto",
    "mr:0815-dominicus-hurtado-soler": "mr:0815-augustinus-hurtado-soler",
    "mr:0815-maria-a-sacrario-a-sancto-aloysio-gonzaga": "mr:0815-elvira-moragas-cantarero",
    "mr:0816-gabriel-sanchis-mompo": "mr:0816-iosephus-maria-sanchis-mompo",
    "mr:0816-petra-a-sancto-ioseph": "mr:0816-anna-iosepha-perez-florido",
    "mr:0822-bernardus-peroni": "mr:0822-dominicus-peroni",
    "mr:0823-ioannes-bourdon": "mr:0823-protasius-bourdon",
    "mr:0823-ioannes-maria-a-cruce": "mr:0823-marianus-garcia-mendez",
    "mr:0823-rosaria-quintana-argos-et-seraphina-fernandez-ibero": "mr:0823-petra-maria-victoria-quintana-argos-et-emmanuela-iusta-fernandez-ibero",
    "mr:0824-maria-ab-incarnatione": "mr:0824-maria-vincentia-rosal",
    "mr:0826-ambrosius-valls-matamales": "mr:0826-aloysius-valls-matamales",
    "mr:0826-laurentia-harasymiv": "mr:0826-leucadia-harasymiv",
    "mr:0826-maria-a-iesu-crucifixo": "mr:0826-maria-baouardy",
    "mr:0826-petrus-max-ginestar": "mr:0826-alexander-max-ginestar",
    "mr:0828-aurelius-ample-alcaide": "mr:0828-iosephus-ample-alcaide",
    "mr:0829-sancia-szymkowiak": "mr:0829-ioannina-szymkowiak",
    "mr:0830-ioachim-ferrer-adell": "mr:0830-iosephus-ferrer-adell",
    "mr:0831-edmigius-primo-rodriguez-et-socii": "mr:0831-isidorus-primo-rodriguez-et-socii",
    "mr:0901-christinus-roca-huguet-et-socii": "mr:0901-michael-roca-huguet-et-socii",
    "mr:0904-bernardus-bieda-grau": "mr:0904-iosephus-bieda-grau",
    "mr:0904-maria": "mr:0904-dina-belanger",
    "mr:0905-teresia-gonhxa-bojaxhiu": "mr:0905-teresia-calcuttae",
    "mr:0908-iosephus-caecilius-rodriguez-gonzalez-et-socii": "mr:0908-bonifatius-rodriguez-gonzalez-et-socii",
    "mr:0909-maria-euthymia-uffing": "mr:0909-emma-uffing",
    "mr:0911-bonaventura-de-barcinone": "mr:0911-michael-gran",
    "mr:0913-aurelius-maria-villalon-acebron": "mr:0913-benvenutus-villalon-acebron",
    "mr:0916-laureanus-ferrer-cardet-et-socii": "mr:0916-salvator-ferrer-cardet-et-socii",
    "mr:0918-ambrosius-chulia-ferrandis-et-valentinus-jaunzaras-gomez": "mr:0918-salvator-chulia-ferrandis-et-socii",
    "mr:0922-ignatius-de-sandone": "mr:0922-laurentius-mauritius-belvisotti",
    "mr:0924-columba-gabriel": "mr:0924-ioanna-gabriel",
    "mr:0925-ioannes-petrus-bengoa-aranguren-et-socii": "mr:0925-iosephus-bengoa-aranguren-et-socii",
    "mr:0926-bonaventura-esteve-flors": "mr:0926-iulius-esteve-flors",
    "mr:0926-leo-legua-martus": "mr:0926-emmanuel-legua-marti",
    "mr:0926-maria-a-refugio-et-maria-a-calvario": "mr:0926-teresia-rosat-balasch-et-iosepha-romero-clariana",
    "mr:0926-teresia-couderc": "mr:0926-maria-victoria-couderc",
    "mr:1002-maria-guadalupe-ricart-olmos": "mr:1002-maria-francisca-ricart-olmos",
    "mr:1005-matthaeus-carreri": "mr:1005-ioannes-franciscus-carreri",
    "mr:1006-maria-francisca-a-vulneribus-domini": "mr:1006-anna-maria-gallo",
    "mr:1009-innocentius-ab-immaculata-et-socii": "mr:1009-emmanuel-canoura-arnau-et-socii",
    "mr:1010-angela-maria-truszkowska": "mr:1010-sophia-camilla-truszkowska",
    "mr:1011-maria-desolata-torres-acosta": "mr:1011-emmanuela-torres-acosta",
    "mr:1012-pacificus-salcedo-puchades": "mr:1012-petrus-salcedo-puchades",
    "mr:1012-seraphinus-de-monte-granario": "mr:1012-felix-de-nicola",
    "mr:1017-maria-natalia-a-sancto-ludovico-et-socii": "mr:1017-maria-ludovica-iosepha-vanot-et-socii",
    "mr:1020-iacobus-kern": "mr:1020-franciscus-alexander-kern",
    "mr:1023-ambrosius-leo-lorente-vicente-et-socii": "mr:1023-petrus-lorente-vicente-et-socii",
    "mr:1023-arnoldus-reche": "mr:1023-iulianus-nicolaus-reche",
    "mr:1023-maria-clotildis-angela-a-sancto-francisco-borgia-et-socii": "mr:1023-clotildis-iosepha-paillot-et-socii",
    "mr:1108-maria-crucifixa-satellico": "mr:1108-elisabeth-maria-satellico",
    "mr:1113-augustina-pietrantoni": "mr:1113-livia-pietrantoni",
    "mr:1115-maria-a-passione": "mr:1115-helena-de-chappotin-de-neuville",
    "mr:1115-raphael-kalinowski": "mr:1115-iosephus-kalinowski",
    "mr:1118-grimoaldus-a-purificatione": "mr:1118-ferdinandus-santamaria",
    "mr:1118-maria-a-refugio-et-socii": "mr:1118-maria-gabriela-hinojosa-y-naveros-et-socii",
    "mr:1120-angela-a-sancto-ioseph-et-socii": "mr:1120-francisca-lloret-marti-et-socii",
    "mr:1120-maria-fortunata-vitus": "mr:1120-anna-felicis-viti",
    "mr:1121-maria-a-iesu-bono-pastore": "mr:1121-francisca-de-siedliska",
    "mr:1122-elias-torrijo-sanchez-et-bertrandus-lahoz-moliner": "mr:1122-iulianus-torrijo-sanchez-et-franciscus-lahoz-moliner",
    "mr:1123-maria-caecilia-cendoya-y-araquistain": "mr:1123-maria-felicitas-cendoya-y-araquistain",
    "mr:1126-humilis-pirozzo": "mr:1126-lucas-antonius-pirozzo",
    "mr:1127-bernardinus-de-fossa": "mr:1127-ioannes-amici",
    "mr:1128-ioannes-iesu-adradas-gonzalo-et-socii": "mr:1128-marianus-adradas-gonzalo-et-socii",
    "mr:1129-dionysius-a-nativitate-et-redemptus-a-cruce": "mr:1129-petrus-berthelot-et-thomas-rodriguez",
    "mr:1201-liduina-meneguzzi": "mr:1201-helisa-angela-meneguzzi",
    "mr:1202-raphael-chylinski": "mr:1202-melchior-chylinski",
    "mr:1207-maria-iosepha-rossello": "mr:1207-benedicta-rossello",
    "mr:1209-bernardus-maria-a-iesu": "mr:1209-caesar-silvestrelli",
    "mr:1213-ioannes-marinoni": "mr:1213-franciscus-marinoni",
    "mr:1214-protasius-cubells-minguell": "mr:1214-antonius-cubells-minguell",
    "mr:1216-honoratus-kazminsky": "mr:1216-florentius-kazminsky",
    "mr:1216-maria-ab-angelis": "mr:1216-marianna-fontanella",
    "mr:1216-sebastianus-de-madiis": "mr:1216-salvaticus-de-madiis",
    "mr:1217-hyacinthus-cormier": "mr:1217-henricus-cormier",
    "mr:1218-nemesia-valle": "mr:1218-iulia-valle",
    "mr:1224-paula-elisabeth-cerioli": "mr:1224-constantia-cerioli",
    "mr:1225-maria-ab-apostolis": "mr:1225-maria-teresia-von-wullenweber",
}

# Days whose opening elogia are printed as unnumbered drop-cap paragraphs in
# both editions (celebrations with liturgical rank: solemnities, feasts,
# memorias — including days with two or three memorias). Maps (month, day) ->
# number of unnumbered leading entries; the printed numbering counts them
# implicitly, so the workbook entry numbers stay aligned. Derived mechanically
# from the full-corpus sweep of both OCR layers (July 2026).
UNNUMBERED_LEADS = {
    (1, 1): 1, (1, 2): 1, (1, 3): 1, (1, 6): 1, (1, 7): 1, (1, 13): 1,
    (1, 17): 1, (1, 20): 2, (1, 21): 1, (1, 22): 1, (1, 24): 1, (1, 25): 1,
    (1, 26): 1, (1, 27): 1, (1, 28): 1, (1, 31): 1, (2, 2): 1, (2, 3): 2,
    (2, 5): 1, (2, 6): 1, (2, 8): 2, (2, 10): 1, (2, 11): 1, (2, 14): 1,
    (2, 17): 1, (2, 21): 1, (2, 22): 1, (2, 23): 1, (3, 4): 1, (3, 7): 1,
    (3, 8): 1, (3, 9): 1, (3, 17): 1, (3, 18): 1, (3, 19): 1, (3, 23): 1,
    (3, 25): 1, (4, 2): 1, (4, 4): 1, (4, 5): 1, (4, 7): 1, (4, 11): 1,
    (4, 13): 1, (4, 21): 1, (4, 23): 2, (4, 24): 1, (4, 25): 1, (4, 28): 2,
    (4, 29): 1, (4, 30): 1, (5, 1): 1, (5, 2): 1, (5, 3): 1, (5, 12): 2,
    (5, 13): 1, (5, 14): 1, (5, 18): 1, (5, 20): 1, (5, 21): 1, (5, 22): 1,
    (5, 25): 3, (5, 26): 1, (5, 27): 1, (5, 31): 1, (6, 1): 1, (6, 2): 1,
    (6, 3): 1, (6, 5): 1, (6, 6): 1, (6, 9): 1, (6, 11): 1, (6, 13): 1,
    (6, 19): 1, (6, 21): 1, (6, 22): 2, (6, 24): 1, (6, 27): 1, (6, 28): 1,
    (6, 29): 1, (6, 30): 1, (7, 3): 1, (7, 4): 1, (7, 5): 1, (7, 6): 1,
    (7, 9): 1, (7, 11): 1, (7, 13): 1, (7, 14): 1, (7, 15): 1, (7, 16): 1,
    (7, 20): 1, (7, 21): 1, (7, 22): 1, (7, 23): 1, (7, 24): 1, (7, 25): 1,
    (7, 26): 1, (7, 29): 1, (7, 30): 1, (7, 31): 1, (8, 1): 1, (8, 2): 2,
    (8, 4): 1, (8, 5): 1, (8, 6): 1, (8, 7): 2, (8, 8): 1, (8, 9): 1,
    (8, 10): 1, (8, 11): 1, (8, 12): 1, (8, 13): 1, (8, 14): 1, (8, 15): 1,
    (8, 16): 1, (8, 19): 1, (8, 20): 1, (8, 21): 1, (8, 22): 1, (8, 23): 1,
    (8, 24): 1, (8, 25): 2, (8, 27): 1, (8, 28): 1, (8, 29): 1, (9, 3): 1,
    (9, 8): 1, (9, 9): 1, (9, 12): 1, (9, 13): 1, (9, 14): 1, (9, 15): 1,
    (9, 16): 1, (9, 17): 1, (9, 19): 1, (9, 20): 1, (9, 21): 1, (9, 23): 1,
    (9, 26): 1, (9, 27): 1, (9, 28): 2, (9, 29): 1, (9, 30): 1, (10, 1): 1,
    (10, 2): 1, (10, 4): 1, (10, 6): 1, (10, 7): 1, (10, 9): 2, (10, 14): 1,
    (10, 15): 1, (10, 16): 2, (10, 17): 1, (10, 18): 1, (10, 19): 2, (10, 23): 1,
    (10, 24): 1, (10, 28): 1, (11, 1): 1, (11, 2): 1, (11, 3): 1, (11, 4): 1,
    (11, 9): 1, (11, 10): 1, (11, 11): 1, (11, 12): 1, (11, 15): 1, (11, 16): 2,
    (11, 17): 1, (11, 18): 1, (11, 21): 1, (11, 22): 1, (11, 23): 2, (11, 24): 1,
    (11, 25): 1, (11, 30): 1, (12, 3): 1, (12, 4): 1, (12, 6): 1, (12, 7): 1,
    (12, 8): 1, (12, 9): 1, (12, 11): 1, (12, 12): 1, (12, 13): 1, (12, 14): 1,
    (12, 21): 1, (12, 23): 1, (12, 25): 1, (12, 26): 1, (12, 27): 1, (12, 28): 1,
    (12, 29): 1, (12, 31): 1,
}

# Placement overrides: the digitized workbook records the Italian (CEI)
# placement, but the anchor edition (the Latin editio altera 2004 print)
# places the elogium on a different day. Maps corrected ID -> (month, day,
# entry, note). None remain: a eulogy printed on different days in different
# editions now has one ID per day (see SAME_EULOGY).
PLACEMENT_OVERRIDES = {}

# Entries present in the Italian (CEI) edition and the digitized workbook but
# absent from the Latin editio altera 2004 print (all verified on the page
# scans of both editions, July 2026).
ENTRY_NOTES = {
    # 1749/1914 source errors and identity remarks found in the #51 audit (set 6, reviewed).
    "mr:1003-candida": (
        "The 1749 and 1914 editions commemorate a male martyr, Candidus; the 2004 edition has "
        "Candida, a woman, in the cemetery of Pontianus. It is probably the 2004 correction of "
        "the same commemoration."
    ),
    "mr:1105-theotimus-et-socii": (
        "In the 1749 and 1914 editions this eulogy opens with Domninus, whom the 2004 edition "
        "commemorates separately (mr:1105-domninus); the rest of the group is Theotimus and "
        "companions."
    ),
    # Acts after the 2004 edition (martyrology-texts#153, sections B and C): canonizations of
    # those it styles blessed, a Doctor of the Church, a feast raised in the General Calendar. The
    # texts stay as printed until an official edition revises them; the note records the act.
    "mr:0101-sigismundus-gorazdowski": "Zygmunt Gorazdowski, blessed in the 2004 editions, was canonized on 23 October 2005.",
    "mr:0103-cyriacus-elias-chavara": "Kuriakose Elias Chavara, blessed in the 2004 editions, was canonized on 23 November 2014.",
    "mr:0104-angela": "Angela of Foligno, blessed in the 2004 editions, was canonized on 9 October 2013.",
    "mr:0105-ioannes-andreas-houben": "Charles of St Andrew (Houben), blessed in the 2004 editions, was canonized on 3 June 2007.",
    "mr:0106-andreas-bessette": "André Bessette, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0116-iosephus-vaz": "Joseph Vaz, blessed in the 2004 editions, was canonized on 14 January 2015.",
    "mr:0120-adalheidis-brando": (
        "Maria Cristina of the Immaculate Conception Brando, blessed in the 2004 editions, was canonized on "
        "17 May 2015."
    ),
    "mr:0202-maria-catharina-kasper": "Maria Katharina Kasper, blessed in the 2004 editions, was canonized on 14 October 2018.",
    "mr:0202-maria-dominica-mantovani": "Maria Domenica Mantovani, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0202-nicolaus-saggio-de-langobardis": "Nicola Saggio of Longobardi, blessed in the 2004 editions, was canonized on 23 November 2014.",
    "mr:0203-maria-anna-rivier": "Marie Rivier, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0206-alphonsus-maria-fusco": "Alfonso Maria Fusco, blessed in the 2004 editions, was canonized on 16 October 2016.",
    "mr:0206-franciscus-spinelli": "Francesco Spinelli, blessed in the 2004 editions, was canonized on 14 October 2018.",
    "mr:0216-iosephus-allamano": "Giuseppe Allamano, blessed in the 2004 editions, was canonized on 20 October 2024.",
    "mr:0218-catharina-comensoli": "Geltrude Comensoli, blessed in the 2004 editions, was canonized on 26 April 2009.",
    "mr:0220-hyacintha-marto": "Jacinta Marto, blessed in the 2004 editions, was canonized on 13 May 2017.",
    "mr:0223-iuditta-adelheidis-vannini": "Giuseppina Vannini, blessed in the 2004 editions, was canonized on 13 October 2019.",
    "mr:0304-ioannes-antonius-farina": "Giovanni Antonio Farina, blessed in the 2004 editions, was canonized on 23 November 2014.",
    "mr:0308-faustinus-miguez": "Faustino Míguez, blessed in the 2004 editions, was canonized on 15 October 2017.",
    "mr:0310-maria-eugenia-milleret-de-brou": "Marie-Eugénie of Jesus Milleret, blessed in the 2004 editions, was canonized on 3 June 2007.",
    "mr:0315-artemidis-zatti": "Artemide Zatti, blessed in the 2004 editions, was canonized on 9 October 2022.",
    "mr:0320-iosephus-bilczewski": "Józef Bilczewski, blessed in the 2004 editions, was canonized on 23 October 2005.",
    "mr:0330-ludovicus-de-casaurea": "Ludovico of Casoria (Palmentieri), blessed in the 2004 editions, was canonized on 23 November 2014.",
    "mr:0401-ludovicus-pavonus": "Lodovico Pavoni, blessed in the 2004 editions, was canonized on 16 October 2016.",
    "mr:0402-didacus-aloysius-de-san-vitores-et-petrus-calungsod": "Pedro Calungsod, blessed in the 2004 editions, was canonized on 21 October 2012.",
    "mr:0402-franciscus-coll": "Francisco Coll y Guitart, blessed in the 2004 editions, was canonized on 11 October 2009.",
    "mr:0404-caietanus-catanoso": "Gaetano Catanoso, blessed in the 2004 editions, was canonized on 23 October 2005.",
    "mr:0404-franciscus-marto": "Francisco Marto, blessed in the 2004 editions, was canonized on 13 May 2017.",
    "mr:0411-helena-guerra": "Elena Guerra, blessed in the 2004 editions, was canonized on 20 October 2024.",
    "mr:0413-margarita": "Margaret of Città di Castello, blessed in the 2004 editions, was canonized on 24 April 2021.",
    "mr:0415-caesar-de-bus": "César de Bus, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0415-damianus-de-veuster": "Damien de Veuster, blessed in the 2004 editions, was canonized on 11 October 2009.",
    "mr:0417-catharina-tekakwitha": "Kateri Tekakwitha, blessed in the 2004 editions, was canonized on 21 October 2012.",
    "mr:0424-maria-elisabeth-hesselblad": "Maria Elisabeth Hesselblad, blessed in the 2004 editions, was canonized on 5 June 2016.",
    "mr:0425-ioannes-piamarta": "Giovanni Battista Piamarta, blessed in the 2004 editions, was canonized on 21 October 2012.",
    "mr:0426-raphael-arnaiz-baron": "Rafael Arnáiz Barón, blessed in the 2004 editions, was canonized on 11 October 2009.",
    "mr:0430-maria-ab-incarnatione": "Marie of the Incarnation Guyart, blessed in the 2004 editions, was canonized on 3 April 2014.",
    "mr:0503-maria-leonia-paradis": "Marie-Léonie Paradis, blessed in the 2004 editions, was canonized on 20 October 2024.",
    "mr:0503-stanislaus": "Stanisław Kazimierczyk, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0505-nuntius-sulprizio": "Nunzio Sulprizio, blessed in the 2004 editions, was canonized on 14 October 2018.",
    "mr:0506-franciscus-de-montmorency-laval": "François de Montmorency-Laval, blessed in the 2004 editions, was canonized on 3 April 2014.",
    "mr:0507-rosa-venerini": "Rosa Venerini, blessed in the 2004 editions, was canonized on 15 October 2006.",
    "mr:0508-amatus-ronconi": "Amato Ronconi, blessed in the 2004 editions, was canonized on 23 November 2014.",
    "mr:0514-theodora-guerin": "Théodore Guérin, blessed in the 2004 editions, was canonized on 15 October 2006.",
    "mr:0517-iulia-salzano": "Giulia Salzano, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0519-verena-butler": "Maria Bernarda Bütler, blessed in the 2004 editions, was canonized on 12 October 2008.",
    "mr:0520-archangelus-tadini": "Arcangelo Tadini, blessed in the 2004 editions, was canonized on 26 April 2009.",
    "mr:0531-camilla-varano": "Camilla Battista da Varano, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0531-iacobus-amoroso": "Felix of Nicosia (Felice Amoroso), blessed in the 2004 editions, was canonized on 23 October 2005.",
    "mr:0601-ioannes-baptista-scalabrinus": "Giovanni Battista Scalabrini, blessed in the 2004 editions, was canonized on 9 October 2022.",
    "mr:0603-ioannes-xxiii": (
        "Pope John XXIII, blessed in the 2004 editions, was canonized on 27 April 2014; on 29 May 2014 his "
        "optional memorial was inscribed in the General Roman Calendar on 11 October."
    ),
    "mr:0604-philippus-smaldone": "Filippo Smaldone, blessed in the 2004 editions, was canonized on 15 October 2006.",
    "mr:0606-raphael-guizar-valencia": "Rafael Guízar Valencia, blessed in the 2004 editions, was canonized on 15 October 2006.",
    "mr:0608-iacobus-berthieu": "Jacques Berthieu, blessed in the 2004 editions, was canonized on 21 October 2012.",
    "mr:0608-maria-teresia-chiramel-mankidiyan": "Mariam Thresia Chiramel Mankidiyan, blessed in the 2004 editions, was canonized on 13 October 2019.",
    "mr:0609-iosephus-anchieta": "José de Anchieta, blessed in the 2004 editions, was canonized on 3 April 2014.",
    "mr:0611-ignatius-maloyan": "Ignatius Maloyan, blessed in the 2004 editions, was canonized on 19 October 2025.",
    "mr:0615-aloysius-maria-palazzolo": "Luigi Maria Palazzolo, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0624-anastasia-garcia-zavala": "María Guadalupe García Zavala, blessed in the 2004 editions, was canonized on 12 May 2013.",
    "mr:0627-margarita-bays": "Marguerite Bays, blessed in the 2004 editions, was canonized on 13 October 2019.",
    "mr:0628-irenaeus": "Irenaeus was declared a Doctor of the Church on 21 January 2022.",
    "mr:0704-petrus-georgius-frassati": "Pier Giorgio Frassati, blessed in the 2004 editions, was canonized on 7 September 2025.",
    "mr:0706-nazaria-a-sancta-teresia": (
        "Nazaria Ignacia of St Teresa of Jesus March Mesa, blessed in the 2004 editions, was canonized on 14 "
        "October 2018."
    ),
    "mr:0707-petrus-to-rot": "Peter To Rot, blessed in the 2004 editions, was canonized on 19 October 2025.",
    "mr:0710-emmanuel-ruiz-et-socii": (
        "Manuel Ruiz and his ten companions, the martyrs of Damascus, blessed in the 2004 editions, were "
        "canonized on 20 October 2024."
    ),
    "mr:0716-andreas-de-soveral-et-dominicus-carvalho": (
        "The martyrs of Brazil, André de Soveral, Ambrósio Francisco Ferro and their 28 companions, blessed "
        "in the 2004 editions, were canonized on 15 October 2017."
    ),
    "mr:0716-bartholomaeus-a-martyribus": "Bartholomew of the Martyrs (Fernandes), blessed in the 2004 editions, was canonized on 5 July 2019.",
    "mr:0717-maria-magdalena-claudina-lidoine-et-socii": (
        "Teresa of St Augustine and her fifteen companions, the martyrs of Compiègne, blessed in the 2004 "
        "editions, were canonized on 18 December 2024."
    ),
    "mr:0718-simon-de-lipnica": "Simon of Lipnica, blessed in the 2004 editions, was canonized on 3 June 2007.",
    "mr:0722-maria-magdalena": (
        "By decree of 3 June 2016 the celebration of Mary Magdalene in the General Roman Calendar was raised "
        "from an obligatory memorial to a feast."
    ),
    "mr:0725-maria-a-monte-carmelo-salles-y-barangueras": (
        "María del Monte Carmelo Sallés y Barangueras, blessed in the 2004 editions, was canonized on 21 "
        "October 2012."
    ),
    "mr:0726-georgius-preca": "George Preca, blessed in the 2004 editions, was canonized on 3 June 2007.",
    "mr:0726-titus-brandsma": "Titus Brandsma, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0728-anna-muttathupadathu": (
        "Alphonsa of the Immaculate Conception, blessed in the 2004 editions, was canonized on 12 October "
        "2008."
    ),
    "mr:0801-petrus-favre": "Peter Faber, blessed in the 2004 editions, was canonized on 17 December 2013.",
    "mr:0806-anna-maria-rubatto": "Maria Francesca of Jesus Rubatto, blessed in the 2004 editions, was canonized on 15 May 2022.",
    "mr:0808-bonifatia-rodriguez-castro": "Bonifacia Rodríguez de Castro, blessed in the 2004 editions, was canonized on 23 October 2011.",
    "mr:0808-maria-helena-mackillop": "Mary of the Cross MacKillop, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0809-ioanna-iosepha-cipitria": "Cándida María de Jesús Cipitria, blessed in the 2004 editions, was canonized on 17 October 2010.",
    "mr:0814-octingenti-martyres-hydrunti": (
        "Antonio Primaldo and his companions, the martyrs of Otranto, blessed in the 2004 editions, were "
        "canonized on 12 May 2013."
    ),
    "mr:0818-albertus-hurtado-cruchaga": "Alberto Hurtado Cruchaga, blessed in the 2004 editions, was canonized on 23 October 2005.",
    "mr:0820-bernardus-tolomei": "Bernardo Tolomei, blessed in the 2004 editions, was canonized on 26 April 2009.",
    "mr:0826-maria-baouardy": (
        "Mary of Jesus Crucified (Mariam Baouardy), blessed in the 2004 editions, was canonized on 17 May "
        "2015."
    ),
    "mr:0828-iuniperus-serra": "Junípero Serra, blessed in the 2004 editions, was canonized on 23 September 2015.",
    "mr:0829-ioanna-jugan": "Jeanne Jugan (Marie de la Croix), blessed in the 2004 editions, was canonized on 11 October 2009.",
    "mr:0902-ioannes-maria-du-lau-et-socii": (
        "Salomon Leclercq, one of these martyrs, blessed in the 2004 editions, was canonized on 16 October "
        "2016."
    ),
    "mr:0917-sigismundus-felix-felinski": "Zygmunt Szczęsny Feliński, blessed in the 2004 editions, was canonized on 11 October 2009.",
    "mr:0923-christophorus-et-socii": (
        "Cristóbal, Antonio and Juan, the child martyrs of Tlaxcala, blessed in the 2004 editions, were "
        "canonized on 15 October 2017."
    ),
    "mr:1003-ambrosius-franciscus-ferro-et-socii": (
        "The martyrs of Brazil, André de Soveral, Ambrósio Francisco Ferro and their 28 companions, blessed "
        "in the 2004 editions, were canonized on 15 October 2017."
    ),
    "mr:1005-anna-schaffer": "Anna Schäffer, blessed in the 2004 editions, was canonized on 21 October 2012.",
    "mr:1005-bartholomaeus-longo": "Bartolo Longo, blessed in the 2004 editions, was canonized on 19 October 2025.",
    "mr:1021-laura-montoya-y-upegui": (
        "Laura of St Catherine of Siena Montoya y Upegui, blessed in the 2004 editions, was canonized on 12 "
        "May 2013."
    ),
    "mr:1024-aloysius-guanella": "Luigi Guanella, blessed in the 2004 editions, was canonized on 23 October 2011.",
    "mr:1029-caietanus-errico": "Gaetano Errico, blessed in the 2004 editions, was canonized on 12 October 2008.",
    "mr:1030-angelus": "Angelo of Acri, blessed in the 2004 editions, was canonized on 15 October 2017.",
    "mr:1101-nonius-alvarez-pereira": "Nuno de Santa Maria Álvares Pereira, blessed in the 2004 editions, was canonized on 26 April 2009.",
    "mr:1105-guido-maria-conforti": "Guido Maria Conforti, blessed in the 2004 editions, was canonized on 23 October 2011.",
    "mr:1107-vincentius-grossi": "Vincenzo Grossi, blessed in the 2004 editions, was canonized on 18 October 2015.",
    "mr:1109-elisabeth-a-sanctissima-trinitate": "Elizabeth of the Trinity (Catez), blessed in the 2004 editions, was canonized on 16 October 2016.",
    "mr:1208-narcissa-a-iesu-martillo-moran": "Narcisa de Jesús Martillo Morán, blessed in the 2004 editions, was canonized on 12 October 2008.",
    "mr:1220-vincentius-romano": "Vincenzo Romano, blessed in the 2004 editions, was canonized on 14 October 2018.",
    "mr:1223-antonius-galvao-de-franca": "Anthony of St Anne Galvão, blessed in the 2004 editions, was canonized on 11 May 2007.",
    "mr:1228-catharina-volpicelli": "Caterina Volpicelli, blessed in the 2004 editions, was canonized on 26 April 2009.",
}

# Asterisk overrides where the digitized workbook follows the Italian (CEI)
# edition but the anchor edition (the Latin editio altera 2004 print) differs.
# All were verified against the page scans of BOTH printed editions (2026-07),
# independently of the workbook: asterisk-presence claims via the OCR text
# layer with visual spot-checks, asterisk-absence claims each visually
# confirmed on the scan of the edition concerned.

# Entries asterisked in the Latin print but not in the CEI edition (nor in the
# workbook). Maps ID -> entry number as printed in the Latin editio altera.
LATIN_ASTERISKED = {
    "mr:0104-ferreolus": 4,
    "mr:0104-rigomerus": 5,
    "mr:0104-pharaildis": 7,
    "mr:0122-ladislaus-batthyany-strattmann": 15,
    "mr:0502-boleslaus-strzelecki": 12,
    "mr:0512-imelda-lambertini": 10,
    "mr:0524-servulus": 4,
    "mr:0611-bardo": 4,
    "mr:0624-gohardus": 7,
    "mr:0711-leontius": 5,
    "mr:0718-olga-mackiv": 13,
    "mr:0730-godeleva": 6,
    "mr:0802-betharius": 8,
    "mr:0807-donatus-vesontione": 7,
    "mr:0909-franciscus-garate-aranguren": 10,
    "mr:1021-wendelinus": 8,
    "mr:1026-eata": 7,
    "mr:1103-libertinus": 3,
    "mr:1103-odrada": 10,
    "mr:1118-theofredus": 6,
    "mr:1119-eudo": 6,
    "mr:1215-marinus": 3,
    "mr:1230-egwinus": 7,
}

# Entries with a plain number in the Latin print that the CEI edition (and the
# workbook) marks with an asterisk. Maps ID -> entry number in the Latin print.
LATIN_PLAIN = {
    "mr:0323-rebecca-de-himlaya": 11,
    "mr:0812-iacobus-do-mai-nam-et-socii": 11,
    "mr:0821-iosephus-dang-dinh-vien": 11,
    "mr:1201-domnolus": 5,
    "mr:1203-lucius": 5,
    "mr:1212-simon-phan-dac-hoa": 11,
}

# Country codes the workbook got wrong (issue #8). `country` is the modern
# country of the place of the elogium: the place-lead when there is one,
# otherwise the place of death. The actual location wins over the printed
# text when the text names the wrong modern country. Most workbook errors come
# from homonymous places resolved to the wrong country (Guadalajara, Eger,
# Nizza, Montserrat → MS, the British overseas territory).
COUNTRY_CORRECTIONS = {
    "mr:0131-eusebius": "AT",  # Viktorsberg near Rankweil, Vorarlberg
    "mr:0217-evermodus": "DE",  # Ratzeburg
    "mr:0615-isfridus": "DE",  # Ratzeburg
    "mr:0715-ansuerus": "DE",  # Ratzeburg
    "mr:1212-vicelinus": "DE",  # Neumünster
    "mr:1115-albertus-magnus": "DE",  # no place-lead; died in Cologne
    "mr:0714-hroznata": "CZ",  # Starý Kynšperk near Cheb (Eger), Bohemia
    "mr:0626-iosephus-maria-robles": "MX",  # near Guadalajara, Jalisco
    "mr:0724-iacoba-martinez-garcia-et-socii": "ES",  # Guadalajara, Spain
    "mr:0830-iosephus-ferrer-adell": "ES",  # Castellón de la Plana
    "mr:1125-hyacinthus-serrano-lopez": "ES",  # Puebla de Híjar near Teruel
    "mr:0825-maria-a-transitu-iesu-sacramenti": "AR",  # Córdoba, Argentina
    "mr:0320-nicetas": "AL",  # Pojani (Apollonia)
    "mr:0731-ignatius-de-loyola": "IT",  # no place-lead; died in Rome
    "mr:0226-paula-a-sancto-iosepho-de-calasanz": "ES",  # Olesa de Montserrat
    "mr:0918-salvator-chulia-ferrandis-et-socii": "ES",  # Montserrat, Catalonia
    "mr:0707-petrus-to-rot": "PG",  # Rakunai, New Britain
    "mr:0514-maria-dominica-mazzarello": "IT",  # Nizza Monferrato, not Nice
    "mr:0626-andreas-hyacinthus-longhin": "IT",  # Treviso
    "mr:1225-anastasia": "IT",  # place-lead "A Roma" (Sirmium is in Serbia)
    "mr:1011-meinardus": "LV",  # Ikšķile near Riga
    "mr:0622-paulinus": "IT",  # no place-lead; Nola
    "mr:1123-columbanus": "IT",  # no place-lead; died at Bobbio
    "mr:0716-reinildis-et-socii": "BE",  # Saintes, Hainaut
    "mr:0706-goaris": "DE",  # Sankt Goar
    "mr:1103-pirminus": "DE",  # Hornbach
    "mr:0724-ludovica": "CH",  # Orbe, Vaud
    "mr:0921-franciscus-jaccard-et-thomas-tran-van-thien": "VN",  # Quảng Trị
    "mr:1124-petrus-dumoulin-borie-et-socii": "VN",  # Đồng Hới
    "mr:0504-florianus": "AT",  # Lorch/Enns (text says "odierna Germania")
    "mr:0304-casimirus": "BY",  # died at Grodno (text says "in Lituania")
    "mr:0603-morandus": "FR",  # Altkirch, Alsace (text says "odierna Svizzera")
    "mr:0827-gebhardus": "DE",  # Petershausen, Konstanz (text says "odierna Svizzera")
    "mr:0913-amatus-broili": "FR",  # died at Breuil-sur-le-Lys; Sion is only his see
}

# The Latin print's asterisk where the CEI's differs; each difference is a note on both editions
# (PLACEMENT_EDITION_NOTES, after EDITION_NOTES).
ASTERISK_OVERRIDES = {_id: True for _id in LATIN_ASTERISKED} | {_id: False for _id in LATIN_PLAIN}

# Entries present in the editio altera 2004 print but absent from the
# digitized "with IDs" workbook (see docs/canonicalization-report.md). Both
# are present in the parallel-texts workbook, whose reviewer comments document
# their numbering across editions.
PRINT_ONLY_ENTRIES = [
    {
        "id": "mr:0104-abrunculus",
        "month": 1,
        "day": 4,
        "entry": 2,
        "asterisk": True,
        "country": "FR",
        "editions": {"martyrologium_romanum_2004_it_IT": {"absent": True}},
    },
    {
        "id": "mr:0104-emmanuel-gonzalez-garcia",
        "month": 1,
        "day": 4,
        "entry": 12,
        "asterisk": True,
        "country": "ES",
        # Its CEI number (11*) follows from Abrunculus's absence there, as for the day's whole series.
        "note": "Manuel González García, blessed in the 2004 editions, was canonized on 16 October 2016.",
        "editions": {"martyrologium_romanum_2004_it_IT": {"entry": 11}},
    },
    {
        "id": "mr:0610-marcus-antonius-durando",
        "month": 6,
        "day": 10,
        "entry": 9,
        "asterisk": True,
        "country": "IT",
        "editions": {"martyrologium_romanum_2004_it_IT": {"absent": True}},
    },
]

# The 2004-family editions. The registry's main placement is the Latin print;
# `editions` records where another edition differs (see
# docs/canonicalization-report.md, Per-edition placements).
EDITION_LA = "martyrologium_romanum_2004"
EDITION_IT = "martyrologium_romanum_2004_it_IT"
EDITION_EN = "martyrologium_romanum_2004_en_unofficial"
EDITIONS_2004 = (EDITION_LA, EDITION_IT, EDITION_EN)
OVERRIDE_KEYS = {"entry", "asterisk", "unnumbered", "absent"}
# The historical editions (their texts live in martyrology-api).
EDITION_1630 = "martyrologium_romanum_1630"
EDITION_1749 = "martyrologium_romanum_1749"
EDITION_1914 = "martyrologium_romanum_1914_en_unofficial"
EDITION_LABELS = {
    EDITION_LA: "2004 Latin", EDITION_IT: "2004 Italian", EDITION_EN: "2004 English",
    EDITION_1630: "1630 Latin", EDITION_1749: "1749 Latin", EDITION_1914: "1914 English",
}

# A curator's note that concerns one edition's text only (a mistranslation, a
# misprint, a dropped line): `edition_notes` on the entry, shown with that
# edition alone; `note` (ENTRY_NOTES) is for remarks about the eulogy itself.
# Deprecated IDs carry theirs in data/deprecated_ids.json.
EDITION_NOTES = {
    "mr:0920-andreas-kim-tae-gon-et-socii": {
        EDITION_EN: (
            "Translation error: \"ten of whom are commemorated on this day\" where the Latin says "
            "that all one hundred and three martyrs are celebrated together on this day."
        ),
    },
    "mr:0926-sebastianus-nam-i-gwan-et-socii": {
        EDITION_EN: (
            "Translation error: \"twelve martyrs\" where the Latin has \"novem sociórum, mártyrum\" "
            "(nine companions, martyrs: ten in all)."
        ),
    },
    "mr:1124-andreas-dung-lac-et-socii": {
        EDITION_LA: (
            "Misprint: footnote 1 prints \"Emmanuel Lê Văn Phụng\" twice in a row; he is one martyr, "
            "listed once in the index of names. The list also seems to leave out Bishop Stephanus "
            "Theodorus Cuénot, one of the 117 martyrs canonized together: with Andreas Dũng Lạc it "
            "names 116, and the index gives Cuénot only his own day (14 November), though martyrs "
            "with a day of their own, such as Emmanuel Lê Văn Phụng (13 July), are listed here too."
        ),
    },
    "mr:1124-balsamus": {
        EDITION_EN: (
            "Omission: the text breaks off after \"amid troubles and conflicts\"; the Latin "
            "continues \"ætátis suæ cum sapiéntia et prudéntia múnere suo functus est\" (of his "
            "time, he discharged his office with wisdom and prudence)."
        ),
    },
    "mr:0104-thomas-plumtree": {
        EDITION_EN: (
            "Translation error: \"choosing the noose over the axe\" where the Latin \"láquei pœnam "
            "... pro vita máluit\" says he preferred the noose to his life."
        ),
    },
    "mr:0107-canutus-lavard": {
        EDITION_EN: (
            "Translation error: \"martyr\" is added; the Latin does not call him a martyr."
        ),
    },
    "mr:0108-laurentius-giustiniani": {
        EDITION_EN: (
            "Translation error: \"the wisdom of reform and doctrine\" where the Latin has \"doctrína "
            "ætérnæ sapiéntiæ\" (the teaching of eternal wisdom)."
        ),
    },
    "mr:0110-leonia-aviat": {
        EDITION_EN: (
            "Translation error: \"Francis de Sales\" where the Latin \"Francíscæ Salésiæ\" is the "
            "feminine Frances de Sales."
        ),
    },
    "mr:0112-arcadius": {
        EDITION_EN: (
            "Translation error: the city is omitted; the Latin has \"Cæsaréæ in Mauretánia\" (at "
            "Caesarea in Mauretania)."
        ),
    },
    "mr:0113-iutta": {
        EDITION_EN: (
            "Translation error: \"Lutgardis\" where the Latin has \"Iuttæ\" (Jutta, or Ivetta, of "
            "Huy)."
        ),
    },
    "mr:0117-rosselina": {
        EDITION_EN: (
            "Translation error: \"Forcalquier\" where the Latin has \"Forum Iúlii\" (Fréjus)."
        ),
    },
    "mr:0119-launomarus": {
        EDITION_EN: (
            "Translation error: \"the monastery of Corbie\" where the Latin has \"monastérii "
            "Corbionénsis\" (Corbion)."
        ),
    },
    "mr:0120-benedictus-ricasoli": {
        EDITION_EN: (
            "Translation error: \"Coltevalenza\" where the Latin has \"Coltibóni\" (Coltibuono)."
        ),
    },
    "mr:0121-ioannes-yi-yun-il": {
        EDITION_EN: (
            "Translation error: \"one of the last victims\" where the Latin has \"última ... "
            "víctima\" (the last victim)."
        ),
    },
    "mr:0124-exsuperantius": {
        EDITION_EN: (
            "Translation error: adds \"who faithfully shepherded his people and is venerated for "
            "his holiness and pastoral zeal\", which is not in the Latin."
        ),
    },
    "mr:0124-felicianus": {
        EDITION_EN: (
            "Translation error: adds \"a faithful guardian of the flock entrusted to him\", which "
            "is not in the Latin."
        ),
    },
    "mr:0124-sabinianus": {
        EDITION_EN: (
            "Translation error: adds \"who bore witness to Christ through the shedding of his "
            "blood\", which is not in the Latin."
        ),
    },
    "mr:0127-theodoricus": {
        EDITION_EN: (
            "Translation error: \"Ternand\" where the Latin has \"Ternodóri\" (Tonnerre)."
        ),
    },
    "mr:0130-carmela-garcia-moyon": {
        EDITION_EN: (
            "Translation error: omits \"violáta\": she was violated before being burned alive."
        ),
    },
    "mr:0131-eusebius": {
        EDITION_EN: (
            "Translation error: \"Regensburg\" where the Latin has \"Rangvílam\" (Rankweil)."
        ),
    },
    "mr:0131-marcella": {
        EDITION_EN: (
            "Translation error: \"Marcellina\" where the Latin has \"Marcéllæ\" (Marcella)."
        ),
    },
    "mr:0131-waldus": {
        EDITION_EN: (
            "Translation error: \"Constance\" where the Latin has \"Constantiénsi\" (Coutances)."
        ),
    },
    "mr:0201-agrippanus": {
        EDITION_EN: (
            "Translation error: \"returning to Rome from the borders of Velacum\" where the Latin "
            "has \"Roma ad fines Velacórum revértens\" (returning from Rome to the Velay)."
        ),
    },
    "mr:0201-andreas-de-comitibus-signiae": {
        EDITION_EN: (
            "Translation error: \"Counts of Signore\" where the Latin has \"de Comítibus Sígniæ\" "
            "(the Counts of Segni)."
        ),
    },
    "mr:0201-conorus-o-devany-et-patricius-o-lougham": {
        EDITION_EN: (
            "Translation error: \"bishop of Dungannon and Connor\" where the Latin has \"epíscopi "
            "Dunénsis et Connorénsis\" (of Down and Connor). Translation error: \"both of the Order "
            "of Friars Minor\" where the Latin gives \"ex Ordine Fratrum Minórum\" to the bishop "
            "alone."
        ),
    },
    "mr:0201-ioannes": {
        EDITION_EN: (
            "Translation error: \"a man of justice and mercy\" where the Latin has \"miræ "
            "austeritátis et iustítiæ\" (of wonderful austerity and justice). Translation error: "
            "\"transferred the episcopal see to Aleth\" where the Latin has \"sedem episcopálem "
            "Alethénsem eódem tránstulit\" (moved the see of Aleth here, to Saint-Malo)."
        ),
    },
    "mr:0201-maria-anna-vaillot-et-socii": {
        EDITION_EN: (
            "Translation error: \"In April, near Angers\" where the Latin has \"Aprilíaci apud "
            "Andégavum\" (at Avrillé near Angers)."
        ),
    },
    "mr:0201-ursus": {
        EDITION_EN: (
            "Translation error: \"In the Alps of Greece\" where the Latin has \"Augústæ Prætóriæ in "
            "Alpibus Graiis\" (at Aosta in the Graian Alps)."
        ),
    },
    "mr:0204-ioanna-de-valois": {
        EDITION_EN: (
            "Translation error: \"finding no way to resolve her marriage bond\" where the Latin has "
            "\"vínculo matrimónii nullo declaráto\" (her marriage having been declared null)."
        ),
    },
    "mr:0204-papias-et-socii": {
        EDITION_EN: (
            "Translation error: \"In Pamphylia\" omits \"Perge\", the city named in the Latin. "
            "Translation error: \"Papirius\" where the Latin has \"Pápiæ\" (Papias)."
        ),
    },
    "mr:0205-lucas": {
        EDITION_EN: (
            "Translation error: \"Lucretius\" where the Latin has \"Lucæ\" (Luke)."
        ),
    },
    "mr:0205-paulus-miki-et-socii": {
        EDITION_EN: (
            "Translation error: \"celebrated today\" where the Latin has \"cras\" (tomorrow)."
        ),
    },
    "mr:0205-sabas-iunior": {
        EDITION_EN: (
            "Translation error: \"Saint Crescentius\" where the Latin has \"Sancti Cæsárii\" (Saint "
            "Caesarius)."
        ),
    },
    "mr:0206-paulus-miki-et-socii": {
        EDITION_EN: (
            "Translation error: \"eighteen laypeople\" where the Latin has \"septem et decem\" "
            "(seventeen)."
        ),
    },
    "mr:0207-lucas-iunior": {
        EDITION_EN: (
            "Translation error: \"Lucerius the Younger\" where the Latin has \"Lucæ Iunióris\" (Luke "
            "the Younger)."
        ),
    },
    "mr:0208-iosephina-gabriela-bonino": {
        EDITION_EN: (
            "Translation error: \"Savona\" where the Latin has \"Saviliáni\" (Savigliano)."
        ),
    },
    "mr:0212-ludanus": {
        EDITION_EN: (
            "Translation error: \"Lucian\" where the Latin has \"Lúdani\" (Ludan)."
        ),
    },
    "mr:0213-stephanus-reate": {
        EDITION_EN: (
            "Editorial error: a bracketed sentence about angels at his death is added, and \"sicut "
            "sanctus Gregórius papa Magnus scripsit\" (as Saint Gregory the Great wrote) is "
            "omitted."
        ),
    },
    "mr:0214-bassianus-et-socii": {
        EDITION_EN: (
            "Translation error: \"Pratus\" where the Latin has \"Proti\" (Protus)."
        ),
    },
    "mr:0215-quinidius": {
        EDITION_EN: (
            "Translation error: \"Quininus\" where the Latin has \"Quinídii\" (Quinidius)."
        ),
    },
    "mr:0217-flavianus": {
        EDITION_EN: (
            "Translation error: \"from the violence of the assault\" is added; the Latin says only "
            "\"brevi póstea vitam finívit\" (he died shortly afterward)."
        ),
    },
    "mr:0221-petrus-damianus": {
        EDITION_IT: (
            "Translation omission: the sentence \"Ipsíus autem tránsitus Favéntiæ in Flamínia "
            "crástina die evénit\" (his death took place at Faenza on the following day) is not "
            "rendered."
        ),
        EDITION_EN: (
            "Translation error: \"on a holy day\" where the Latin has \"crástina die\" (on the "
            "following day)."
        ),
    },
    "mr:0222-aemilia-d-oultremont": {
        EDITION_EN: (
            "Translation error: the clause \"terrénam peregrinatiónem iter ad pátriam fáciens pie "
            "conclúsit\" (she piously ended her earthly pilgrimage while journeying home) is "
            "omitted."
        ),
    },
    "mr:0227-gabriel-a-virgine-perdolenti": {
        EDITION_EN: (
            "Translation error: \"On the island of the Abruzzi\" where the Latin has \"Insulæ in "
            "Aprútio\" (at Isola del Gran Sasso, in the Abruzzi)."
        ),
    },
    "mr:0301-albinus": {
        EDITION_EN: (
            "Translation error: \"Gallia Lugdunensis Lugdunum\" where the Latin has only \"in Gállia "
            "Lugdunénsi\" (in Gallia Lugdunensis)."
        ),
    },
    "mr:0301-leo-lucas": {
        EDITION_EN: (
            "Translation error: \"Leo of Lucca\" where the Latin has \"Leónis Lucæ\" (Leo Luca, known as Leoluca)."
        ),
    },
    "mr:0302-angela-a-cruce": {
        EDITION_IT: (
            "Translation omission: the title \"vergine\" (Latin \"vírginis\") is missing after the "
            "name."
        ),
        EDITION_EN: (
            "Translation error: the title \"virgin\" (\"vírginis\") is omitted."
        ),
    },
    "mr:0303-petrus-renatus-rogue": {
        EDITION_EN: (
            "Translation error: \"Daron\" where the Latin has \"Dariórigi\" (Vannes)."
        ),
    },
    "mr:0309-francisca": {
        EDITION_EN: (
            "Translation error: \"among the offerings\" where the Latin has \"inter oblátas\" (among "
            "the Oblates)."
        ),
    },
    "mr:0311-dominicus-cam": {
        EDITION_EN: (
            "Translation error: \"Thieu Tri\" where the Latin has \"Tự Ðức\"."
        ),
    },
    "mr:0312-aloysius-orione": {
        EDITION_EN: (
            "Translation error: \"Tortona\" where the Latin has \"Matútæ\" (Sanremo)."
        ),
    },
    "mr:0312-iosephus-zhang-dapeng": {
        EDITION_EN: (
            "Translation error: \"the outcasts\" where the Latin has \"ægrótis\" (the sick)."
        ),
    },
    "mr:0318-amata-le-bouteiller": {
        EDITION_EN: (
            "Translation error: \"Saint Savior at Vicoigne\" where the Latin has \"Sancti Salvatóris "
            "Vicecómitis\" (Saint-Sauveur-le-Vicomte)."
        ),
    },
    "mr:0320-ioanna-veron": {
        EDITION_EN: (
            "Translation error: \"Érines in the district of Meudon\" where the Latin has \"Erenéi in "
            "pago Meduáno\" (Ernée, in Mayenne)."
        ),
    },
    "mr:0321-ioannes": {
        EDITION_EN: (
            "Translation error: \"Saint-Julien of Valence\" where the Latin \"Iúliæ Valéntiæ\" is "
            "simply Valence. Translation error: \"truly ruined\" where the Latin has \"ære dírutos\" "
            "(ruined by debt)."
        ),
    },
    "mr:0323-gualterius": {
        EDITION_EN: (
            "Translation error: \"Pont-Sainte-Maxence\" where the Latin has \"Pontísaræ\" (Pontoise)."
        ),
    },
    "mr:0323-victorianus-et-socii": {
        EDITION_EN: (
            "Translation error: \"of Aghlab origin\" where the Latin has \"Aquæregénsium\" (of Aquae "
            "Regiae)."
        ),
    },
    "mr:0324-franciscus-iosephus-lopez-caamano": {
        EDITION_EN: (
            "Translation error: \"Andújar\" where the Latin has \"Arúndæ\" (Ronda)."
        ),
    },
    "mr:0325-everardus": {
        EDITION_EN: (
            "Translation error: \"Petershausen\" where the Latin has \"Probatópoli\" (Schaffhausen)."
        ),
    },
    "mr:0330-regulus": {
        EDITION_EN: (
            "Translation error: \"Autun\" where the Latin has \"Augustómagi\" (Senlis)."
        ),
    },
    "mr:0409-acacius": {
        EDITION_EN: (
            "Translation error: \"to ransom Persian captives, and the clergy from dreadful "
            "tortures, even melted them down\" where the Latin has \"pro rediméndis Persis captívis "
            "ac diris tortis supplíciis clerum conflávit\" (to ransom Persian captives cruelly "
            "tortured, he gathered the clergy)."
        ),
    },
    "mr:0409-aedesius": {
        EDITION_EN: (
            "Translation error: \"virgins consecrated to a goddess\" where the Latin has \"vírgines "
            "Deo dicátas\" (virgins consecrated to God)."
        ),
    },
    "mr:0409-liborius": {
        EDITION_EN: (
            "Translation error: \"Saint Liberius\" where the Latin has \"sancti Libórii\" (Saint "
            "Liborius)."
        ),
    },
    "mr:0413-margarita": {
        EDITION_EN: (
            "Translation error: \"born Greek\" where the Latin has \"cæca nata\" (born blind)."
        ),
    },
    "mr:0415-ortarius": {
        EDITION_EN: (
            "Translation error: \"Saint Ouen (Ortarius)\" where the Latin has \"sancti Ortárii\" "
            "(Saint Ortarius); Ouen is a different saint."
        ),
    },
    "mr:0415-paternus": {
        EDITION_EN: (
            "Translation error: \"Séez\" where the Latin has \"Sescíaci\" (Scissy, in the district of "
            "Coutances)."
        ),
    },
    "mr:0417-simeon": {
        EDITION_EN: (
            "Translation error: \"Sapor, Second King of the Persians\" where the Latin has \"Sápore "
            "Persárum rege Secúndo\" (Sapor II, King of the Persians)."
        ),
    },
    "mr:0421-conradus-de-parzham": {
        EDITION_EN: (
            "Translation error: \"Hohenwart\" where the Latin has \"Hodíngis\" (Altötting)."
        ),
    },
    "mr:0422-senorina": {
        EDITION_EN: (
            "Translation error: \"Badajoz\" where the Latin has \"Basti\" (Basto, in Portugal)."
        ),
    },
    "mr:0425-marcus-evangelista": {
        EDITION_EN: (
            "Translation error: \"blessed Peter, his son\" where the Latin has \"ab illo fílius "
            "nuncupátus\" (called son by him, that is, by Peter)."
        ),
    },
    "mr:0501-arigius": {
        EDITION_EN: (
            "Translation error: \"Vence\" where the Latin has \"Vapínci\" (Gap)."
        ),
    },
    "mr:0506-benedicta": {
        EDITION_EN: (
            "Translation error: \"whom she especially loved above all others\" where the Latin has "
            "\"cui máxime præ céteris dilécta erat\" (by whom she was loved above all others)."
        ),
    },
    "mr:0506-eduardus-jones-et-antonius-middleton": {
        EDITION_EN: (
            "Translation error: \"hanged on pitchforks\" where the Latin has \"furcis suspénsi sunt\" "
            "(hanged on gallows)."
        ),
    },
    "mr:0510-gulielmus": {
        EDITION_EN: (
            "Translation error: \"Pont-Sainte-Maxence\" where the Latin has \"Pontísaræ\" (Pontoise)."
        ),
    },
    "mr:0516-peregrinus": {
        EDITION_EN: (
            "Translation error: \"Autun\" where the Latin has \"Autissiodorénsi\" (Auxerre)."
        ),
    },
    "mr:0516-simon-stock": {
        EDITION_IT: (
            "Translation error: \"beato Simone Stock\" where the Latin has \"sancti Simónis Stock\" "
            "(Saint)."
        ),
        EDITION_EN: (
            "Translation error: \"blessed Simon Stock\" where the Latin has \"sancti Simónis Stock\" "
            "(Saint)."
        ),
    },
    "mr:0520-aurea": {
        EDITION_EN: (
            "Translation error: \"Aurore\" where the Latin has \"Aureæ\" (Aurea)."
        ),
    },
    "mr:0520-protasius-chong-kuk-bo": {
        EDITION_EN: (
            "Translation error: \"Chong Kuk-ho\" where the Latin has \"Chong Kuk-bo\"."
        ),
    },
    "mr:0528-paulus-hanh": {
        EDITION_EN: (
            "Translation error: \"led a gang in the marketplace\" where the Latin has \"manípulum "
            "furum ducébat\" (led a band of thieves)."
        ),
    },
    "mr:0530-hubertus": {
        EDITION_EN: (
            "Translation error: \"Saint Robert\" where the Latin has \"sancti Hubérti\" (Saint "
            "Hubert)."
        ),
    },
    "mr:0531-iacobus-amoroso": {
        EDITION_EN: (
            "Translation error: \"Erice\" where the Latin has \"Hérbitæ\" (Nicosia)."
        ),
    },
    "mr:0604-philippus-smaldone": {
        EDITION_EN: (
            "Translation error: \"deaf and mute\" where the Latin has \"surdórum ac cæcórum\" (the "
            "deaf and the blind)."
        ),
    },
    "mr:0606-innocentius-guz": {
        EDITION_EN: (
            "Translation error: \"followers of contrary opinions and religions ... was detained by "
            "the guards\" where the Latin has \"opiniónum hóminum et religiónis adversárum\" "
            "(ideologies hostile to man and religion) and \"a vigílibus ... trucidátus est\" "
            "(murdered by the guards)."
        ),
    },
    "mr:0612-basilides": {
        EDITION_EN: (
            "Translation error: \"Loreto\" where the Latin has \"Lórii\" (Lorium, on the Via "
            "Aurelia)."
        ),
    },
    "mr:0619-remigius-isore-et-modestus-andlauer": {
        EDITION_EN: (
            "Translation error: \"Science City\" where the Latin has \"civitátem Scienscienénsem\" "
            "(the city of Xianxian)."
        ),
    },
    "mr:0623-walherus": {
        EDITION_EN: (
            "Translation error: \"while still bearing the tonsure of Remigius\" where the Latin has "
            "\"remígii tonsa mactátus\" (killed with an oar)."
        ),
    },
    "mr:0624-ioannes-baptista": {
        EDITION_EN: (
            "Translation error: \"was filled with the Holy Spirit\" (of John) where the Latin has "
            "\"matris, Spíritu Sancto replétæ\" (his mother, filled with the Holy Spirit)."
        ),
    },
    "mr:0625-salomon": {
        EDITION_EN: (
            "Translation error: \"attacked\" where the Latin has \"obcæcátus\" (blinded)."
        ),
    },
    "mr:0626-salvius": {
        EDITION_EN: (
            "Translation error: \"Valence\" where the Latin has \"Valentiánam\" (Valenciennes)."
        ),
    },
    "mr:0629-petrus-et-paulus-apostoli": {
        EDITION_EN: (
            "Translation error: \"confessed [Christ] on the Via Ostiensis\" where the Latin has "
            "\"via Ostiénsi confóssus\" (pierced on the Ostian Way)."
        ),
    },
    "mr:0702-lidanus": {
        EDITION_EN: (
            "Translation error: \"Settimo\" where the Latin has \"Sétiæ\" (Sezze)."
        ),
    },
    "mr:0703-marcus-et-mocianus": {
        EDITION_EN: (
            "Translation error: \"Mysia\" where the Latin has \"Mœsia\" (Moesia, on the Danube)."
        ),
    },
    "mr:0705-georgius-nichols-et-richardus-yaxley": {
        EDITION_EN: (
            "Translation error: \"condemned to death by beheading\" where the Latin has \"cápite "
            "damnáti\" (condemned to death); they were hanged."
        ),
    },
    "mr:0706-maria-goretti": {
        EDITION_EN: (
            "Translation error: \"confessed [attested to her faith] by [through the] blows of a "
            "dagger\" where the Latin has \"pugiónis íctibus confóssa\" (stabbed with blows of a "
            "dagger)."
        ),
    },
    "mr:0711-placidus-et-sigisbertus": {
        EDITION_EN: (
            "Translation error: \"the former ... founded\" where the Latin has \"alter\" (the other, "
            "Sigisbert) as founder and \"prior\" (Placidus) as the martyr."
        ),
    },
    "mr:0712-ioannes-gualbertus": {
        EDITION_EN: (
            "Translation error: \"the Valley of the Umbra\" where the Latin has \"Valle Umbrósa\" "
            "(Vallombrosa)."
        ),
    },
    "mr:0715-bernardus": {
        EDITION_EN: (
            "Translation error: \"Mont Cenis\" where the Latin has \"Monte Calério\" (Moncalieri)."
        ),
    },
    "mr:0716-maria-rosa-de-gordon-et-socii": {
        EDITION_EN: (
            "Translation error: \"Anne-Marie of Jesus\" where the Latin has \"Amátæ a Iesu\" (Aimée "
            "of Jesus)."
        ),
    },
    "mr:0717-fredegandus": {
        EDITION_EN: (
            "Translation error: \"Tournai\" where the Latin has \"Turníni\" (Deurne), and \"southern "
            "Brabant\" where it has \"Brabántia Austrásiæ\"."
        ),
    },
    "mr:0717-petrus-gojdich": {
        EDITION_EN: (
            "Translation error: \"Prešov\" where the Latin has \"Leopoldópoli\" (Leopoldov)."
        ),
    },
    "mr:0718-symphorosa-et-socii": {
        EDITION_EN: (
            "Translation error: \"her seven sons\" where the Latin has \"septem sociórum\" (seven "
            "companions)."
        ),
    },
    "mr:0720-aurelius": {
        EDITION_EN: (
            "Translation error: \"moved the episcopal seat from the place of the idol\" where the "
            "Latin \"simulácri deæ Cæléstis loco collocávit\" means he set it in the place of the "
            "idol."
        ),
    },
    "mr:0720-leo-ignatius-mangin-et-paulus-denn": {
        EDITION_EN: (
            "Translation error: \"Yingxian\" sect where the Latin has \"sectæ «Yihetuan»\" (the "
            "Boxers)."
        ),
    },
    "mr:0720-magdalena-yi-yong-hui-et-socii": {
        EDITION_EN: (
            "Translation error: \"virgins\" where the Latin has \"vírginis\" (singular, of Mary Wŏn "
            "Kwi-im only)."
        ),
    },
    "mr:0720-rita-a-virgine-perdolenti-a-corde-iesu-et-francisca-a-corde-iesu": {
        EDITION_EN: (
            "Translation error: the clause \"et paulo post plumbis in via transfóssæ\" (and shortly "
            "afterwards shot in the street) is omitted."
        ),
    },
    "mr:0720-vulmarus": {
        EDITION_EN: (
            "Translation error: \"Bologna\" where the Latin \"in pago Bononiénsi Gálliæ\" is the "
            "district of Boulogne."
        ),
    },
    "mr:0721-gabriel-pergaud": {
        EDITION_EN: (
            "Translation error: \"Lugduni\" where the Latin has \"beáti\" (blessed)."
        ),
    },
    "mr:0723-severus": {
        EDITION_EN: (
            "Translation error: \"Bizerte in Tunisia\" where the Latin has \"Bízyæ in Thrácia\" (Vize "
            "in Thrace)."
        ),
    },
    "mr:0727-desideratus": {
        EDITION_EN: (
            "Translation error: \"Salins-les-Bains\" where the Latin \"Ledóne Salinário\" is "
            "Lons-le-Saunier."
        ),
    },
    "mr:0801-friardus-et-secundellus": {
        EDITION_EN: (
            "Translation error: \"Friard and Secundellus, deacons\" where the Latin has \"Friárdi et "
            "Secundélli diáconi\" (only Secundellus was a deacon)."
        ),
    },
    "mr:0804-eleutherius": {
        EDITION_EN: (
            "Translation error: \"Tarsus\" where the Latin has \"Társiæ\" (Tarsia, in Bithynia; "
            "Tarsus is in Cilicia)."
        ),
    },
    "mr:0804-fridericus-janssoone": {
        EDITION_EN: (
            "Translation error: \"Mariannhill\" where the Latin has \"Marianópoli\" (Montreal)."
        ),
    },
    "mr:0804-ia": {
        EDITION_EN: (
            "Translation error: \"Saint Ira\" where the Latin has \"sanctæ Iæ\" (Saint Ia)."
        ),
    },
    "mr:0805-cassianus": {
        EDITION_EN: (
            "Translation error: \"At Lyon\" where the Latin has \"Augustodúni\" (Autun)."
        ),
    },
    "mr:0808-secundus-et-socii": {
        EDITION_EN: (
            "Translation error: the place \"Albáni\" (at Albano) is omitted."
        ),
    },
    "mr:0810-archangelus-de-calataphino": {
        EDITION_EN: (
            "Translation error: \"of Calataphim near Piacenza\" where the Latin has \"de Calataphíno "
            "Piacentini\" (of Calatafimi, surnamed Piacentini)."
        ),
    },
    "mr:0813-iacobus-gapp": {
        EDITION_EN: (
            "Translation error: \"Gibraltar\" where the Latin has \"in Gálliam\" (France)."
        ),
    },
    "mr:0816-stephanus": {
        EDITION_EN: (
            "Translation error: \"being Alba Regalis just and peaceful ... at in Hungary\" where "
            "the Latin has \"iustus et pacíficus ... donec Albæ Regáli in Hungária\" (just and "
            "peaceful ... until, at Székesfehérvár in Hungary); and \"churches\" where the Latin "
            "has \"ópibus\" (wealth)."
        ),
    },
    "mr:0817-iero": {
        EDITION_EN: (
            "Translation error: \"Jerome\" where the Latin has \"Ierónis\" (Iero, Jeron), a different "
            "name."
        ),
    },
    "mr:0818-martyres-massae-candidae": {
        EDITION_EN: (
            "Translation error: \"drawn more frequently like fish into the net\" where the Latin "
            "has \"crebrióres píscibus\" (more numerous than the fish drawn into the net)."
        ),
    },
    "mr:0819-elvira-a-nativitate-dominae-nostrae-et-socii": {
        EDITION_EN: (
            "Translation error: \"Nativity of Our Lord Torrente Paraira\" where the Latin has "
            "\"Nativitáte Dóminæ Nostræ Torrentallé Paraire\" (Our Lady)."
        ),
    },
    "mr:0820-ladislaus-maczkowski": {
        EDITION_EN: (
            "Translation error: \"defended the dignity of human and Christian faith\" where the "
            "Latin has \"fidem coram persecutóribus humánæ et christiánæ dignitátis\" (the faith, "
            "before the persecutors of human and Christian dignity)."
        ),
    },
    "mr:0823-zachaeus": {
        EDITION_EN: (
            "Translation error: \"Zacharias\" where the Latin has \"Zachǽi\" (Zacchaeus)."
        ),
    },
    "mr:0826-victor": {
        EDITION_EN: (
            "Translation error: \"sentenced to death by beheading\" where the Latin has \"cápite "
            "damnátus\" (condemned to death)."
        ),
    },
    "mr:0827-guarinus": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" where the Latin has \"Sabaudiae\" (in Savoy)."
        ),
        EDITION_EN: (
            "Translation error: \"Hautecombe\" where the Latin has \"monastério Alpénsi\" (Aulps)."
        ),
    },
    "mr:0827-poemen": {
        EDITION_EN: (
            "Translation error: \"Phermeus\" where the Latin has \"Pœmenis\" (Poemen)."
        ),
    },
    "mr:0830-pammachius": {
        EDITION_EN: (
            "Translation error: \"Titulus Crescentianus\" where the Latin has \"títulus "
            "Cælimontánus\" (the title on the Caelian Hill)."
        ),
    },
    "mr:0830-sexaginta-martyres-coloniae-sufetanae": {
        EDITION_EN: (
            "Translation error: \"were burned\" where the Latin has \"cæsi sunt\" (were slain)."
        ),
    },
    "mr:0902-albertus-et-vitus": {
        EDITION_EN: (
            "Translation error: \"Ponte\" where the Latin has \"Pontídæ\" (Pontida). Translation "
            "error: \"forsook the military service of Christ\" where the Latin has \"milítiam "
            "Christi armis honoribúsque sǽculi præpósuit\" (preferred the service of Christ to the "
            "arms and honours of the world)."
        ),
    },
    "mr:0902-antoninus": {
        EDITION_EN: (
            "Translation error: \"the twentieth year of the reign\" where the Latin has \"vicésimo "
            "ætátis anno\" (in the twentieth year of his age)."
        ),
    },
    "mr:0902-brochardus": {
        EDITION_EN: (
            "Translation error: \"spring of Elisha\" where the Latin has \"fontem Elíæ\" (the spring "
            "of Elijah)."
        ),
    },
    "mr:0902-theodota": {
        EDITION_EN: (
            "Translation error: \"Nicomedia\" where the Latin has \"Nicǽæ\" (Nicaea)."
        ),
    },
    "mr:0903-andreas-abel-alricy-et-socii": {
        EDITION_EN: (
            "Translation error: \"after having confessed the faith on the previous day\" where the "
            "Latin has \"post pridiánam cædem\" (after the previous day's massacre)."
        ),
    },
    "mr:0903-guala": {
        EDITION_EN: (
            "Translation error: \"Gualterus\" where the Latin has \"Guálæ\" (Guala)."
        ),
    },
    "mr:0904-catharina-mattei": {
        EDITION_EN: (
            "Translation error: \"Carmagnola\" where the Latin has \"Caramániæ\" (Caramagna)."
        ),
    },
    "mr:0904-iosephus-paschalis-carda-saporta": {
        EDITION_EN: (
            "Translation error: \"near Castile\" where the Latin has \"apud Castáliam\" (near "
            "Castellón)."
        ),
    },
    "mr:0907-eugenia-picco": {
        EDITION_EN: (
            "Translation error: the eulogy is broken off and an editorial comment disputing it is "
            "added after \"wholly devoted to the will of God\"; the Latin simply states that she "
            "\"dignitátem mulíerum promóvit\" (promoted the dignity of women)."
        ),
    },
    "mr:0908-antonius-a-sancto-bonaventura-et-socii": {
        EDITION_EN: (
            "Translation error: \"seven of whom were martyrs\" where the Latin has \"vigínti "
            "sociórum, mártyrum, quorum céteri láici\" (twenty companions, martyrs, the rest of "
            "them laymen)."
        ),
    },
    "mr:0908-iosepha-a-sancto-ioanne-a-deo-et-maria-a-doloribus-a-sancta-eulalia": {
        EDITION_EN: (
            "Translation error: \"Burjasot\" where the Latin has \"Buñol\"."
        ),
    },
    "mr:0909-emma-uffing": {
        EDITION_EN: (
            "Translation error: \"At a monastery\" where the Latin has \"Monastérii\" (at Münster)."
        ),
    },
    "mr:0910-iacobus-gagnot": {
        EDITION_EN: (
            "Translation error: \"On the rafts of the pontoon\" where the Latin has \"In æquóribus "
            "ponti\" (on the waters of the sea)."
        ),
    },
    "mr:0913-aemilianus": {
        EDITION_EN: (
            "Translation error: \"Yzeures-sur-Creuse (ancient Juliacum)\" where the Latin has "
            "\"Iúliæ Valéntiæ\" (Valence)."
        ),
    },
    "mr:0913-dedicatio-basilicarum-hierosolymis": {
        EDITION_EN: (
            "Translation error: \"ordered to be rebuilt\" where the Latin has \"ædificári vóluit\" "
            "(built)."
        ),
    },
    "mr:0913-litorius": {
        EDITION_EN: (
            "Translation error: \"the first to rebuild a church\" where the Latin has \"ecclésiam "
            "ædificávit\" (built)."
        ),
    },
    "mr:0914-notburga": {
        EDITION_EN: (
            "Translation error: \"blessed Notburga\" where the Latin has \"sanctæ Notbúrgæ\" (Saint "
            "Notburga)."
        ),
    },
    "mr:0920-iosephus-maria-de-yermo-y-parres": {
        EDITION_IT: (
            "Translation error: \"beato\" where the Latin has \"sancti\" (Saint); he was canonized in "
            "2000."
        ),
        EDITION_EN: (
            "Translation error: \"blessed\" where the Latin has \"sancti\" (Saint)."
        ),
    },
    "mr:0920-thomas-johnson": {
        EDITION_EN: (
            "Translation error: \"with some of his fellow brothers\" where the Latin has \"nonus ex "
            "número confrátrum\" (the ninth of his confreres to die)."
        ),
    },
    "mr:0921-cadocus": {
        EDITION_EN: (
            "Translation error: \"Llantwit Major\" where the Latin has \"Lancarvanénsi\" "
            "(Llancarfan)."
        ),
    },
    "mr:0923-maria-aemilia-tavernier": {
        EDITION_EN: (
            "Translation error: \"Marieville\" where the Latin has \"Marianópoli\" (Montreal)."
        ),
    },
    "mr:0929-adelricus": {
        EDITION_EN: (
            "Translation error: \"Reichenau\" where the Latin has \"ínsula Augia lacus Turicénsis\" "
            "(Ufnau in Lake Zurich)."
        ),
    },
    "mr:1001-piato": {
        EDITION_EN: (
            "Translation error: \"Saint-Piat\" where the Latin has \"Sacilínii\" (Seclin)."
        ),
    },
    "mr:1002-leodegarius": {
        EDITION_EN: (
            "Translation error: \"mutilated\" where the Latin has \"excæcátum\" (blinded)."
        ),
    },
    "mr:1004-franciscus-xaverius-seelos": {
        EDITION_EN: (
            "Translation error: \"northern United States\" where the Latin has the United States of "
            "North America (Louisiana is in the south)."
        ),
    },
    "mr:1005-apollinaris": {
        EDITION_EN: (
            "Translation error: \"Saint-Julien-en-Vienne\" where the Latin has \"Iúliæ Valéntiæ\" "
            "(Valence)."
        ),
    },
    "mr:1005-petrus-de-foro-cornelii": {
        EDITION_EN: (
            "Translation error: \"Foraz Cornelii\" where the Latin has \"de Foro Cornélii\" (of "
            "Imola)."
        ),
    },
    "mr:1005-sanctus": {
        EDITION_EN: (
            "Translation error: \"Corneto\" where the Latin has \"Coræ\" (Cori)."
        ),
    },
    "mr:1009-guntherus": {
        EDITION_EN: (
            "Translation error: \"Braunau\" where the Latin has \"Brennóviæ\" (Břevnov)."
        ),
    },
    "mr:1014-fortunatus": {
        EDITION_EN: (
            "Translation error: \"prisoners\" where the Latin has \"ægrótis\" (the sick)."
        ),
    },
    "mr:1017-iacobus-burin": {
        EDITION_EN: (
            "Translation error: \"La Vallée de Guyon\" where the Latin has \"Vallis Guidónis\" "
            "(Laval)."
        ),
    },
    "mr:1017-maria-ludovica-iosepha-vanot-et-socii": {
        EDITION_EN: (
            "Translation error: \"Valence\" where the Latin has \"Valentiánæ\" (Valenciennes)."
        ),
    },
    "mr:1022-abercius": {
        EDITION_EN: (
            "Translation error: \"led the faith ... and to have nourished it\" where the Latin has "
            "\"fidem ... conduxísse et ... enutrivísse\" (that faith led him and nourished him)."
        ),
    },
    "mr:1026-witta": {
        EDITION_EN: (
            "Translation error: \"Wigbert\" where the Latin has \"Wittæ\" (Witta)."
        ),
    },
    "mr:1027-bartholomaeus-de-bregantia": {
        EDITION_EN: (
            "Translation error: \"Bragança\" where the Latin has \"de Bregántia\" (Breganze, near "
            "Vicenza)."
        ),
    },
    "mr:1028-genesius": {
        EDITION_EN: (
            "Translation error: \"twice clothed in white\" where the Latin has \"albis indútus\" "
            "(clothed in white)."
        ),
    },
    "mr:1028-ioannes-dat": {
        EDITION_EN: (
            "Translation error: \"John Baptist\" where the Latin has \"Ioánnis Ðạt\" (John Đạt)."
        ),
    },
    "mr:1029-caietanus-errico": {
        EDITION_EN: (
            "Translation error: the place \"Secundiliáni\" (Secondigliano) is omitted; only \"Near "
            "Naples\" is given."
        ),
    },
    "mr:1101-rainerius-aretinus": {
        EDITION_EN: (
            "Translation error: \"Città della Pieve\" where the Latin has \"Burgi Sancti Sepúlcri\" "
            "(Sansepolcro)."
        ),
    },
    "mr:1105-domninus": {
        EDITION_EN: (
            "Translation error: \"banished to Phoenicia\" where the Latin has \"ad metálla "
            "Phænénsia\" (to the mines of Phaeno)."
        ),
    },
    "mr:1106-paulus": {
        EDITION_EN: (
            "Translation error: \"and martyr\" is added; the Latin has only \"epíscopi "
            "Constantinopolitáni\"."
        ),
    },
    "mr:1108-godefridus": {
        EDITION_IT: (
            "Translation error: \"per un quinquennio\" (for five years) where the Latin has \"a "
            "quinquénnio\" (from the age of five)."
        ),
        EDITION_EN: (
            "Translation error: \"from the age of fifteen\" where the Latin has \"a quinquénnio\" "
            "(from the age of five)."
        ),
    },
    "mr:1108-elisabeth-maria-satellico": {
        EDITION_EN: (
            "Translation error: \"Montegranaro\" where the Latin has \"Monte Novo\" (Montenovo, today "
            "Ostra Vetere)."
        ),
    },
    "mr:1112-benedictus-et-socii": {
        EDITION_EN: (
            "Translation error: \"Vistula\" where the Latin has \"Vartam flúvium\" (the Warta)."
        ),
    },
    "mr:1113-antoninus-et-socii": {
        EDITION_EN: (
            "Translation error: \"Galerius Maximian\" where the Latin has \"Galério Maximíno\" "
            "(Galerius Maximinus)."
        ),
    },
    "mr:1115-helena-de-chappotin-de-neuville": {
        EDITION_EN: (
            "Translation error: \"Savona\" where the Latin has \"Matútæ\" (Sanremo)."
        ),
    },
    "mr:1117-lupus-sebastianus-hunot": {
        EDITION_EN: (
            "Translation error: \"on the reefs of the bridge\" where the Latin has \"in æquóribus "
            "ponti ad litus\" (in the waters of the sea off the shore)."
        ),
    },
    "mr:1118-ferdinandus-santamaria": {
        EDITION_EN: (
            "Translation error: \"Ferentino\" where the Latin has \"Fabratériæ\" (Ceccano)."
        ),
    },
    "mr:1119-elisaeus-garcia-et-alexander-planas-sauri": {
        EDITION_EN: (
            "Translation error: \"Garray\" where the Latin has \"Garraf\"."
        ),
    },
    "mr:1121-maurus-caesenae": {
        EDITION_EN: (
            "Translation error: \"Cresson in Umbria\" where the Latin has \"Cæsénæ in Flamínia\" "
            "(Cesena in Flaminia)."
        ),
    },
    "mr:1126-pontius-falciniacensis": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" (in Burgundy) where the Latin has \"in Sabáudia\" (in "
            "Savoy)."
        ),
        EDITION_EN: (
            "Translation error: \"Sées\" where the Latin has \"Sisiénsi\" (Sixt)."
        ),
    },
    "mr:1127-eusicius": {
        EDITION_EN: (
            "Translation error: \"at the foot of Mount Cari\" where the Latin has \"ad Cari "
            "crepídinem\" (on the bank of the Cher)."
        ),
    },
    "mr:1127-gulstanus": {
        EDITION_EN: (
            "Translation error: \"Belle-Île\" where the Latin has \"in loco Bello Visu\" "
            "(Beauvoir-sur-Mer)."
        ),
    },
    "mr:1201-florentia": {
        EDITION_EN: (
            "Translation error: \"Florentina\" where the Latin has \"Floréntiæ\" (Florentia)."
        ),
    },
    "mr:1201-helisa-angela-meneguzzi": {
        EDITION_EN: (
            "Translation error: \"Hélène Angela\" where the Latin has \"Helísæ Angelæ\" (Elisa "
            "Angela)."
        ),
    },
    "mr:1207-fara": {
        EDITION_EN: (
            "Translation error: \"Évry\" where the Latin has \"Eboríaci\" (Faremoutiers)."
        ),
    },
    "mr:1209-iosephus-ferrer-esteve": {
        EDITION_EN: (
            "Translation error: \"Poor Schools\" where the Latin has \"Scholárum Piárum\" (Pious "
            "Schools)."
        ),
    },
    "mr:1209-liborius-wagner": {
        EDITION_EN: (
            "Translation error: \"Liberius\" where the Latin has \"Libórii\" (Liborius)."
        ),
    },
    "mr:1212-epimachus-et-alexander": {
        EDITION_EN: (
            "Translation error: \"without hearing them\" and \"their constancy also be conquered\" "
            "where the Latin means the judge feared that, even after unheard-of tortures, he "
            "would be conquered by their constancy."
        ),
    },
    "mr:1216-clemens-marchisio": {
        EDITION_EN: (
            "Translation error: \"Riva presso Chieri\" where the Latin has \"Ripæ Albæ\" (Rivalba)."
        ),
    },
    "mr:1217-sturmius": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificándum curávit\" (had it "
            "built)."
        ),
    },
    "mr:1226-zeno": {
        EDITION_EN: (
            "Translation error: \"rebuilt a basilica with his kinsmen\" where the Latin says he "
            "built a basilica for his cousins the martyrs."
        ),
    },
    "mr:1228-franciscus-de-sales": {
        EDITION_EN: (
            "Translation error: \"the day of his death at Annecy\" where the Latin has \"die "
            "depositiónis\" (the day of his burial)."
        ),
    },
    "mr:1229-ebrulfus": {
        EDITION_EN: (
            "Translation error: \"Ouche\" where the Latin has \"Oximi\" (Exmes)."
        ),
    },
    "mr:1229-libosus": {
        EDITION_EN: (
            "Translation error: \"Liberius\" where the Latin has \"Libósi\" (Libosus)."
        ),
    },
    "mr:1230-geremarus": {
        EDITION_EN: (
            "Translation error: \"Flavigny\" where the Latin has \"Fláviæ\" (Fly)."
        ),
    },
    "mr:1231-barbatianus": {
        EDITION_EN: (
            "Translation error: \"Barbatus\" where the Latin has \"Barbatiáni\" (Barbatian)."
        ),
    },
    "mr:0101-valentinus-paquay": {
        EDITION_IT: (
            "Translation error: \"vicino a Tongeren\" where the Latin has \"prope Traiéctum Mosæ\" "
            "(near Maastricht)."
        ),
    },
    "mr:0111-bernardus-scammacca": {
        EDITION_IT: (
            "Translation error: \"Bernardino\" where the Latin has \"Bernárdi\" (Bernardo)."
        ),
    },
    "mr:0120-wulfstanus": {
        EDITION_IT: (
            "Translation error: \"condannare la venalità\" (condemning venality) where the Latin "
            "has \"in venalícia exprobránda\" (condemning the slave trade)."
        ),
    },
    "mr:0126-albericus": {
        EDITION_IT: (
            "Translation error: \"Neumünster\" where the Latin has \"Novum Monastérium\" (the New "
            "Monastery, that is Cîteaux)."
        ),
    },
    "mr:0127-ioannes": {
        EDITION_IT: (
            "Translation error: \"sede episcopale di Maurienne\" where the Latin has \"sedem "
            "Morinénsem\" (the see of the Morini, that is Thérouanne)."
        ),
    },
    "mr:0208-martyres-monachi-dii-constantinopolitani": {
        EDITION_IT: (
            "Translation error: \"monastero di Dio\" (monastery of God) where the Latin has "
            "\"monastérii Dii\" (the monastery of Dius, named after its founder)."
        ),
    },
    "mr:0212-meletius": {
        EDITION_IT: (
            "Translation error: \"mandato dall’esilio\" (sent from exile) where the Latin has "
            "\"exsílio afféctus est\" (was sent into exile)."
        ),
    },
    "mr:0217-evermodus": {
        EDITION_IT: (
            "Translation error: \"nell’Alsazia\" (Alsace) where the Latin has \"in Holsátia\" "
            "(Holstein)."
        ),
    },
    "mr:0219-bonifatius": {
        EDITION_IT: (
            "Translation error: \"tra i monaci cistercensi\" (among Cistercian monks) where the "
            "Latin has \"apud moniáles Cisterciénses\" (among Cistercian nuns)."
        ),
    },
    "mr:0220-eucherius": {
        EDITION_IT: (
            "Translation error: \"dal re Carlo Martello\" (by King Charles Martel) where the Latin "
            "has \"duce\" (duke); Charles Martel was never king."
        ),
    },
    "mr:0223-raphaela-de-villalonga-ybarra": {
        EDITION_IT: (
            "Translation error: \"nella Guascogna\" (Gascony) where the Latin has \"in Vascónia\" "
            "(the Basque Country)."
        ),
    },
    "mr:0229-augustus-chapdelaine": {
        EDITION_IT: (
            "Translation error: \"Agostino\" (Augustine) for the Latin \"Augústi\" (Auguste, "
            "Augusto)."
        ),
    },
    "mr:0302-ceadda": {
        EDITION_IT: (
            "Translation error: \"dell’Anglia meridionale\" (southern Anglia) where the Latin has "
            "\"Mediterraneórum Anglórum\" (the Middle Angles)."
        ),
    },
    "mr:0303-winwaloeus": {
        EDITION_IT: (
            "Translation error: \"Nella Cornovaglia in Inghilterra\" (Cornwall in England) where "
            "the Latin has \"In Cornúbia Armóricæ\" (Cornouaille in Brittany, where Landévennec "
            "lies)."
        ),
    },
    "mr:0306-fridolinus": {
        EDITION_IT: (
            "Translation error: \"due monasteri\" (two monasteries) where the Latin has \"duplex "
            "monastérium\" (a double monastery)."
        ),
    },
    "mr:0307-basilius-et-socii": {
        EDITION_IT: (
            "Translation error: \"in Grecia\" (in Greece) for \"Chersonésum\", which is Cherson in "
            "the Crimea."
        ),
    },
    "mr:0314-eva-montis-cornelius": {
        EDITION_IT: (
            "Translation error: \"monaca di clausura nel monastero di San Martino\" (an enclosed "
            "nun in the monastery) where the Latin has \"reclúsæ prope cœnóbium Sancti Martíni\" (a "
            "recluse near the monastery of Saint Martin)."
        ),
    },
    "mr:0320-franciscus-a-iesu-maria-ioseph": {
        EDITION_IT: (
            "Translation error: \"dove morì abbandonato a se stesso\" (where he died, abandoned) "
            "where the Latin says only that he was banished there, \"ab ómnibus derelíctus\" "
            "(abandoned by all); he died at Tarragona."
        ),
    },
    "mr:0320-maria-iosepha-a-corde-iesu": {
        EDITION_IT: (
            "Translation error: \"nella Guascogna\" (Gascony, in France) where the Latin has \"in "
            "Vascónia Hispániæ\" (the Basque Country of Spain)."
        ),
    },
    "mr:0328-hilarion": {
        EDITION_IT: (
            "Translation error: \"nell’odierna Grecia\" for the Bithynian Mount Olympus, which is "
            "in Asia Minor (modern Turkey)."
        ),
    },
    "mr:0418-idesbaldus": {
        EDITION_IT: (
            "Translation error: \"nel monastero di Down\" where the Latin has \"Dunénse monastérium\" "
            "(the Abbey of the Dunes, Ten Duinen, in Flanders)."
        ),
    },
    "mr:0427-ioannes": {
        EDITION_IT: (
            "Translation error: \"nel mare Egeo\" (in the Aegean Sea) where the Latin has \"in "
            "Propóntide\" (the Propontis, i.e. the Sea of Marmara)."
        ),
    },
    "mr:0427-zita": {
        EDITION_IT: (
            "Translation error: \"fu per dodici anni domestica\" (a domestic for twelve years) "
            "where the Latin has \"duodénnis\" (at twelve years of age she entered service, "
            "remaining in it until death)."
        ),
    },
    "mr:0505-godehardus": {
        EDITION_IT: (
            "Translation error: \"succeduto a san Bernardo\" where the Latin has \"sancto Bernwárdo\" "
            "(Saint Bernward, his predecessor at Hildesheim)."
        ),
    },
    "mr:0507-gisella": {
        EDITION_IT: (
            "Translation error: \"spogliatasi di tutti i suoi beni\" (having stripped herself) "
            "where the Latin has \"ómnibus facultátibus spoliáta\" (despoiled of all her goods)."
        ),
    },
    "mr:0513-andreas-hubertus-fournet": {
        EDITION_IT: (
            "Translation error: \"Puy-en-Vélay\" where the Latin has \"Pódii in pago Pictaviénsi\" "
            "(La Puye, near Poitiers)."
        ),
    },
    "mr:0522-lupus": {
        EDITION_IT: (
            "Translation error: \"monastero di Solesme\" where the Latin has \"monastérii "
            "Solemníaci\" (the monastery of Solignac, near Limoges)."
        ),
    },
    "mr:0522-quiteria": {
        EDITION_IT: (
            "Translation error: \"Aire-sur-le-Lys\" where the Latin has \"pago Aturénsi\" (the "
            "district of Aire-sur-l'Adour, in Aquitaine)."
        ),
    },
    "mr:0615-isfridus": {
        EDITION_IT: (
            "Translation error: \"nell’Alsazia\" (Alsace) where the Latin has \"in Holsátia\" "
            "(Holstein), the region of Ratzeburg."
        ),
    },
    "mr:0617-teresia": {
        EDITION_IT: (
            "Translation error: \"A Ourem\" where the Latin has \"Lorvanii\" (Lorvão, the monastery "
            "she founded)."
        ),
    },
    "mr:0623-lanfrancus": {
        EDITION_IT: (
            "Translation error: \"san Lanfranco\" where the Latin has \"beati Lanfranci\" (Blessed)."
        ),
    },
    "mr:0625-ioannes-hispanus": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" (Burgundy) where the Latin has \"in Sabaudia\" "
            "(Savoy)."
        ),
    },
    "mr:0701-ignatius-falzon": {
        EDITION_IT: (
            "Translation error: \"sacerdote\" (priest) where the Latin has \"cléricus\" (a cleric); "
            "Blessed Ignatius Falzon was never ordained a priest."
        ),
    },
    "mr:0704-bonifatius": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" (in Burgundy) where the Latin has \"in Sabáudia\" (in "
            "Savoy); Hautecombe and Lake Bourget are in Savoy."
        ),
    },
    "mr:0706-palladius": {
        EDITION_IT: (
            "Translation error: \"morì in Inghilterra\" (died in England) where the Latin has "
            "\"ibídem óbiit\" (died there, in Scotland)."
        ),
    },
    "mr:0708-auspicius": {
        EDITION_IT: (
            "Translation error: \"Tulle\" where the Latin has \"Tulli\" (Toul, in Gallia Belgica)."
        ),
    },
    "mr:0711-hidulphus": {
        EDITION_IT: (
            "Translation error: \"vescovo di Treviri\" (bishop of Trier) where the Latin has "
            "\"chorepíscopus Tréviris\" (chorbishop at Trier)."
        ),
    },
    "mr:0715-ansuerus": {
        EDITION_IT: (
            "Translation error: \"nell’Alsazia\" (in Alsace) where the Latin has \"in Holsátia\" (in "
            "Holstein)."
        ),
    },
    "mr:0716-helerius": {
        EDITION_IT: (
            "Translation error: \"nel Mare del Nord\" (in the North Sea) where the Latin has \"in "
            "mari Británnico\" (in the British Sea, the English Channel)."
        ),
    },
    "mr:0717-maria-magdalena-claudina-lidoine-et-socii": {
        EDITION_IT: (
            "Translation error: \"Marta Maddalena Claudina\" where the Latin has \"Maríæ Magdalénæ "
            "Claudínæ\" (Marie-Madeleine-Claudine)."
        ),
    },
    "mr:0721-simeon-salus": {
        EDITION_IT: (
            "Translation error: \"presso il lago di Mareotide in Egitto\" where the Latin has \"apud "
            "Asphaltitem lacum\" (the Dead Sea)."
        ),
    },
    "mr:0724-boris-et-gleb": {
        EDITION_IT: (
            "Translation error: \"sul fiume Don\" where the Latin has \"ad Altam flumen\" (the river "
            "Alta)."
        ),
    },
    "mr:0727-raymundus-palmerio": {
        EDITION_IT: (
            "Translation error: \"la moglie e il figlio\" (one son) where the Latin has \"uxore et "
            "filiis\" (wife and children)."
        ),
    },
    "mr:0809-claudius-richard": {
        EDITION_IT: (
            "Translation error: \"dal monastero di Metz\" where the Latin \"e Mediáno monastério\" is "
            "the abbey of Moyenmoutier."
        ),
    },
    "mr:0811-tiburtius": {
        EDITION_IT: (
            "Translation error: \"san Tiburzio\" omits the title \"martire\" given in the Latin "
            "(\"sancti Tibúrtii, mártyris\")."
        ),
    },
    "mr:0813-maximus-confessor": {
        EDITION_IT: (
            "Translation error: \"nella regione di Lesghistan\" where the Latin has \"in Lazícam "
            "regiónem\" (Lazica, in western Georgia)."
        ),
    },
    "mr:0814-arnulphus": {
        EDITION_IT: (
            "Translation error: \"Altenburg nelle Fiandre, ora in Germania\" where the Latin "
            "\"Aldenbúrgi in Flándria\" is Oudenburg in Flanders, in present-day Belgium."
        ),
    },
    "mr:0821-bassa-et-socii": {
        EDITION_IT: (
            "Translation error: \"a Edessa nell’antica Siria\" where the Latin has \"Edessae in "
            "Hellade\" (Edessa in Greece, in Macedonia)."
        ),
    },
    "mr:0826-ioanna-elisabeth-bichier": {
        EDITION_IT: (
            "Translation error: \"Puy-en-Vélay\" where the Latin has \"Podii apud Pictavium\" (La "
            "Puye, near Poitiers)."
        ),
    },
    "mr:0827-gebhardus": {
        EDITION_IT: (
            "Translation error: \"nel territorio dell’odierna Svizzera\" where the Latin has \"in "
            "Suevia\" (Swabia); Petershausen at Constance is in Germany."
        ),
    },
    "mr:0828-pelagius": {
        'martyrologium_romanum_1914_en_unofficial': (
            "Translation error: the Latin 'Constantiae, in Germania' is Konstanz, not Coutances."
        ),
        EDITION_IT: (
            "Translation error: \"nell’odierna Svizzera\" where the Latin has \"in Suevia\" (Swabia); "
            "Constance is in Germany."
        ),
    },
    "mr:0829-richardus-herst": {
        EDITION_LA: (
            "Error: \"sub Iacobo rege Primo\" (under James I), but Richard Herst was executed in "
            "1628, under Charles I."
        ),
    },
    "mr:0830-didacus-ventaja-milan-et-emmanuel-medina-olmos": {
        EDITION_IT: (
            "Translation error: \"vescovo di Cadice\" (Cádiz) where the Latin has \"Guadicensis\" (of "
            "Guadix)."
        ),
    },
    "mr:0903-rimagilus": {
        EDITION_IT: (
            "Translation error: \"Solesmes\" where the Latin has \"Sollemniacénse\" (Solignac, where "
            "Remaclus was abbot before founding Stavelot and Malmedy)."
        ),
    },
    "mr:0905-bertinus": {
        EDITION_IT: (
            "Translation error: \"fu deposto insieme a san Mummolino\" (buried together with Saint "
            "Mummolinus) where the Latin says the monastery was founded together with Saint "
            "Mummolinus."
        ),
    },
    "mr:0906-bertrandus-de-garrigues": {
        EDITION_IT: (
            "Translation error: \"san Bertrando\" (Saint) where the Latin has \"beáti Bertrándi\" "
            "(Blessed)."
        ),
    },
    "mr:0909-franciscus-garate-aranguren": {
        EDITION_IT: (
            "Translation error: \"nella Guascogna\" (Gascony) where the Latin has \"in Vascónia "
            "Hispániæ\" (the Basque Country of Spain)."
        ),
    },
    "mr:0911-ioannes-gabriel-perboyre": {
        EDITION_IT: (
            "Translation error: \"provincia dello Hebei\" where the Latin has \"provínciæ Hubei\" "
            "(Hubei, where Wuchang lies)."
        ),
    },
    "mr:0913-claudius-dumonet": {
        EDITION_IT: (
            "Translation error: \"artigiano\" (craftsman) where the Latin has \"magíster ártium\" "
            "(Master of Arts)."
        ),
    },
    "mr:0914-petrus": {
        EDITION_IT: (
            "Translation error: \"Beauvale\" where the Latin has \"Bellævallénsi\" (Bellevaux, near "
            "Besançon)."
        ),
    },
    "mr:0928-venceslaus": {
        EDITION_IT: (
            "Translation error: \"dalla zia paterna Ludmilla\" (his paternal aunt) where the Latin "
            "has \"ab ávia sancta Ludmílla\" (his grandmother, Saint Ludmila)."
        ),
    },
    "mr:1014-dominicus": {
        EDITION_IT: (
            "Translation error: \"discepolo di san Damiano\" where the Latin has \"sancti Petri "
            "Damiáni discípulus\" (a disciple of Saint Peter Damian)."
        ),
    },
    "mr:1019-ioannes-de-brebeuf-et-socii": {
        EDITION_IT: (
            "Translation error: \"oggi in Canada\" (today in Canada) where the Latin has \"tunc in "
            "território Canadénsi\" (then in Canadian territory); Ossernenon lies in present-day "
            "New York State, USA."
        ),
    },
    "mr:1023-ethelfleda": {
        EDITION_IT: (
            "Translation error: \"A Ramsey\" where the Latin has \"Rumeséiæ\" (Romsey)."
        ),
    },
    "mr:1023-ignatius": {
        EDITION_IT: (
            "Translation error: \"imperatore Barda\" (the emperor Bardas) where the Latin has "
            "\"Bardam Cǽsarem\" (Bardas the Caesar)."
        ),
    },
    "mr:1023-severinus": {
        EDITION_IT: (
            "Translation error: \"san Severo\" where the Latin has \"sancti Severíni\" (Saint "
            "Severinus)."
        ),
    },
    "mr:1023-theodoretus": {
        EDITION_IT: (
            "Translation error: \"imperatore d’Oriente\" (emperor of the East) where the Latin has "
            "\"cómite Oriéntis\" (Count of the East)."
        ),
    },
    "mr:1025-recaredus-centelles-abad": {
        EDITION_IT: (
            "Translation error: \"Riccardo\" where the Latin has \"Recarédi\" (Recaredo)."
        ),
    },
    "mr:1028-germanus": {
        EDITION_IT: (
            "Translation error: \"nella Borgogna\" (in Burgundy) where the Latin has \"in Sabáudia\" "
            "(in Savoy)."
        ),
    },
    "mr:1030-marcellus": {
        EDITION_IT: (
            "Translation error: \"la vita stessa\" (his very life) where the Latin has \"ipsam "
            "vitem\" (his vine staff, the centurion's badge)."
        ),
    },
    "mr:1105-bertilla": {
        EDITION_IT: (
            "Translation error: \"monastero di Calais\" where the Latin has \"cœnóbio Calénsi\" (the "
            "monastery of Chelles, near Meaux)."
        ),
    },
    "mr:1114-siardus": {
        EDITION_IT: (
            "Translation error: \"Malgarten\" where the Latin has \"Horto Sanctæ Maríæ\" "
            "(Mariëngaarde, in Friesland)."
        ),
    },
    "mr:1202-chromatius": {
        EDITION_IT: (
            "Translation error: \"chiostri d’Italia\" (the cloisters of Italy) where the Latin has "
            "\"Itáliæ claustris\" (the defensive barriers of Italy breached by Alaric)."
        ),
    },
    "mr:1202-silverius": {
        EDITION_IT: (
            "Translation error: \"Palmarola in Liguria\" where the Latin \"ínsula Palmária\" is "
            "Palmarola in the Pontine Islands, off Lazio, not in Liguria."
        ),
    },
    "mr:1212-vicelinus": {
        EDITION_IT: (
            "Translation error: \"nell’Alsazia\" (in Alsace) where the Latin has \"in Holsátia\" (in "
            "Holstein)."
        ),
    },
    "mr:1214-hero-et-socii": {
        EDITION_IT: (
            "Translation error: \"morì fatto a brandelli\" (died torn to pieces) where the Latin "
            "has \"différri præcépit\" (the judge ordered him to be put off, sparing him)."
        ),
    },
    "mr:1216-aggaeus-propheta": {
        EDITION_IT: (
            "Translation error: \"re di Giuda\" (king of Judah) where the Latin has \"ducis Iudæ\" "
            "(leader of Judah); Zerubbabel was governor, not king."
        ),
    },
    "mr:1218-winebaldus": {
        EDITION_IT: (
            "Translation error: \"Hildesheim\" where the Latin has \"Heidenheiménsi\" (Heidenheim), "
            "the monastery Saint Winebald founded."
        ),
    },
    "mr:1223-paulus-melendez-gonzalo": {
        EDITION_IT: (
            "Translation error: the title \"beato\" is omitted before \"Paolo Meléndez Gonzalo\"; the "
            "Latin has \"beáti Pauli\"."
        ),
    },
    "mr:1224-avi-iesu-christi": {
        EDITION_IT: (
            "Translation error: \"figlio di Adamo\" is omitted after \"figlio di Abramo\"; the Latin "
            "has \"fílii Abraham, fílii Adam\"."
        ),
    },
    "mr:1226-stephanus": {
        EDITION_IT: (
            "Translation error: \"seduto\" (seated) where the Latin has \"stantem\" (standing), as in "
            "Acts 7:55-56."
        ),
    },
    "mr:1227-iosephus-maria-corbin-ferrer": {
        EDITION_IT: (
            "Translation error: the title \"martire\" is omitted after \"Giuseppe Maria Corbin "
            "Ferrer\"; the Latin has \"mártyris\"."
        ),
    },
    "mr:0801-secundinus": {
        EDITION_IT: (
            "Translation error: \"al tredicesimo miglio\" (the thirteenth mile of the Via "
            "Prenestina) where the Latin has \"miliário tricésimo\" (the thirtieth)."
        ),
    },
    "mr:0217-septem-fundatores-servorum-mariae": {
        EDITION_1749: (
            "This edition prints the eulogy of Alexius Falconieri alone, one of the seven "
            "founders; the 2004 edition commemorates the seven founders together."
        ),
    },
    "mr:0709-maria-a-iesu-crucifixo": {
        EDITION_IT: (
            "Absent from the Latin editio altera 2004 print, whose July 9 ends at entry 10*. Bl. "
            "Marija Petković was beatified on 6 June 2003."
        ),
    },
    "mr:0712-proclus-et-hilarion": {
        EDITION_IT: (
            "Absent from the Latin editio altera 2004 print, whose July 12 numbering begins at 2 "
            "with the gap left unrenumbered."
        ),
    },
    "mr:0825-eusebius-et-socii": {
        EDITION_IT: (
            "Absent from the Latin editio altera 2004 print, where the day's numbered entries "
            "begin at 3 (Genesius) after the two unnumbered memorias."
        ),
    },
    "mr:1210-marcus-antonius-durando": {
        EDITION_IT: (
            "The Latin print and the English edition give this eulogy at 10 June "
            "(mr:0610-marcus-antonius-durando)."
        ),
    },
    "mr:0130-theophilus-iuvenis": {
        EDITION_EN: (
            "Renders the cognomen as \"the Youth\" (Latin cognoménto Iúvenis, Italian (CEI) detto "
            "il Giovane); \"the Younger\" is the conventional English epithet, which the English "
            "subject follows."
        ),
    },
    "mr:0212-antonius-caulea": {
        EDITION_EN: (
            "Translation error: \"under Emperor Leo III the Isaurian\", where the Latin print has "
            "Leónis imperatóris Sexti and the Italian (CEI) Leone VI: the emperor is Leo VI the "
            "Wise."
        ),
    },
    "mr:0410-beda": {
        EDITION_EN: (
            "Translation error: \"Saint Peter the Younger\" for the subject; the Latin print has "
            "sancti Bedæ iunióris and the Italian (CEI) san Beda il Giovane. The English subject "
            "follows the Latin."
        ),
    },
    "mr:0118-deicolus": {
        EDITION_1914: (
            "Translation error: the Latin 'In monasterio Lutrensi, in Burgundia' is Lure, in "
            "Burgundy, not Brittany."
        ),
    },
    "mr:0127-angela-merici": {
        EDITION_1914: (
            "Translation error: the Latin Brixia is Brescia, not Brixen."
        ),
    },
    "mr:0214-antoninus": {
        EDITION_1914: (
            "Translation error: the Latin is Antoninus, not Antonius (Anthony)."
        ),
    },
    "mr:0428-prudentius": {
        EDITION_1914: (
            "Translation error: the Latin has 'Episcopi et Confessoris', not a martyr."
        ),
    },
    "mr:0529-maximinus": {
        EDITION_1914: (
            "Translation error: the Latin has 'Maximini' (Maximinus of Trier), but the English "
            "says 'Maximus'."
        ),
    },
    "mr:0625-prosperus": {
        EDITION_1914: (
            "Translation error: the Latin 'Apud Rhegium' (Reggio) is rendered 'Riez'."
        ),
        EDITION_1749: (
            "This eulogy conflates Prosper of Reggio with Prosper of Aquitaine, the anti-Pelagian "
            "writer."
        ),
    },
    "mr:0703-thomas-apostolus": {
        EDITION_1914: (
            "Translation error: the Latin 'Ortonam, apud Frentanos' is Ortona, not Tortona."
        ),
    },
    "mr:0708-eugenius-iii": {
        EDITION_1914: (
            "Translation error: the Latin 'Eugenii Papae Tertii' is Eugenius III."
        ),
    },
    "mr:0719-macrina": {
        EDITION_1914: (
            "Misprint: 'Marcina' for Macrina."
        ),
    },
    "mr:0821-privatus": {
        EDITION_1749: (
            "This text joins the opening of Privatus's eulogy to the body of the eulogy of "
            "Paternus of Fondi (mr:0821-paternus): a line has evidently dropped. The 1914 English "
            "prints both eulogies."
        ),
    },
    "mr:0824-tatio": {
        EDITION_1914: (
            "Translation error: 'Domitian' where the Latin has 'persecutione Diocletiani' "
            "(Diocletian)."
        ),
    },
    "mr:0829-basilla": {
        EDITION_1914: (
            "Translation error: the Latin 'Apud Sirmium' is Sirmium, not Smyrna."
        ),
    },
    "mr:1017-florentius": {
        EDITION_1914: (
            "Translation error: the Latin (and the 2004 entry) name Florentius, not Florentinus."
        ),
    },
    "mr:1102-victorinus": {
        EDITION_1914: (
            "Translation error: the Latin 'Poetovione, in Pannonia' is Pettau (Ptuj), not "
            "Poitiers."
        ),
    },
    "mr:1218-gatianus": {
        EDITION_1914: (
            "Misprints: 'Gratian' for Gatianus and 'Fabrian' for Fabianus."
        ),
    },
    "mr:0709-melania-et-maria-anna-margarita-ab-angelis": {
        EDITION_LA: (
            "Error: \"Melániæ et Maríæ Annæ Magdalénæ de Guilhermier\" makes two martyrs of one: "
            "Melania is the religious name of Maria Anna Magdalena de Guilhermier. The eulogy "
            "commemorates two Ursulines, she and Maria Anna Margarita ab Angelis de Rocher."
        ),
        EDITION_IT: (
            "Translation error: \"Melania Marianna, Maddalena de Guilhermier\" divides one name "
            "in two: Melania is the religious name of Marianna Maddalena de Guilhermier."
        ),
        EDITION_EN: (
            "Translation error: \"Mélanie and Mary Anne Magdalen de Guilhermier\" makes two martyrs "
            "of one: Mélanie is the religious name of Mary Anne Magdalen de Guilhermier."
        ),
    },
    # Bl. Falco of Palena: all three 2004 editions set Palena in Calabria.
    "mr:0809-falcus": {
        edition: (
            f"Error: \"{printed}\": Palena is in Abruzzo (province of Chieti), not in Calabria. "
            "Falco, a Basilian monk, came from Taverna in Calabria and lived as a hermit in "
            "Abruzzo; he died at Palena, where he is buried and venerated as its patron. His "
            "Calabrian origin probably accounts for the error."
        )
        for edition, printed in ((EDITION_LA, "Palénæ in Calábria"), (EDITION_IT, "A Palena in Calabria"),
                                 (EDITION_EN, "At Palena in Calabria"))
    },
    # Printed in the Latin and the English, not in the CEI (PRINT_ONLY_ENTRIES).
    "mr:0104-abrunculus": {
        EDITION_LA: "Not printed in the Italian (CEI) edition.",
        EDITION_EN: "Not printed in the Italian (CEI) edition.",
    },
    "mr:0610-marcus-antonius-durando": {
        EDITION_LA: "The Italian (CEI) edition prints this eulogy at 10 December "
                    "(mr:1210-marcus-antonius-durando).",
        EDITION_EN: "The Italian (CEI) edition prints this eulogy at 10 December "
                    "(mr:1210-marcus-antonius-durando).",
    },
}

# The medium- and low-confidence findings of the readings of the unofficial English 2004 and of
# the Italian (CEI) 2004 against the Latin (October 2026). The English findings were accepted
# together (the curator checked the first thirty); the Italian ones were sorted as the curator
# sorted the first fifty: errors of fact, place, name, title or number are noted, renderings
# that only loosen or compress the Latin are not. Each follows any note the eulogy already has
# for that edition.
REVIEW_EDITION_NOTES = {
    "mr:0101-odilo": {
        EDITION_IT: (
            "Translation error: \"Presso Sauvigny\" where the Latin has \"Apud Silviníacum\" "
            "(Souvigny, where Odilo died)."
        ),
    },
    "mr:0102-telesphorus": {
        EDITION_IT: (
            "Translation error: \"dopo l’Apostolo\" where the Latin has \"ab Apóstolis\" (from "
            "the Apostles)."
        ),
    },
    "mr:0102-theodorus": {
        EDITION_EN: (
            "Translation error: \"the province of France\" where the Latin \"in Província "
            "Gálliæ\" names Provence."
        ),
    },
    "mr:0104-abrunculus": {
        EDITION_EN: (
            "Translation error: \"In Auvergne\" where the Latin \"Arvérnæ\" names the city of "
            "Clermont."
        ),
    },
    "mr:0104-emmanuel-gonzalez-garcia": {
        EDITION_LA: (
            "Name error: \"Sorórum Missionariárum a Názareth\"; the congregation is the "
            "Eucharistic Missionary Sisters of Nazareth."
        ),
    },
    "mr:0106-felix": {
        EDITION_EN: (
            "Translation error: \"rebuilt the cathedral church\" where the Latin has \"ecclésiam "
            "cathedrálem ædificávit\" (built)."
        ),
    },
    "mr:0107-tillo": {
        EDITION_EN: (
            "Translation error: \"blacksmith\" where the Latin has only \"faber\" (a craftsman; "
            "Tillo worked as a goldsmith under Eligius)."
        ),
    },
    "mr:0108-erhardus": {
        EDITION_IT: (
            "Translation error: \"di origine scozzese\" where the Latin \"génere scotus\" means "
            "of Irish origin."
        ),
    },
    "mr:0108-severinus": {
        EDITION_EN: (
            "Translation error: \"Ripuarian Noricum\" where the Latin \"Nórico Ripénsi\" means "
            "riverside Noricum (along the Danube)."
        ),
    },
    "mr:0109-agatha-yi-et-teresia-kim": {
        EDITION_EN: (
            "Translation error: \"beheaded\" where the Latin has \"iugulátæ\" (their throats "
            "cut)."
        ),
    },
    "mr:0110-gundisalvus": {
        EDITION_IT: (
            "Translation error: \"ai suoi seguaci\" where the Latin has \"áccolis\" (the people "
            "living nearby). Translation error: \"sacerdote: originario di Braga\" where the "
            "Latin has \"presbýteri Bracarénsis\" (a priest of Braga)."
        ),
        EDITION_EN: (
            "Translation error: \"helped rebuild a bridge\" where the Latin has \"pontem "
            "ædificándum curávit\" (had a bridge built)."
        ),
    },
    "mr:0112-caesaria": {
        EDITION_EN: (
            "Translation error: \"the province of France\" where the Latin \"in Província "
            "Gálliæ\" names Provence."
        ),
    },
    "mr:0112-nicolaus-bunkerd-kitbamrung": {
        EDITION_EN: (
            "Translation error: \"helping fellow prisoners\" where the Latin has \"in ægrótis "
            "adiuvándis\" (helping the sick)."
        ),
    },
    "mr:0113-hermylius-et-stratonicus": {
        EDITION_EN: (
            "Translation error: \"Stratonice\" (a woman's name) where the Latin has "
            "\"Stratoníci\" (Stratonicus, a man)."
        ),
    },
    "mr:0114-firminus": {
        EDITION_EN: (
            "Translation error: \"At Gabala\" where the Latin \"Apud Gábalos\" means among the "
            "Gabali (the Gévaudan)."
        ),
    },
    "mr:0115-ablebertus": {
        EDITION_IT: (
            "Translation error: \"nell’odierna Olanda\" for \"Haméti in Brabántia\", which lies "
            "in present-day Belgium."
        ),
    },
    "mr:0116-honoratus": {
        EDITION_EN: (
            "Translation error: \"the Province of France\" where the Latin has \"Província "
            "Gálliæ\" (Provence)."
        ),
    },
    "mr:0116-iosephus-antonius-tovini": {
        EDITION_EN: (
            "Translation error: \"promoted the restoration of public works\" where the Latin has "
            "\"ópera pública ædificánda curávit\" (had public works built)."
        ),
    },
    "mr:0116-iosephus-vaz": {
        EDITION_EN: (
            "Translation error: omits \"ábditos\" (hidden): the Catholics he confirmed were both "
            "scattered and in hiding."
        ),
    },
    "mr:0119-launomarus": {
        EDITION_EN: (
            "Translation error: \"the district of Dunois\" where the Latin has \"pago "
            "Dorcasíno\" (the district of Dreux)."
        ),
    },
    "mr:0119-liberata-et-faustina": {
        EDITION_EN: (
            "Translation error: \"the monastery of Margaret\" where the Latin has \"monastérium "
            "Sanctæ Margarítæ\" (the monastery of Saint Margaret)."
        ),
    },
    "mr:0120-adalheidis-brando": {
        EDITION_EN: (
            "Translation error: \"Cesaura\" where the Latin has \"Casáureæ\" (Casoria)."
        ),
    },
    "mr:0120-stephanus-min-kuk-ka": {
        EDITION_EN: (
            "Translation error: \"beheaded\" where the Latin has \"iugulátus\" (his throat was "
            "cut)."
        ),
    },
    "mr:0122-iosephus-nascimbeni": {
        EDITION_EN: (
            "Translation error: \"Castel Gardo\" where the Latin has \"Parvo Castéllo Gardæ\" "
            "(Castelletto on Lake Garda)."
        ),
    },
    "mr:0124-gulielmus-ireland-et-ioannes-grove": {
        EDITION_EN: (
            "Translation error: adds \"steadfast in faith and courage\", which is not in the "
            "Latin."
        ),
    },
    "mr:0124-iosephus-giaccardo": {
        EDITION_EN: (
            "Translation error: adds \"modern\" and \"to bring Christ to all\", which are not in "
            "the Latin."
        ),
    },
    "mr:0124-paula-gambara-costa": {
        EDITION_EN: (
            "Translation error: \"the trials of a difficult marriage\" where the Latin has "
            "\"violéntum cóniugem\" (a violent husband)."
        ),
    },
    "mr:0124-vincentius-lewoniuk-et-socii": {
        EDITION_EN: (
            "Translation error: adds \"offering their lives in fidelity to the faith\", which is "
            "not in the Latin."
        ),
    },
    "mr:0125-antonius-migliorati": {
        EDITION_EN: (
            "Translation error: \"Amando\" where the Latin has \"Amándulæ\" (Amandola)."
        ),
    },
    "mr:0125-praeiectus-et-amarinus": {
        EDITION_EN: (
            "Translation error: \"the region of Auvergne\" where the Latin has \"Arvérnæ\", the "
            "city (Clermont)."
        ),
    },
    "mr:0127-georgius-matulaitis": {
        EDITION_IT: (
            "Translation error: \"Nunzio apostolico\" where the Latin has \"missi apostólici\" "
            "(apostolic envoy, i.e. Apostolic Visitor)."
        ),
    },
    "mr:0127-gilduinus": {
        EDITION_IT: (
            "Translation error: \"Dôle\" where the Latin has \"Dolénsis in Británnia Minóre\" "
            "(Dol in Brittany)."
        ),
    },
    "mr:0128-thomas-de-aquino": {
        EDITION_EN: (
            "Translation error: \"prayer\" where the Latin \"oratiónibus\" here means discourses."
        ),
    },
    "mr:0129-sulpicius-severus": {
        EDITION_EN: (
            "Translation error: \"formerly a senator\" where the Latin has \"e senatóribus "
            "Galliárum\" (of a Gallic senatorial family)."
        ),
    },
    "mr:0131-maedhoc": {
        EDITION_EN: (
            "Translation error: \"monasteries\" where the Latin has \"cœnóbium\" (a monastery)."
        ),
    },
    "mr:0201-aloysius-variara": {
        EDITION_EN: (
            "Translation error: \"Sisters of the Sacred Heart of Jesus and Mary\" where the "
            "Latin has \"Soróres Fílias Sacrórum Córdium Iesu et Maríæ\" (Sisters Daughters of "
            "the Sacred Hearts)."
        ),
    },
    "mr:0201-anna-michelotti": {
        EDITION_EN: (
            "Translation error: \"Johanna Francesca Michelotti\" omits \"a Visitatióne (Annæ)\" "
            "(of the Visitation, born Anna). Translation error: \"Sisters of the Sacred Heart\" "
            "where the Latin has \"Sorórum Parvárum a Sacro Corde\" (Little Sisters of the "
            "Sacred Heart)."
        ),
    },
    "mr:0201-henricus-morse": {
        EDITION_EN: (
            "Translation error: \"gave up his spirit at Tyburn\" omits \"láqueo\" (by the noose: "
            "he was hanged)."
        ),
    },
    "mr:0201-ioannes": {
        EDITION_EN: (
            "Translation error: \"commended by Saint Bernard for being a poor bishop\" where the "
            "Latin has \"commendátus est, ut epíscopum páuperem se præbéret\" (was urged to show "
            "himself a poor bishop)."
        ),
    },
    "mr:0201-maria-anna-vaillot-et-socii": {
        EDITION_IT: (
            "Translation error: \"Maria Vaillot\" where the Latin has \"Maríæ Annæ Vaillot\" "
            "(Maria Anna, i.e. Marie-Anne Vaillot)."
        ),
    },
    "mr:0201-paulus": {
        EDITION_EN: (
            "Translation error: \"France-Vienna\" where the Latin has \"in pago Gálliæ "
            "Viennénsi\" (the territory of Vienne in Gaul)."
        ),
    },
    "mr:0201-reginaldus-aurelianensis": {
        EDITION_EN: (
            "Translation error: \"Reginald of Aurelian\" where the Latin has \"Regináldi "
            "Aurelianénsis\" (of Orléans)."
        ),
    },
    "mr:0201-sigisbertus": {
        EDITION_EN: (
            "Translation error: \"Sigisbert, King of the Franks\" where the Latin has "
            "\"Sigisbérti regis Tértii\" (King Sigebert III)."
        ),
    },
    "mr:0201-tryphon": {
        EDITION_EN: (
            "Translation error: \"Tryphonius\" where the Latin has \"Tryphónis\" (Tryphon)."
        ),
    },
    "mr:0201-viridiana": {
        EDITION_EN: (
            "Translation error: \"Castle Florence\" where the Latin has \"Castrum Florentínum\" "
            "(Castelfiorentino)."
        ),
    },
    "mr:0202-flosculus": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in the province of Lugdunensis)."
        ),
    },
    "mr:0202-maria-catharina-kasper": {
        EDITION_LA: (
            "Misprint: \"Dernáchi\" for Dernbach, where the saint lived and died."
        ),
    },
    "mr:0202-maria-dominica-mantovani": {
        EDITION_EN: (
            "Translation error: the sentence omits \"prǽfuit\" (she presided over the institute "
            "as its first superior)."
        ),
    },
    "mr:0202-nicolaus-saggio-de-langobardis": {
        EDITION_EN: (
            "Translation error: \"of the Lombards\" where the Latin \"de Langobárdis\" is the "
            "town of Longobardi."
        ),
    },
    "mr:0203-celerinus": {
        EDITION_IT: (
            "Translation error: \"spada\" (sword) where the Latin has \"ferro\" (irons, i.e. "
            "chains, alongside the stocks)."
        ),
        EDITION_EN: (
            "Translation error: \"through His glorious Passion\" where the Latin \"gloriósa "
            "passióne\" refers to their own martyrdom."
        ),
    },
    "mr:0203-claudina-thevenet": {
        EDITION_IT: (
            "Translation error: \"Suore dei Sacri Cuori di Gesù e Maria\" where the Latin has "
            "\"Sorórum Iesu et Maríæ\" (the Sisters of Jesus and Mary, without \"Sacred "
            "Hearts\")."
        ),
    },
    "mr:0203-leonius": {
        EDITION_EN: (
            "Translation error: \"Leonianus\" where the Latin has \"Leónii\" (Leonius)."
        ),
    },
    "mr:0203-teridius-et-remedius": {
        EDITION_EN: (
            "Translation error: \"the Province of France\" where the Latin \"in Província "
            "Gálliæ\" means Provence."
        ),
    },
    "mr:0204-aventinus-trecis": {
        EDITION_EN: (
            "Translation error: \"in France, Lyon\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in the province of Lugdunensis)."
        ),
    },
    "mr:0204-eutychius": {
        EDITION_EN: (
            "Translation error: \"Eutychii\" where the Latin genitive \"Eutýchii\" means "
            "Eutychius."
        ),
    },
    "mr:0204-iosephus-de-leonessa": {
        EDITION_EN: (
            "Translation error: \"after enduring great hardships, preached the Gospel\" where "
            "the Latin has \"dire perpéssus quod Evangélium ... prædicáverat\" (suffered "
            "terribly because he had preached)."
        ),
    },
    "mr:0204-philea-et-philoromus": {
        EDITION_EN: (
            "Translation error: \"Philere\" where the Latin has \"Philéæ\" (Phileas)."
        ),
    },
    "mr:0205-albuinus": {
        EDITION_EN: (
            "Translation error: \"Albinus\" where the Latin has \"Albuíni\" (Albuin). "
            "Translation error: \"from Sabina\" where the Latin has \"e Sebána\" (from Säben, "
            "Sabiona)."
        ),
    },
    "mr:0205-avitus": {
        EDITION_EN: (
            "Translation error: \"in France Lyon\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in the province of Lugdunensis)."
        ),
    },
    "mr:0205-elisabeth-canori-mora": {
        EDITION_EN: (
            "Translation error: \"conversion of sinners, peace, and holiness\" omits \"salúte\" "
            "(salvation)."
        ),
    },
    "mr:0205-francisca-meziere": {
        EDITION_EN: (
            "Translation error: \"the Valley of Guido\" where the Latin \"Valle Guidónis\" is "
            "Laval."
        ),
    },
    "mr:0205-ingenuinus": {
        EDITION_EN: (
            "Translation error: \"Sabina\" where the Latin has \"Sebánæ\" (Säben, Sabiona)."
        ),
    },
    "mr:0205-lucas": {
        EDITION_EN: (
            "Translation error: \"Elire\" where the Latin has \"Elíæ\" (Elias)."
        ),
    },
    "mr:0208-iosephina-bakhita": {
        EDITION_EN: (
            "Translation error: \"last freed\" for \"demum liberáta\" (at last set free)."
        ),
    },
    "mr:0209-ansbertus": {
        EDITION_IT: (
            "Translation error: \"dal re Pipino\" (by King Pepin) where the Latin has \"a "
            "Pippíno príncipe\" (Pepin of Herstal, mayor of the palace, not a king)."
        ),
    },
    "mr:0210-hugo": {
        EDITION_IT: (
            "Translation error: \"la rifondazione dell’Ordine\" (the refounding of the Order) "
            "where the Latin has \"novi Ordinis institutiónem\" (the establishment of the new "
            "Order)."
        ),
    },
    "mr:0210-petrus-fremond-et-socii": {
        EDITION_EN: (
            "Translation error: \"virgins and martyrs 3\" where the Latin has only \"mártyrum\" "
            "(martyrs)."
        ),
    },
    "mr:0210-scholastica": {
        EDITION_EN: (
            "Translation error: \"Commemoration\" where the Latin has \"Memória\" (Memorial)."
        ),
    },
    "mr:0211-franciscus-borras-romeu": {
        EDITION_EN: (
            "Translation error: \"a glorious struggle against hatred for the faith\" where the "
            "Latin \"in ódium fídei\" means out of hatred for the faith."
        ),
    },
    "mr:0211-soter": {
        EDITION_EN: (
            "Translation error: \"set aside ... the honors of faith\" where the Latin says she "
            "put noble birth and honours second to the faith (\"fídei posthábitis\"). "
            "Translation error: \"frequent insults from slaves\" where the Latin has "
            "\"servílibus cæsa contuméliis\" (struck with blows fit for a slave)."
        ),
    },
    "mr:0212-ludanus": {
        EDITION_EN: (
            "Translation error: \"in Alsace\" omits \"ad ripam Illæ\" (on the bank of the Ill)."
        ),
    },
    "mr:0212-martyres-abitinenses": {
        EDITION_EN: (
            "Translation error: \"forty-nine in number\" is not in the Latin, which gives no "
            "number."
        ),
    },
    "mr:0212-thomas-hemmerford-et-socii": {
        EDITION_EN: (
            "Translation error: \"the holy martyrs\" where the Latin has \"beatórum mártyrum\" "
            "(the blessed martyrs)."
        ),
    },
    "mr:0213-augustina-camozzi": {
        EDITION_EN: (
            "Translation error: \"(Augusta)\" where the Latin has \"(Augustínæ)\" (Augustina)."
        ),
    },
    "mr:0213-gosbertus": {
        EDITION_LA: (
            "Source error: \"Suebórum\" (the Suebi, Swabians) where Gosbert was bishop of the "
            "Swedes (Sueones)."
        ),
    },
    "mr:0213-guimera": {
        EDITION_EN: (
            "Translation error: \"Guimene\" where the Latin has \"Guiméræ\" (Guimera)."
        ),
    },
    "mr:0213-paulus-le-van-loc": {
        EDITION_EN: (
            "Translation error: \"Thủ-Nghẹ\" where the Latin has \"Thị-Nghè\"."
        ),
    },
    "mr:0214-cyrillus-et-methodius": {
        EDITION_IT: (
            "Translation error: \"Srijem, nell’odierna Croazia\" for the Latin \"Sirmiénsis\"; "
            "Sirmium is Sremska Mitrovica, in present-day Serbia."
        ),
    },
    "mr:0215-georgia": {
        EDITION_EN: (
            "Translation error: \"Auvergne\" where the Latin has \"Arvérnæ\" (the city of "
            "Clermont)."
        ),
    },
    "mr:0215-quinidius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0217-silvinus": {
        EDITION_IT: (
            "Translation error: \"Auxy-aux-Moines\" for the Latin \"Alcíaci\", which is "
            "Auchy-les-Moines (Auchy-lès-Hesdin)."
        ),
        EDITION_EN: (
            "Translation error: \"apud Mórinos\" (among the Morini) is left untranslated."
        ),
    },
    "mr:0218-helladius": {
        EDITION_EN: (
            "Translation error: \"a courtier of the king\" where the Latin has \"aulæ régiæ "
            "rector\" (governor of the royal court)."
        ),
    },
    "mr:0218-ioannes-pibush": {
        EDITION_EN: (
            "Translation error: \"while yet alive\" is added; the Latin has only \"ferróque "
            "exenterátus\" (and disembowelled with the blade)."
        ),
    },
    "mr:0219-bonifatius": {
        EDITION_IT: (
            "Translation error: \"La Chambre\" for the Latin \"Cámeræ\", which is the abbey of "
            "La Cambre near Brussels."
        ),
    },
    "mr:0221-eustatius": {
        EDITION_IT: (
            "Translation error: \"a Tuzla\" for the Latin \"Traianópolim\" (Traianopolis, near "
            "present-day Alexandroupoli)."
        ),
    },
    "mr:0221-germanus": {
        EDITION_IT: (
            "Translation error: \"Grandfelt\" for the Latin \"Grandivallénsi\" "
            "(Moutier-Grandval, in German Grandfelden)."
        ),
        EDITION_EN: (
            "Translation error: \"the inhabitants of the monastery\" where the Latin has "
            "\"áccolas monastérii\" (the people living near the monastery)."
        ),
    },
    "mr:0222-cathedra-petri-apostoli": {
        EDITION_IT: (
            "Translation error: \"dalla sua vittoria\" (his victory) where the Latin \"tropǽo\" "
            "means the monument over his tomb in the Vatican."
        ),
    },
    "mr:0222-isabella": {
        EDITION_EN: (
            "Translation error: \"Poor Clare Sisters\" where the Latin has \"Sorórum Minórum\" "
            "(Sisters Minor)."
        ),
    },
    "mr:0222-paschasius": {
        EDITION_EN: (
            "Translation error: \"in France of Lyon\" where the Latin has \"in Gállia "
            "Lugdunénsi\" (in Lugdunensian Gaul)."
        ),
    },
    "mr:0223-ludovicus-mzyk": {
        EDITION_EN: (
            "Translation error: \"hostile to the faith\" where the Latin has \"homínibus et "
            "fídei infénsæ\" (hostile to mankind and to the faith)."
        ),
    },
    "mr:0223-vincentius-frelichowski": {
        EDITION_EN: (
            "Translation error: \"in the infirmary\" is added; the Latin has only \"in ægrótis "
            "assidéndo\" (attending the sick)."
        ),
    },
    "mr:0226-alexander": {
        EDITION_EN: (
            "Translation error: \"weakened in divine truth\" where the Latin has \"divína "
            "veritáte infirmátum\" (refuted by divine truth)."
        ),
    },
    "mr:0226-victor": {
        EDITION_EN: (
            "Translation error: \"Arcy\" where the Latin has \"Archíaci\" (Arcis-sur-Aube)."
        ),
    },
    "mr:0228-marana-et-cyra": {
        EDITION_EN: (
            "Translation error: the rubric \"(To be omitted in a leap year)\" is run into the "
            "eulogy; it is not part of the Latin text."
        ),
    },
    "mr:0302-agnes": {
        EDITION_EN: (
            "Translation error: \"rebuilt by herself\" where the Latin has \"ab ipsa ædificáto\" "
            "(built by her)."
        ),
    },
    "mr:0303-cunegundis": {
        EDITION_IT: (
            "Translation error: \"facendo di Cristo la sua eredità\" (making Christ her "
            "inheritance) where the Latin has \"Christum sibi herédem fáciens\" (making Christ "
            "her heir)."
        ),
    },
    "mr:0304-eulalia-viel": {
        EDITION_EN: (
            "Translation error: \"Saint Savior at Vico-Comitatus\" where the Latin has \"Sancti "
            "Salvatóris Vicecómitis\" (Saint-Sauveur-le-Vicomte). Translation error: \"stood out "
            "in the Congregation\" where the Latin has \"in Congregatióne ... regénda\" (in "
            "governing the Congregation)."
        ),
    },
    "mr:0304-humbertus": {
        EDITION_IT: (
            "Translation error: \"terzo conte di Savoia\" (the third count of Savoy) where the "
            "Latin has \"cómitis Sabáudiæ Tértii\" (Humbert III, Count of Savoy)."
        ),
    },
    "mr:0306-quiriacus": {
        EDITION_EN: (
            "Translation error: \"Belgic France\" where the Latin has \"Gállia Bélgica\" (Belgic "
            "Gaul)."
        ),
    },
    "mr:0307-perpetua-et-felicitas": {
        EDITION_IT: (
            "Translation error: \"altre giovani catecumene\" (other young women catechumens) "
            "where the Latin has \"áliis cum adulescéntibus catechúmenis\" (with other young "
            "catechumens), who included men. Translation error: \"sua schiava\" (her slave, i.e. "
            "Perpetua's) where the Latin has only \"serva\" (a slave)."
        ),
    },
    "mr:0308-humfridus": {
        EDITION_EN: (
            "Translation error: \"At Merville\" where the Latin has \"Apud Mórinos\" (among the "
            "Morini, the territory of Thérouanne)."
        ),
    },
    "mr:0308-ioannes-de-deo": {
        EDITION_EN: (
            "Translation error: \"rebuilt by himself\" where the Latin has \"a se ædificáto\" "
            "(built by him)."
        ),
    },
    "mr:0309-catharina": {
        EDITION_EN: (
            "Translation error: \"humble devotion\" where the Latin has \"pæniténtiæ "
            "humilitatísque cursu\" (course of penance and humility)."
        ),
    },
    "mr:0309-pacianus": {
        EDITION_EN: (
            "Translation error: \"truly Catholic by nature\" where the Latin has \"cathólicum "
            "vero cognómen\" (but Catholic his surname)."
        ),
    },
    "mr:0309-quadraginta-milites-sebastes": {
        EDITION_EN: (
            "Translation error: \"not for blood but for faith ... suffered\" where the Latin has "
            "\"non sánguinis sed fídei ... sócii\" (companions not of blood but of faith)."
        ),
    },
    "mr:0310-caius-et-alexander": {
        EDITION_IT: (
            "Translation error: \"A Hisarlik\" for \"Apaméæ\" (Apamea in Phrygia, modern Dinar); "
            "Hisarlik is the site of Troy."
        ),
    },
    "mr:0311-ioannes-kearney": {
        EDITION_EN: (
            "Translation error: \"Clon\" where the Latin has \"Clonæ\" (Clonmel)."
        ),
    },
    "mr:0311-marcus-chong-ui-bae-et-alexius-u-se-yong": {
        EDITION_EN: (
            "Translation error: \"Se-yang\" where the Latin has \"Se-yŏng\"."
        ),
    },
    "mr:0311-oengus-culdeus": {
        EDITION_EN: (
            "Translation error: \"the White Book of the Saints of Ireland\" where the Latin has "
            "\"album sanctórum Hibérniæ\" (a register of the saints of Ireland)."
        ),
    },
    "mr:0313-francisca-trehet": {
        EDITION_IT: (
            "Translation error: \"trafitta con la spada\" (run through with a sword) where the "
            "Latin has only \"ferro\" (by the blade); she was guillotined."
        ),
    },
    "mr:0315-menignus": {
        EDITION_IT: (
            "Translation error: \"tintore\" (dyer) where the Latin has \"fullónis\" (fuller)."
        ),
    },
    "mr:0317-alexandria": {
        EDITION_EN: (
            "Translation error: \"were most cruelly scourged\" where the Latin has \"sævíssime "
            "cæsi\" (most cruelly slain)."
        ),
    },
    "mr:0317-ioannes-sarkander": {
        EDITION_EN: (
            "Translation error: \"the torture of the rack\" where the Latin has \"rotæ "
            "supplício\" (the torture of the wheel)."
        ),
    },
    "mr:0318-anselmus": {
        EDITION_EN: (
            "Translation error: \"where he was a vigorous helper\" where the Latin \"cui "
            "strénuus fuit adiútor\" means he was a vigorous helper to the pope."
        ),
    },
    "mr:0318-cyrillus": {
        EDITION_EN: (
            "Translation error: \"prayers\" where the Latin has \"oratiónibus\" (discourses, "
            "homilies)."
        ),
    },
    "mr:0318-ioannes-thules-et-rogerius-wrenno": {
        EDITION_EN: (
            "Translation error: \"Lancashire\" where the Latin \"Lancástriæ\" is the town of "
            "Lancaster."
        ),
    },
    "mr:0318-salvator-de-horta": {
        EDITION_EN: (
            "Translation error: \"from Girona\" where the Latin has the surname \"Grionesos\"."
        ),
    },
    "mr:0320-iosephus-bilczewski": {
        EDITION_IT: (
            "Misprint: \"Bilezewski\" for the surname Bilczewski."
        ),
    },
    "mr:0322-paulus": {
        EDITION_IT: (
            "Omission: the Latin places the deposition \"extra Urbem\" (outside the city) on the "
            "Via Domitia; this is not rendered."
        ),
    },
    "mr:0323-rebecca-de-himlaya": {
        EDITION_IT: (
            "Translation error: \"Congregazione delle Suore Libanesi Maronite\" where the Latin "
            "has \"Ordine Libanénsi Sancti Antónii Maronitárum\" (the Lebanese Maronite Order of "
            "Saint Anthony)."
        ),
    },
    "mr:0323-turibius-de-mogrovejo": {
        EDITION_IT: (
            "Omission: the Latin clause \"Ecclésiam strénue deféndit\" (he vigorously defended "
            "the Church) is not rendered."
        ),
    },
    "mr:0325-lucia-filippini": {
        EDITION_EN: (
            "Translation error: \"Tuscany\" where the Latin \"Túscia\" is the Tuscia of northern "
            "Lazio."
        ),
    },
    "mr:0325-margarita-clitherow": {
        EDITION_EN: (
            "Translation error: \"the judges\" where the Latin has \"consiliariórum iúdicis\" "
            "(the judge's counsellors, the jurors)."
        ),
    },
    "mr:0325-nicodemus": {
        EDITION_EN: (
            "Translation error: \"Hierax\" where the Latin \"Hierácium\" is Gerace."
        ),
    },
    "mr:0326-bercharius": {
        EDITION_EN: (
            "Translation error: \"Campania\" where the Latin \"Campánia Gálliæ\" is Champagne."
        ),
    },
    "mr:0326-eutychius": {
        EDITION_EN: (
            "Translation error: \"was beaten\" where the Latin \"cæsus est\" means he was slain."
        ),
    },
    "mr:0326-montanus-et-maxima": {
        EDITION_IT: (
            "Translation error: \"Srijem ... nell’odierna Croazia\" where the Latin \"Sírmii\" "
            "is the city of Sirmium (Sremska Mitrovica, in Serbia)."
        ),
    },
    "mr:0327-rupertus": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificávit\" (built)."
        ),
    },
    "mr:0328-conus": {
        EDITION_EN: (
            "Translation error: \"Conon\" where the Latin has \"Coni\" (Conus, Cono)."
        ),
    },
    "mr:0328-priscus-et-socii": {
        EDITION_EN: (
            "Translation error: \"continuously devoured\" where the Latin \"contínuo ... "
            "trádidit\" means he immediately handed them over."
        ),
    },
    "mr:0330-antonius-daveluy-et-socii": {
        EDITION_EN: (
            "Translation error: \"catechists\" where the Latin has \"catechístæ\" in the "
            "singular, of Luke Hwang alone."
        ),
    },
    "mr:0330-petrus-regalado": {
        EDITION_EN: (
            "Translation error: \"Aguilar\" where the Latin has \"Aquilériæ\" (La Aguilera)."
        ),
    },
    "mr:0331-natalia-tulasiewicz": {
        EDITION_EN: (
            "Translation error: \"asphyxiating steam\" where the Latin \"mortíferi vapóris\" "
            "means deadly gas."
        ),
    },
    "mr:0404-gulielmus-cuffitelli": {
        EDITION_EN: (
            "Translation error: \"Scillium\" where the Latin has \"Sicli\" (Scicli)."
        ),
    },
    "mr:0406-irenaeus": {
        EDITION_IT: (
            "Translation error: \"nell’odierna Croazia\" where the Latin \"Sírmii\" (Sirmium) is "
            "the present Sremska Mitrovica, in Serbia. Translation error: \"fu dapprima "
            "frustato\" (was first scourged) where the Latin has \"primum torméntis vexátus "
            "est\" (was first tormented with tortures)."
        ),
    },
    "mr:0407-aibertus": {
        EDITION_EN: (
            "Translation error: \"Saint Albert\" where the Latin has \"sancti Aibérti\" (Saint "
            "Aybert)."
        ),
    },
    "mr:0407-ioannes-baptista-de-la-salle": {
        EDITION_EN: (
            "Translation error: the rank \"Memória\" (Memorial) at the head of the eulogy is "
            "omitted."
        ),
    },
    "mr:0407-theodorus-et-socii": {
        EDITION_EN: (
            "Translation error: \"Ammonius\" where the Latin has \"Ammónis\" (Ammon)."
        ),
    },
    "mr:0408-dominicus-a-sanctissimo-sacramento": {
        EDITION_EN: (
            "Translation error: \"El Buen Monte\" where the Latin has \"in convéntu "
            "Belomontáno\" (the convent of Belmonte)."
        ),
    },
    "mr:0409-demetrius": {
        EDITION_IT: (
            "Translation error: \"nell’odierna Croazia\" where the Latin \"Sírmium\" (Sirmium) "
            "is the present Sremska Mitrovica, in Serbia."
        ),
    },
    "mr:0409-liborius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lyonnese Gaul, the Roman province)."
        ),
    },
    "mr:0411-domnio": {
        EDITION_IT: (
            "Translation error: \"A Spalato\" (Split) where the Latin has \"Salónæ\" (Salona, "
            "the present Solin)."
        ),
    },
    "mr:0411-sympronianus-ducki": {
        EDITION_EN: (
            "Translation error: \"Symphorian\" where the Latin has \"Symproniáni\" (Sympronian)."
        ),
    },
    "mr:0412-ioanna-fernandez-solar": {
        EDITION_IT: (
            "Translation error: \"all’età di venti anni\" (at the age of twenty) where the Latin "
            "has \"vigésimo ætátis anno\" (in her twentieth year, i.e. aged nineteen)."
        ),
    },
    "mr:0412-iulius-i": {
        EDITION_EN: (
            "Translation error: \"Saint Julius, Pope\" omits the ordinal of \"sancti Iúlii papæ "
            "Primi\" (Saint Julius the First, pope)."
        ),
    },
    "mr:0413-ida": {
        EDITION_IT: (
            "Translation error: \"Roosendaal nel Brabante, nell’odierna Olanda\" where the Latin "
            "\"Vallis Rosárum\" is the abbey of Roosendael near Mechelen, in present Belgium."
        ),
    },
    "mr:0413-ida-boloniensis": {
        EDITION_EN: (
            "Translation error: \"near Vasto\" where the Latin has \"prope Vastum in pago Gálliæ "
            "Boloniénsi\" (near Le Wast, in the Boulonnais)."
        ),
    },
    "mr:0413-sabas-reyes": {
        EDITION_LA: (
            "Printing error: \"Totoclán\" for Tototlán, the town in the jurisdiction of "
            "Guadalajara where Saint Sabas Reyes was martyred."
        ),
    },
    "mr:0414-benedictus": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificátus est\" (was built)."
        ),
    },
    "mr:0415-crescens": {
        EDITION_EN: (
            "Translation error: \"Saint Crescentius\" where the Latin has \"sancti Crescéntis\" "
            "(Saint Crescens)."
        ),
    },
    "mr:0415-ortarius": {
        EDITION_EN: (
            "Translation error: \"Andely\" where the Latin has \"monastério Andeleiénsi in pago "
            "Baiocénsi\" (Landelles, in the district of Bayeux)."
        ),
    },
    "mr:0416-optatus-et-socii": {
        EDITION_EN: (
            "Translation error: \"afflicted together with chains\" where the Latin has \"simul "
            "pœnis affécti\" (subjected together to torments)."
        ),
    },
    "mr:0417-robertus-molismensis": {
        EDITION_IT: (
            "Translation error: \"fondò un monastero cistercense\" (founded a Cistercian "
            "monastery) where the Latin has \"Cisterciénse monastérium fundávit\" (founded the "
            "monastery of Cîteaux)."
        ),
    },
    "mr:0418-anthusa": {
        EDITION_EN: (
            "Translation error: \"rebuilding monasteries\" where the Latin has \"monasteriáque "
            "ædificánda\" (building monasteries)."
        ),
    },
    "mr:0419-aelphegus": {
        EDITION_EN: (
            "Translation error: \"Saint Aelphegi\" keeps the Latin genitive of \"Ælphégi\"; the "
            "name is Alphege (Aelphegus)."
        ),
    },
    "mr:0419-geroldus": {
        EDITION_EN: (
            "Translation error: \"Frastanz\" where the Latin has \"Frisæ\" (Frisen)."
        ),
    },
    "mr:0419-mappalicus": {
        EDITION_IT: (
            "Translation error: \"fossero lasciate in pace e per questo\" (that they be left in "
            "peace, and for this reason) where the Latin has \"pacem dari mandávit, sed\" (he "
            "asked that the peace of the Church be granted to them, but he himself)."
        ),
    },
    "mr:0420-mauritius-mackenraghty": {
        EDITION_EN: (
            "Translation error: \"Clon\" where the Latin \"Clonæ\" is Clonmel."
        ),
    },
    "mr:0420-viho": {
        EDITION_IT: (
            "Translation error: \"come primo abate di questo luogo\" (as first abbot of this "
            "place) where the Latin has \"primum abbas ... missus\" (first sent as an abbot, "
            "then made bishop)."
        ),
    },
    "mr:0423-adalbertus": {
        EDITION_EN: (
            "Translation error: \"near the Vistula\" where the Latin has \"ad sinum Venédicum\" "
            "(on the Venedic Gulf, the Baltic gulf of Gdańsk)."
        ),
    },
    "mr:0423-gerardus": {
        EDITION_EN: (
            "Translation error: \"Gerald\" where the Latin has \"Gerárdi\" (Gerard)."
        ),
    },
    "mr:0423-helena-valentinus": {
        EDITION_EN: (
            "Translation error: \"Udine in Venice\" where the Latin has \"in Venétia\" (the "
            "region of Venetia). Translation error: \"Helena of Valentini\" where the Latin "
            "\"Hélenæ Valentíni\" gives her surname (Helena Valentini)."
        ),
    },
    "mr:0423-maria-gabriela-sagheddu": {
        EDITION_EN: (
            "Translation error: \"the Crypt of the Ferrata\" where the Latin \"Cryptæ Ferrátæ\" "
            "is the town of Grottaferrata."
        ),
    },
    "mr:0424-deodatus": {
        EDITION_EN: (
            "Translation error: \"the village of Blesensis in Lyon France\" where the Latin \"in "
            "pago Blesénsi in Gállia Lugdunénsi\" means the district of Blois in Lugdunensian "
            "Gaul."
        ),
    },
    "mr:0424-rosa-virginia-pelletier": {
        EDITION_EN: (
            "Translation error: \"Rose of Virginia\" where the Latin has \"Rosæ Virgíniæ\" (her "
            "baptismal name, Rose Virginia)."
        ),
    },
    "mr:0425-franca": {
        EDITION_EN: (
            "Translation error: \"Frances\" where the Latin has \"Francæ\" (Franca)."
        ),
    },
    "mr:0425-ioannes-piamarta": {
        EDITION_IT: (
            "Translation error: \"nelle vicinanze di una colonia agricola\" (near an "
            "agricultural colony) where the Latin has \"in finítimis colóniam agrícolam\" (he "
            "also founded an agricultural colony nearby)."
        ),
        EDITION_EN: (
            "Translation error: \"in nearby colonies of farmers, promoted the religious "
            "education\" where the Latin \"in finítimis colóniam agrícolam\" says he also "
            "started an agricultural colony nearby."
        ),
    },
    "mr:0425-pasicrates-et-valentio": {
        EDITION_EN: (
            "Translation error: \"Paschyratus and Valentian\" where the Latin has \"Pasícratis "
            "et Valentiónis\" (Pasicrates and Valentio)."
        ),
    },
    "mr:0426-richarius": {
        EDITION_IT: (
            "Translation error: \"monaci scozzesi\" (Scottish monks) where the Latin has "
            "\"monachórum scotórum\" (Irish monks)."
        ),
    },
    "mr:0430-donatus": {
        EDITION_EN: (
            "Translation error: \"Eucea\" where the Latin has \"Eurœæ\" (Euroea)."
        ),
    },
    "mr:0501-marculphus": {
        EDITION_IT: (
            "Translation error: \"Sull’isola di Nanteuil\" where the Latin names Nanteuil only "
            "as his monastery (\"monastérii Nantólii\"), not as the island."
        ),
        EDITION_EN: (
            "Translation error: \"on the island of Brittany\" where the Latin has \"in ínsula "
            "Británniæ Minóris\" (on an island of Brittany)."
        ),
    },
    "mr:0502-boleslaus-strzelecki": {
        EDITION_IT: (
            "Translation error: \"campo di prigionia\" (prison camp) where the Latin has \"campo "
            "exítii\" (extermination camp)."
        ),
    },
    "mr:0503-ansfridus": {
        EDITION_EN: (
            "Translation error: \"Heverlee\" where the Latin has \"monastério Hohorsténsi\" "
            "(Hohorst)."
        ),
    },
    "mr:0504-agapius-et-secundinus": {
        EDITION_EN: (
            "Translation error: \"through their illustrious priesthood\" where the Latin has "
            "\"ex illústri sacerdótio\" (from illustrious priests they became martyrs)."
        ),
    },
    "mr:0504-silvanus-et-socii": {
        EDITION_IT: (
            "Translation error: \"Mismiya\" where the Latin has \"Phænóne\" (the mines of "
            "Phaeno, at Feinan), a different place."
        ),
    },
    "mr:0505-avertinus": {
        EDITION_EN: (
            "Translation error: \"Vendoeuvres\" where the Latin has \"Ventíaci\" (Vençay, now "
            "Saint-Avertin)."
        ),
    },
    "mr:0505-godehardus": {
        EDITION_IT: (
            "Translation error: \"istituì altri monasteri\" (founded) where the Latin has "
            "\"instaurávit\" (restored)."
        ),
    },
    "mr:0505-hilarius": {
        EDITION_EN: (
            "Translation error: \"the basilica of the city\" where the Latin has \"basílicæ "
            "civitátis habuérunt\" (the basilicas of the city)."
        ),
    },
    "mr:0505-iovinianus": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0505-nicetius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0508-catharina-symon-de-longprey": {
        EDITION_EN: (
            "Translation error: \"in the Province of Quebec\" where the Latin has \"In Quebéco "
            "Cánadæ província\" (at Quebec, in the province of Canada)."
        ),
    },
    "mr:0508-helladius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0508-martinus": {
        EDITION_EN: (
            "Translation error: \"Salonne\" where the Latin has \"Saliónii\" (Saujon)."
        ),
    },
    "mr:0509-dionysius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0510-ivanus-merz": {
        EDITION_EN: (
            "Translation error: \"a master of Christ ... the advancement of the lay faithful in "
            "society\" where the Latin has \"magístri Christi fídei inníxi ... in provéctum "
            "societátis\" (a teacher grounded in faith in Christ ... for the advancement of "
            "society)."
        ),
    },
    "mr:0511-gualterius": {
        EDITION_EN: (
            "Translation error: \"Sturpenne\" where the Latin has \"monastério Stirpénsi\" "
            "(Esterp, L'Esterps)."
        ),
    },
    "mr:0511-maiolus": {
        EDITION_IT: (
            "Translation error: \"Sauvigny\" where the Latin has \"Silviníacum\" (Souvigny)."
        ),
    },
    "mr:0511-mamertus": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0512-cyrillus": {
        EDITION_IT: (
            "Translation error: \"Galatz\" where the Latin has \"Axiópoli\" (Axiopolis, at "
            "Cernavodă)."
        ),
    },
    "mr:0512-imelda-lambertini": {
        EDITION_IT: (
            "Translation error: \"con straordinaria devozione\" where the Latin has \"mirándam "
            "Eucharístiæ receptiónem\" (a wondrous reception of the Eucharist)."
        ),
    },
    "mr:0513-andreas-hubertus-fournet": {
        EDITION_EN: (
            "Translation error: \"Le-Puy\" where the Latin has \"Pódii in pago Pictaviénsi\" (La "
            "Puye, near Poitiers)."
        ),
    },
    "mr:0513-servatius": {
        EDITION_EN: (
            "Translation error: \"the natal day heavenly birthday\" where the Latin has "
            "\"natális\" (the heavenly birthday)."
        ),
    },
    "mr:0514-michael-garicoits": {
        EDITION_EN: (
            "Translation error: \"Society of Priests of the Sacred Heart\" where the Latin has "
            "\"Presbyterórum Missionariórum\" (Missionary Priests)."
        ),
    },
    "mr:0515-rheticius": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0516-fidolus": {
        EDITION_EN: (
            "Translation error: \"in Lyon France\" where the Latin has \"in Gállia Lugdunénsi\" "
            "(in Lugdunensian Gaul)."
        ),
    },
    "mr:0516-simon-stock": {
        EDITION_EN: (
            "Translation error: \"Gascony\" where the Latin has \"in Vascónia\"."
        ),
    },
    "mr:0517-adrio": {
        EDITION_EN: (
            "Translation error: \"Adrian\" where the Latin has \"Adriónis\" (Adrio, not Hadrian)."
        ),
    },
    "mr:0517-heraclius-et-paulus": {
        EDITION_IT: (
            "Translation error: \"A Tulcea\" where the Latin has \"Nivedúni\" (Noviodunum, today "
            "Isaccea)."
        ),
    },
    "mr:0518-maria-magdalena-merten": {
        EDITION_IT: (
            "Translation uncertain: \"Mergentheim\" for the Latin \"Maríæ Domo\"; Blessed "
            "Blandina Merten died at Trier."
        ),
    },
    "mr:0519-ioannes-de-cetina-et-petrus-de-duenas": {
        EDITION_EN: (
            "Translation error: \"by order of the king of the Moors\" where the Latin has "
            "\"ipsíus Maurórum regis manu\" (by the hand of the king himself)."
        ),
    },
    "mr:0519-petrus-caelestinus": {
        EDITION_EN: (
            "Translation error: \"when an old man\" where the Latin has \"octogenárius\" (an "
            "octogenarian)."
        ),
    },
    "mr:0525-leo": {
        EDITION_EN: (
            "Translation error: \"Moutier-la-Celle\" where the Latin has \"cœnóbio Mentuníaco\" "
            "(Mantenay)."
        ),
    },
    "mr:0526-andreas-franchi": {
        EDITION_EN: (
            "Translation error: \"formerly of the Order of Preachers\" where the Latin has "
            "\"prior ex Ordine Prædicatórum\" (a prior of the Order of Preachers)."
        ),
    },
    "mr:0526-andreas-kaggwa": {
        EDITION_LA: (
            "Source error: \"Numyanyo\" is a misspelling of Munyonyo, the place of his martyrdom."
        ),
    },
    "mr:0526-lambertus": {
        EDITION_IT: (
            "Translation error: \"A Vance\" where the Latin has \"Véntiæ\" (Vence, in Provence)."
        ),
    },
    "mr:0526-pontianus-ngondwe": {
        EDITION_IT: (
            "Translation error: \"ministro del re\" (minister of the king) where the Latin has "
            "\"satélles régius\" (a royal guard)."
        ),
    },
    "mr:0527-gausbertus": {
        EDITION_EN: (
            "Translation error: \"near Aurillac\" where the Latin has \"apud Arvérnam\" (near "
            "Clermont)."
        ),
    },
    "mr:0601-ioannes-baptista-scalabrinus": {
        EDITION_LA: (
            "Error: \"Pias Societátes a Sacro Corde\" (of the Sacred Heart) for the "
            "congregations Scalabrini founded, which are the Missionaries and Missionary Sisters "
            "of Saint Charles."
        ),
    },
    "mr:0601-proculus": {
        EDITION_EN: (
            "Translation error: \"nails from wooden beams\" where the Latin has \"trabálibus "
            "clavis\" (beam-nails, great spikes)."
        ),
    },
    "mr:0601-wistanus": {
        EDITION_IT: (
            "Translation error: \"Lichester\" where the Latin has \"Licestriénsi\" (Leicester)."
        ),
    },
    "mr:0602-eugenius-i": {
        EDITION_EN: (
            "Translation error: \"Saint Eugene, Pope\" omits the ordinal of \"Eugénii papæ "
            "Primi\" (Eugene the First)."
        ),
    },
    "mr:0603-carolus-renatus-collas-du-bignon": {
        EDITION_EN: (
            "Translation error: \"Callas du Bignon\" where the Latin has \"Collas du Bignon\"."
        ),
    },
    "mr:0603-clotildis": {
        EDITION_EN: (
            "Translation error: \"Lyon France\" where the Latin has \"Gállia Lugdunénsi\" "
            "(Lyonnese Gaul, the province)."
        ),
    },
    "mr:0604-pacificus-ramati": {
        EDITION_EN: (
            "Translation error: \"Sàcceri\" where the Latin \"Sáccere\" is Sassari."
        ),
    },
    "mr:0605-eutychius": {
        EDITION_EN: (
            "Translation error: \"Eucychius\" where the Latin has \"Eutýchii\" (Eutychius)."
        ),
    },
    "mr:0606-petrus-dung-et-petrus-thuan": {
        EDITION_EN: (
            "Translation error: \"Vincent Dung\" where the Latin has \"Vincéntii Ðương\" "
            "(Vincent Dương)."
        ),
    },
    "mr:0608-iacobus-berthieu": {
        EDITION_EN: (
            "Translation error: \"tried with kicks\" where the Latin has \"cálcibus petítus\" "
            "(attacked with kicks)."
        ),
    },
    "mr:0609-primus-et-felicianus": {
        EDITION_EN: (
            "Translation error: \"at the Arenae\" where the Latin has \"ad Arcas\" (at the "
            "Arches)."
        ),
    },
    "mr:0610-henricus-de-bauzano": {
        EDITION_EN: (
            "Translation error: \"of Balsano\" where the Latin \"de Bauzáno\" is Bolzano."
        ),
    },
    "mr:0610-ithamarus": {
        EDITION_IT: (
            "Translation error: \"la gente di Canterbury\" where the Latin has \"gente "
            "Cantuariórum\" (the people of Kent)."
        ),
    },
    "mr:0610-landericus": {
        EDITION_EN: (
            "Translation error: \"rebuilt a hospital\" where the Latin has \"nosocomíum "
            "ædificásse\" (built a hospital)."
        ),
    },
    "mr:0611-ignatius-maloyan": {
        EDITION_EN: (
            "Translation error: \"having fed the captives with the consecrated bread\" where the "
            "Latin has \"consecráto pane pro spiritáli refectióne concaptivórum\" (having "
            "consecrated bread for his fellow prisoners)."
        ),
    },
    "mr:0612-mercedis-maria-a-iesu": {
        EDITION_IT: (
            "Translation error: \"Rivibamba\" for the city of Riobamba (Latin \"Rivibámbæ\")."
        ),
    },
    "mr:0613-augustinus-phan-viet-huy-et-nicolaus-bui-viet-the": {
        EDITION_EN: (
            "Translation error: \"Huu\" where the Latin \"Huéum\" is Huế."
        ),
    },
    "mr:0613-aventinus": {
        EDITION_EN: (
            "Translation error: \"valley of Arbas\" where the Latin \"valle Arbústo\" is the "
            "Larboust valley."
        ),
    },
    "mr:0613-fandila": {
        EDITION_EN: (
            "Translation addition: \"[and martyr]\" is not in the Latin, which has \"presbýteri "
            "et mónachi\"."
        ),
    },
    "mr:0613-ragnebertus": {
        EDITION_IT: (
            "Translation error: \"imprigionato\" (imprisoned) where the Latin has "
            "\"relegatióne\" (banishment)."
        ),
    },
    "mr:0614-protus": {
        EDITION_EN: (
            "Translation error: \"Pratus\" where the Latin has \"Proti\" (Protus)."
        ),
    },
    "mr:0615-aloysius-maria-palazzolo": {
        EDITION_EN: (
            "Translation error: \"Little Sisters of the Poor\" where the Latin has \"Sorórum "
            "Pauperculárum\" (the Poor Sisters, Poverelle)."
        ),
    },
    "mr:0615-barbara-cui-lianzhi": {
        EDITION_IT: (
            "Translation error: \"Presso la città di Liushuitao nel territorio di "
            "Qianshengzhuang\" where the Latin has the village (pagus) of Qianshengzhuang near "
            "the city of Liushuitao."
        ),
    },
    "mr:0615-petrus-snow-et-radulphus-grimston": {
        EDITION_EN: (
            "Translation error: \"and suffered the punishment of the gibbet\" reads as part of "
            "the second martyr's offence; the Latin \"passi sunt\" says both suffered the "
            "gallows."
        ),
    },
    "mr:0616-similianus": {
        EDITION_EN: (
            "Translation error: \"in Lyon\" where the Latin has \"in Lugdunénsi\" (in the "
            "province of Gallia Lugdunensis, not the city of Lyon)."
        ),
    },
    "mr:0618-calogerus": {
        EDITION_IT: (
            "Translation error: \"monte Gemmariaro\" where the Latin has \"monte Chronio\" "
            "(Monte Kronio, above Sciacca)."
        ),
    },
    "mr:0619-gervasius-et-protasius": {
        EDITION_EN: (
            "Translation error: \"rebuilt by him\" where the Latin has \"ab ipso ædificátam\" "
            "(built by him)."
        ),
    },
    "mr:0619-romualdus": {
        EDITION_EN: (
            "Translation error: \"rebuilding small monasteries\" where the Latin has \"párvula "
            "monastéria ædíficans\" (building)."
        ),
    },
    "mr:0620-gobanus": {
        EDITION_EN: (
            "Translation note: \"Saint Fursa\" where the Latin has \"sancti Fusci\" (Saint "
            "Fuscus)."
        ),
    },
    "mr:0620-margarita-ball": {
        EDITION_IT: (
            "Translation error: the Latin says she died \"in carcere\" (in prison) after \"varia "
            "genera molestiarum\" (various hardships); the text omits the prison and speaks of "
            "\"varie torture\"."
        ),
    },
    "mr:0621-mevennus": {
        EDITION_IT: (
            "Translation error: \"A Ghé\" where the Latin has \"Gaeli\" (Gaël)."
        ),
        EDITION_EN: (
            "Translation error: \"Grel\" where the Latin has \"Gæli\" (Gaël)."
        ),
    },
    "mr:0621-radulphus": {
        EDITION_EN: (
            "Translation error: \"to gather with the priests ..., {reading} chapters\" where the "
            "Latin has \"cum presbýteris ... capítula ... collígere curávit\" (took care, with "
            "the priests, to collect chapters)."
        ),
    },
    "mr:0622-iulius-et-aaron": {
        EDITION_LA: (
            "Editorial error: \"in Britannia Minore\" (Brittany), but Caerleon, the City of the "
            "Legions, is in Britain (Wales)."
        ),
    },
    "mr:0623-ediltrudis": {
        EDITION_IT: (
            "Translation error: \"rifiutate per due volte le nozze\" (twice refused marriage) "
            "where the Latin has \"bis nuptiis posthabitis\" (having twice set her marriages "
            "aside); she was twice married."
        ),
    },
    "mr:0624-agoardus-et-agilbertus": {
        EDITION_EN: (
            "Translation error: \"Aglibert\" where the Latin has \"Agilbérti\" (Agilbert)."
        ),
    },
    "mr:0624-gohardus": {
        EDITION_EN: (
            "Translation error: \"Gobard\" where the Latin has \"Gohárdi\" (Gohard)."
        ),
    },
    "mr:0625-molochus": {
        EDITION_EN: (
            "Translation error: \"Rossmarkre\" where the Latin has \"Rossmárkæi\" (Rosemarkie)."
        ),
    },
    "mr:0626-anthelmus": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" (Burgundy) where the Latin has \"in Sabaudia\" "
            "(Savoy)."
        ),
    },
    "mr:0626-magdalena-fontaine-et-socii": {
        EDITION_EN: (
            "Translation error: \"crowned with mockery and led to execution with the Rosary\" "
            "where the Latin has \"per ludíbrium coronátæ Rosário\" (crowned in mockery with the "
            "Rosary)."
        ),
    },
    "mr:0626-vigilius": {
        EDITION_EN: (
            "Translation error: \"distinguished instruction\" where the Latin has "
            "\"institutiónis insígnibus\" (the insignia of his office)."
        ),
    },
    "mr:0628-lucia-wang-cheng-et-socii": {
        EDITION_EN: (
            "Translation error: \"Qi Yu\" where the Latin has \"Maríæ Qi Yu\" (Maria Qi Yu)."
        ),
    },
    "mr:0630-ladislaus": {
        EDITION_LA: (
            "Source error: \"ad Vagum flumen\" (on the river Váh), but Nitra lies on the river "
            "Nitra."
        ),
    },
    "mr:0630-protomartyres-sanctae-romanae-ecclesiae": {
        EDITION_EN: (
            "Translation error: \"the most savage emperor Nero\" where the Latin has \"sævíssime "
            "intérfici\" (to be killed most savagely)."
        ),
    },
    "mr:0630-raymundus-li-quanzhen-et-petrus-li-quanhui": {
        EDITION_EN: (
            "Translation error: \"Jiaobei\" where the Latin has \"Jiaohe\"."
        ),
    },
    "mr:0703-leo-ii": {
        EDITION_EN: (
            "Translation error: \"undertook\" where the Latin has \"suscépit\" (received, that "
            "is, accepted the Council)."
        ),
    },
    "mr:0704-caesidius-giacomantonio": {
        EDITION_EN: (
            "Translation error: \"a mob of soldiers\" where the Latin has \"satéllitum turba\" "
            "(a mob of henchmen)."
        ),
    },
    "mr:0704-petrus-georgius-frassati": {
        EDITION_EN: (
            "Translation error: \"stirring up the Society\" where the Latin has \"in societátem "
            "excitándam\" (the betterment of society)."
        ),
    },
    "mr:0706-elias-desgardin": {
        EDITION_IT: (
            "Translation error: \"Septfontaines\" where the Latin has \"Septem Fóntium\" (the "
            "Cistercian abbey of Sept-Fons)."
        ),
        EDITION_EN: (
            "Translation error: \"Elisée\" where the Latin has \"Elíæ\" (Élie)."
        ),
    },
    "mr:0706-maria-goretti": {
        EDITION_IT: (
            "Translation error: \"a dodici anni\" (at twelve years of age) where the Latin has "
            "\"duodécimo ætátis anno\" (in her twelfth year, that is, aged eleven)."
        ),
    },
    "mr:0706-maria-rosa-de-loye": {
        EDITION_EN: (
            "Translation error: \"de Laye\" where the Latin has \"de Loye\"."
        ),
    },
    "mr:0707-marcus-ji-tianxiang": {
        EDITION_IT: (
            "Translation error: \"Jixian\" where the Latin has \"Ueihœivénsem\" (Weixian)."
        ),
    },
    "mr:0708-eugenius-iii": {
        EDITION_IT: (
            "Translation error: \"dalle insidie dell’eresia\" (from the snares of heresy) where "
            "the Latin has \"ab infidélium insídiis\" (from the snares of unbelievers)."
        ),
    },
    "mr:0708-ioannes-wu-wenyin": {
        EDITION_EN: (
            "Translation error: \"condemned to death by beheading\" where the Latin has only "
            "\"cápite damnátus\" (condemned to death)."
        ),
    },
    "mr:0709-ioachim-he-kaizhi": {
        EDITION_EN: (
            "Translation error: \"Qingyan\" where the Latin has \"Cœiiaménsi\" (Guiyang)."
        ),
    },
    "mr:0710-antonius-nguyen-huu-quynh-et-petrus-nguyen-khac-tu": {
        EDITION_IT: (
            "Translation error: \"Nguyễn (Nam) Quỳnh\" omits \"Hữu\", which the Latin gives as "
            "\"Nguyễn Hữu (Nam) Quỳnh\"."
        ),
    },
    "mr:0710-emmanuel-ruiz-et-socii": {
        EDITION_EN: (
            "Translation error: \"three lay brothers\" where the Latin has \"trium germanórum "
            "fidélium\" (three blood brothers, lay faithful)."
        ),
    },
    "mr:0711-abundius": {
        EDITION_EN: (
            "Translation error: \"was killed, seized by sudden indignation\" where the Latin has "
            "\"céleri indignatióne mota, perémptus est\" (sudden indignation being roused, he "
            "was killed). Translation error: \"[martyr]\" added; the Latin has only "
            "\"presbýteri\"."
        ),
    },
    "mr:0711-anna-an-xinzhi-et-socii": {
        EDITION_IT: (
            "Misprint: \"Maia An Guozhi\" for \"Maria An Guozhi\"."
        ),
    },
    "mr:0712-nabor-et-felix": {
        EDITION_IT: (
            "Translation error: \"a Lodi\" where the Latin has \"Laude Pompéia\" (Laus Pompeia, "
            "today Lodi Vecchio)."
        ),
    },
    "mr:0713-clelia-barbieri": {
        EDITION_EN: (
            "Translation error: \"Budrio\" where the Latin has \"Búdriæ\" (Budrie)."
        ),
    },
    "mr:0713-henricus": {
        EDITION_LA: (
            "Source error: \"in Francónia\" (in Franconia), but Grona near Göttingen lies in "
            "Saxony."
        ),
    },
    "mr:0714-camillus-de-lellis": {
        EDITION_EN: (
            "Translation error: \"Theano\" where the Latin has \"Theánum in Aprútio\" (Chieti)."
        ),
    },
    "mr:0714-franciscus-solano": {
        EDITION_IT: (
            "Translation error: \"la testimonianza\" (witness) where the Latin has \"signis\" "
            "(signs, that is, miracles)."
        ),
    },
    "mr:0714-gaspar-de-bono": {
        EDITION_IT: (
            "Translation error: \"per amore della casa dell’Ordine nella provincia spagnola, che "
            "resse con prudenza e carità\" where the Latin has \"domus provínciæ hispánæ Ordinis "
            "zelo, prudéntia et caritáte rexit\" (he governed the houses of the Spanish province "
            "of the Order with zeal, prudence and charity)."
        ),
    },
    "mr:0716-lang-yangzhi-et-paulus-lang-fu": {
        EDITION_EN: (
            "Translation error: \"Lijiapo\" where the Latin has \"Lüjiapo\"."
        ),
    },
    "mr:0716-maria-magdalena-postel": {
        EDITION_EN: (
            "Translation error: \"in extréma inópia\" (in extreme poverty) is omitted."
        ),
    },
    "mr:0716-teresia-zhang-hezhi": {
        EDITION_IT: (
            "Translation error: the title \"martire\" is missing after \"santa Teresa Zhang "
            "Hezhi\"; the Latin has \"mártyris\"."
        ),
    },
    "mr:0717-zoerardus-et-benedictus": {
        EDITION_LA: (
            "Source error: \"ad Vagum flumen\" (on the river Váh), but Nitra lies on the river "
            "Nitra."
        ),
    },
    "mr:0718-dominicus-nicolaus-dinh-dat": {
        EDITION_IT: (
            "Translation error: \"per espiare la colpa dell’apostasia\" where the Latin has "
            "\"pretio apostasiae reddito\" (having returned the reward given for his apostasy)."
        ),
        EDITION_EN: (
            "Translation error: \"paid the price of his apostasy\" where the Latin \"prétio "
            "apostásiæ réddito\" means he returned the reward given him for apostatizing."
        ),
    },
    "mr:0718-maternus": {
        EDITION_EN: (
            "Translation error: \"Laud Pompey\" where the Latin has \"Laude Pompéia\" (Lodi "
            "Vecchio)."
        ),
    },
    "mr:0718-symphorosa-et-socii": {
        EDITION_IT: (
            "Translation error: \"con diversi generi di tortura\" where the Latin has \"diverso "
            "mortis exitu\" (by different kinds of death)."
        ),
    },
    "mr:0719-achilles-puchala-et-hermannus-stepien": {
        EDITION_IT: (
            "Translation error: \"sacerdote\" (singular) where the Latin has \"presbyterorum\" "
            "(both were priests)."
        ),
    },
    "mr:0719-dius-thaumaturgus": {
        EDITION_EN: (
            "Translation error: \"Dii\" (a Latin genitive) where the name is Dius."
        ),
    },
    "mr:0719-stilla": {
        EDITION_EN: (
            "Translation error: \"Marienberg\" where the Latin has \"Mariæbúrgi\" (Marienburg)."
        ),
    },
    "mr:0720-magdalena-yi-yong-hui-et-socii": {
        EDITION_EN: (
            "Translation error: the names \"Terésiæ\", \"Marthæ\", \"Lúciæ\", \"Rosæ\" and "
            "\"Mariæ\" are left in Latin case forms (Teresa, Martha, Lucy, Rose, Mary)."
        ),
    },
    "mr:0721-iosephus-wang-yumei": {
        EDITION_EN: (
            "Translation error: \"Yomenienina\" where the Latin \"Iomnienínam\" is the city of "
            "Yongnian."
        ),
    },
    "mr:0721-victor": {
        EDITION_EN: (
            "Translation error: \"the province of France\" where the Latin \"in Província "
            "Gálliæ\" means Provence."
        ),
    },
    "mr:0722-martyres-massilitani": {
        EDITION_EN: (
            "Translation error: \"of Massilia\" (Marseilles) where the Latin \"Massilitanórum\" "
            "denotes the African Massylitan martyrs."
        ),
    },
    "mr:0723-birgitta": {
        EDITION_EN: (
            "Translation error: \"the Mystical Church\" where the Latin \"mýstice reformándis\" "
            "speaks of reforming the Church mystically."
        ),
    },
    "mr:0723-severus": {
        EDITION_EN: (
            "Translation error: \"having won the palm of martyrdom\" where the Latin has "
            "\"mártyrum palmas æmulátus\" (emulating the martyrs' palms)."
        ),
    },
    "mr:0724-boris-et-gleb": {
        EDITION_IT: (
            "Translation error: \"principi di Rostov\" where the Latin has \"principes Rutheni\" "
            "(princes of the Rus')."
        ),
    },
    "mr:0724-maria-a-mercede-prat": {
        EDITION_EN: (
            "Translation error: \"though a religious\" where the Latin \"cum religiósa esset\" "
            "means because she was a religious."
        ),
    },
    "mr:0725-petrus-a-corde-et-socii": {
        EDITION_EN: (
            "Translation error: \"Peter of the Heart\" omits the surname \"Redondo\" given in "
            "the Latin."
        ),
    },
    "mr:0726-hugo-de-actis": {
        EDITION_EN: (
            "Translation error: \"Hugh of the Acts\" where \"de Actis\" is a surname (Hugh de "
            "Actis)."
        ),
    },
    "mr:0727-ecclesius": {
        EDITION_EN: (
            "Translation error: \"stood firm\" where the Latin \"solus in superándis\" says he "
            "alone survived them."
        ),
    },
    "mr:0727-georgius-et-socii": {
        EDITION_EN: (
            "Translation error: \"George, deacon, and Syrian, monk\" where the Latin describes "
            "George as a Syrian deacon and monk."
        ),
    },
    "mr:0727-maria-clemens-a-iesu-crucifixo": {
        EDITION_EN: (
            "Translation error: \"Maria Clementina\" where the Latin has \"Maríæ Cleméntis\" "
            "(Maria Clemens)."
        ),
    },
    "mr:0728-melchior-garcia-sanpedro": {
        EDITION_EN: (
            "Translation error: \"beaten to death, his limbs crushed\" where the Latin \"membris "
            "cæsus\" means cut limb from limb."
        ),
    },
    "mr:0729-iosephus-zhang-wenlan-et-paulus-chen-changpin": {
        EDITION_IT: (
            "Translation error: \"in una cava\" (a quarry) where the Latin has \"in cavea\" (a "
            "cage)."
        ),
    },
    "mr:0729-lucius-martinez-mancebo-et-socii": {
        EDITION_EN: (
            "Translation error: \"thirteen martyrs\" is added; the Latin \"et sociórum\" gives "
            "no number."
        ),
    },
    "mr:0729-lupus": {
        EDITION_LA: (
            "Edition error: \"Británniam Minórem\" (Brittany) where the mission of Germanus and "
            "Lupus against the Pelagians was to Britain."
        ),
    },
    "mr:0731-fabius": {
        EDITION_EN: (
            "Translation error: \"imperial standards\" where the Latin has \"vexílla "
            "præsidália\" (the governor's standards)."
        ),
    },
    "mr:0731-ignatius-de-loyola": {
        EDITION_IT: (
            "Translation error: \"nato nella Guascogna\" (Gascony) where the Latin \"in "
            "Vasconia\" means the Basque country, where Loyola lies."
        ),
    },
    "mr:0801-ethelwoldus": {
        EDITION_IT: (
            "Translation error: \"tradusse\" (translated) the \"Concordia dei monaci\" where the "
            "Latin has \"exarávit\" (composed)."
        ),
    },
    "mr:0803-euphronius": {
        EDITION_EN: (
            "Translation error: \"rebuilt the basilica\" where the Latin has \"ædificávit\" "
            "(built)."
        ),
    },
    "mr:0803-petrus": {
        EDITION_EN: (
            "Translation error: \"completed the rebuilding\" where the Latin has \"ædificatiónem "
            "perfécit\" (completed the building)."
        ),
    },
    "mr:0804-iustinus-et-crescention": {
        EDITION_EN: (
            "Translation error: \"Crescentius\" where the Latin has \"Crescentiónis\" "
            "(Crescentio)."
        ),
    },
    "mr:0804-onuphrius": {
        EDITION_EN: (
            "Translation error: \"Panaria\" where the Latin has \"Panáiæ\" (Panaia)."
        ),
    },
    "mr:0805-franciscus-zanfredini": {
        EDITION_EN: (
            "Translation error: \"the hermitage he had rebuilt\" where the Latin has \"quem "
            "ædificáverat\" (which he had built)."
        ),
    },
    "mr:0805-oswaldus": {
        EDITION_IT: (
            "Translation error: \"nello Shrewsbury\" where the Latin \"in agro Salopiénsi\" is "
            "the county of Shropshire."
        ),
    },
    "mr:0805-viator": {
        EDITION_EN: (
            "Translation error: \"the region of Saintes\" where the Latin has \"Secaláunia\" "
            "(the Sologne)."
        ),
    },
    "mr:0806-dominicus": {
        EDITION_EN: (
            "Translation error: \"the nativity\" where the Latin \"natális\" means the birth "
            "into heaven (his death)."
        ),
    },
    "mr:0806-iustus-et-pastor": {
        EDITION_EN: (
            "Translation error: \"beheaded\" where the Latin has \"gládio iuguláti\" (their "
            "throats were cut with the sword)."
        ),
    },
    "mr:0806-transfiguratio-domini": {
        EDITION_EN: (
            "Translation error: \"the glorious restoration of our nature ... was to be joined to "
            "him\" where the Latin has \"servílis formæ nostræ ipsi coaptátæ\" (our servile "
            "form, fitted to himself)."
        ),
    },
    "mr:0807-albertus-de-abbatibus": {
        EDITION_EN: (
            "Translation error: \"Albert of the Abbeys\" where the Latin \"de Abbátibus\" is the "
            "family name (degli Abbati)."
        ),
    },
    "mr:0808-maria-a-iesu-infante-et-socii": {
        EDITION_EN: (
            "Translation error: \"two virgin martyrs\" is not in the Latin, which gives no "
            "number of companions."
        ),
    },
    "mr:0809-claudius-richard": {
        EDITION_EN: (
            "Translation error: \"the monastery of Mèze\" where the Latin has \"Mediáno "
            "monastério\" (Moyenmoutier)."
        ),
    },
    "mr:0809-nathaeus": {
        EDITION_EN: (
            "Translation error: \"Aghagower\" where the Latin has \"Achadénsi\" (Achonry)."
        ),
    },
    "mr:0809-ruben-a-iesu-lopez-aguilar-et-socii": {
        EDITION_IT: (
            "Translation error: \"in odio alla fede\" where the Latin has \"in ódium vitæ "
            "religiósæ\" (in hatred of the religious life)."
        ),
    },
    "mr:0810-laurentius": {
        EDITION_IT: (
            "Translation error: \"nutrito e sfamato con dei beni elemosinati\" where the Latin "
            "has \"in quorum victum atque vestiméntum facultátes cumuláverat\" (on whose food "
            "and clothing he had spent the Church's goods)."
        ),
    },
    "mr:0811-clara": {
        EDITION_EN: (
            "Translation error: \"she was never allowed to be separated\" where the Latin has "
            "\"numquam divélli concéssit\" (she never allowed herself to be parted from it)."
        ),
    },
    "mr:0811-equitius": {
        EDITION_IT: (
            "Translation error: \"nel territorio dell'odierna Umbria\" where the Latin has \"in "
            "província Valériæ\", a province lying chiefly in present-day Abruzzo."
        ),
    },
    "mr:0811-ioannes-sandys-et-stephanus-rowsham": {
        EDITION_EN: (
            "Translation error: \"layman\" where the Latin has \"manuleárii\" (a tailor)."
        ),
    },
    "mr:0813-gertrudis": {
        EDITION_EN: (
            "Translation error: \"the region of Oldenburg\" where the Latin has \"in terra "
            "Vocatórum\" (near Wetzlar)."
        ),
    },
    "mr:0813-secundinus-maria-ortega-garcia-et-socii": {
        EDITION_IT: (
            "Translation error: \"in odio alla fede\" where the Latin has \"in ódium vitæ "
            "religiósæ\" (in hatred of the religious life)."
        ),
    },
    "mr:0815-ludovicus-masferrer-vila-et-socii": {
        EDITION_IT: (
            "Translation error: \"affidarono la loro vita a Cristo\" (entrusted their life to "
            "Christ) where the Latin has \"in Christo vitam posuérunt\" (laid down their lives "
            "in Christ)."
        ),
    },
    "mr:0815-straton-et-socii": {
        EDITION_EN: (
            "Translation error: \"Eutychius\" where the Latin has \"Euthychiáni\" (Eutychian)."
        ),
    },
    "mr:0816-iosephus-maria-sanchis-mompo": {
        EDITION_EN: (
            "Translation error: \"Capuchin Sisters\" where the Latin has \"Capulatórum\" (the "
            "Capuchin Tertiaries, a congregation of men)."
        ),
    },
    "mr:0816-simon-bokusai-kyota-et-socii": {
        EDITION_EN: (
            "Translation error: \"the prefect of Yetsundo\" where the Latin has \"præfécti "
            "Yetsundo\" (the prefect Yetsundo)."
        ),
    },
    "mr:0819-guerricus": {
        EDITION_EN: (
            "Translation error: \"spiritual words, humility, and frequent charity\" where the "
            "Latin has \"sermónibus humilitáte et caritáte crebris\" (sermons full of humility "
            "and charity)."
        ),
    },
    "mr:0819-ludovicus": {
        EDITION_EN: (
            "Translation error: \"the Province of France\" where the Latin has \"Província\" "
            "(Provence). Translation error: \"perpetually\" where the Latin has \"pérpeti\" (to "
            "endure)."
        ),
    },
    "mr:0821-iosephus-dang-dinh-vien": {
        EDITION_EN: (
            "Translation error: \"Đình Viên (Em-Dinh-Nien)\" where the Latin has \"Ðặng Ðình "
            "(Niên) Viên\"."
        ),
    },
    "mr:0822-timotheus": {
        EDITION_EN: (
            "Translation error: \"the cemetery of the same name\" where the Latin has \"in "
            "cœmetério eiúsdem\" (in his own cemetery)."
        ),
    },
    "mr:0824-maximianus-binkiewicz": {
        EDITION_LA: (
            "Error in the Latin: \"Maximiáni\" (Maximian) where the blessed's name is Maximilian "
            "(Maksymilian)."
        ),
    },
    "mr:0824-tatio": {
        EDITION_IT: (
            "Translation error: \"Eskihisar\" where the Latin has \"Claudiopoli in Honoriade\" "
            "(Claudiopolis, the modern Bolu)."
        ),
        EDITION_EN: (
            "Translation error: \"Tatian\" where the Latin has \"Tatiónis\" (Tatio)."
        ),
    },
    "mr:0825-paulus-ioannes-charles": {
        EDITION_IT: (
            "Translation error: \"Septfontaines\" where the Latin has \"Septem Fontium\" (the "
            "Cistercian abbey of Sept-Fons)."
        ),
    },
    "mr:0825-thomas-cantelupe": {
        EDITION_EN: (
            "Translation error: \"Tuscany\" where the Latin has \"Túscia\" (Tuscia, now in "
            "Lazio)."
        ),
    },
    "mr:0826-alexander-max-ginestar": {
        EDITION_EN: (
            "Translation error: \"Benisa\" where the Latin has \"Hemeroscópii\" (Dénia)."
        ),
    },
    "mr:0826-ioanna-elisabeth-bichier": {
        EDITION_EN: (
            "Translation error: \"At Poitiers\" where the Latin has \"Pódii apud Pictávium\" (at "
            "La Puye near Poitiers)."
        ),
    },
    "mr:0827-ferdinandus-gonzalez-anon": {
        EDITION_EN: (
            "Translation error: \"Afiñón\" where the Latin has \"Añón\"."
        ),
    },
    "mr:0828-florentina": {
        EDITION_EN: (
            "Translation error: \"was entrusted ... with treatises\" where the Latin has "
            "\"tractátus ... despondérunt\" (dedicated treatises to her)."
        ),
    },
    "mr:0828-iuniperus-serra": {
        EDITION_IT: (
            "Translation error: \"Monterrey\" where the Latin has \"Monte Regali in California\" "
            "(Monterey)."
        ),
    },
    "mr:0829-basilla": {
        EDITION_IT: (
            "Translation error: \"Srijem nell’odierna Croazia\" where the Latin has \"Sirmium\" "
            "(the city, now Sremska Mitrovica in Serbia)."
        ),
        EDITION_EN: (
            "Translation error: \"Basilia\" where the Latin has \"Basíllæ\" (Basilla)."
        ),
    },
    "mr:0829-ludovicus-vulfilacius-huppy": {
        EDITION_EN: (
            "Translation error: \"died, emaciated, in exile\" where the Latin has \"ægrótus "
            "óbiit\" (died sick)."
        ),
    },
    "mr:0829-sebbus": {
        EDITION_IT: (
            "Translation error: \"re della Sassonia orientale\" where the Latin has \"rex "
            "Saxonum orientalium\" (king of the East Saxons, Essex)."
        ),
    },
    "mr:0829-victor": {
        EDITION_IT: (
            "Translation error: \"La Chambon\" where the Latin has \"Campum Bonum\" (Campbon, "
            "near Nantes)."
        ),
    },
    "mr:0830-agilus": {
        EDITION_EN: (
            "Translation error: \"Aegilius\" where the Latin has \"Agíli\" (Agilus)."
        ),
    },
    "mr:0830-vincentius-cabanes-badenas": {
        EDITION_EN: (
            "Translation error: \"Santander\" where the Latin has \"Flaviobrígæ\"."
        ),
    },
    "mr:0831-aidanus": {
        EDITION_IT: (
            "Translation error: \"chiamato ... a questa sede episcopale, dove fondò un "
            "monastero\" where the Latin says he established both the see and the monastery "
            "there."
        ),
    },
    "mr:0901-aegidius": {
        EDITION_EN: (
            "Translation error: \"grew into Saint-Gilles-du-Gard\" where the Latin has \"in "
            "Camária excrévit\" (grew up in the Camargue)."
        ),
    },
    "mr:0901-victorius": {
        EDITION_EN: (
            "Translation error: \"Victor\" where the Latin has \"Victórii\" (Victorius)."
        ),
    },
    "mr:0902-ioannes-maria-du-lau-et-socii": {
        EDITION_EN: (
            "Translation error: \"of Laud’Allemans\" where the Latin has \"du Lau d’Allemans\". "
            "Translation error: \"blessed martyr saints\" where the Latin has \"beatórum "
            "mártyrum\" (blessed martyrs)."
        ),
    },
    "mr:0903-guala": {
        EDITION_EN: (
            "Translation error: \"region of Asti\" where the Latin has \"pago Astinénsi\" (the "
            "district of Astino)."
        ),
    },
    "mr:0905-ioannes-bonus-de-siponto": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificávit\" (built)."
        ),
    },
    "mr:0906-bega": {
        EDITION_EN: (
            "Translation error: \"virgin and nun\" where the Latin has only \"moniális\" (nun)."
        ),
    },
    "mr:0907-marcus-crisini-et-socii": {
        EDITION_EN: (
            "Translation error: \"torture, or the agony of fire\" where the Latin has \"rotæ "
            "ignísque torméntis\" (the torments of the wheel and of fire)."
        ),
    },
    "mr:0907-memorius-et-socii": {
        EDITION_EN: (
            "Translation error: \"Bar-sur-Aube\" where the Latin has \"Brólii\" (Breuil)."
        ),
    },
    "mr:0908-bonifatius-rodriguez-gonzalez-et-socii": {
        EDITION_EN: (
            "Translation error: \"Crecilius\" where the Latin has \"Cæcílii\" (Caecilius)."
        ),
    },
    "mr:0908-petrus-de-chavanon": {
        EDITION_EN: (
            "Translation error: \"rebuilt a monastery\" where the Latin has \"ædificávit\" "
            "(built)."
        ),
    },
    "mr:0909-emma-uffing": {
        EDITION_EN: (
            "Translation error: \"Offing\" where the Latin has \"Üffing\"."
        ),
    },
    "mr:0910-sebastianus-kimura-et-socii": {
        EDITION_EN: (
            "Translation error: \"eight of them priests\" where the Latin has only \"presbýteri, "
            "religiósi\" (priests, religious), without a number."
        ),
    },
    "mr:0911-paphnutius": {
        EDITION_IT: (
            "Translation error: \"il tendine del piede sinistro\" (the tendon of the left foot) "
            "where the Latin has \"sinístro póplite\" (the left hamstring)."
        ),
    },
    "mr:0912-guido": {
        EDITION_IT: (
            "Translation error: \"Mariensee\" where the Latin has \"Maríæ Laci\" (Our Lady of "
            "Laeken, near Brussels)."
        ),
    },
    "mr:0914-cornelius": {
        EDITION_IT: (
            "Translation error: \"molti dissidenti\" (many dissidents) where the Latin has "
            "\"plures de lapsis\" (many of the lapsed, who had denied the faith in persecution)."
        ),
    },
    "mr:0914-cyprianus": {
        EDITION_IT: (
            "Translation error: \"trafitto con la spada\" (pierced with the sword) where the "
            "Latin has \"gládio animadvérti\" (executed by the sword, i.e. beheaded)."
        ),
    },
    "mr:0915-alpinus": {
        EDITION_IT: (
            "Translation error: \"sant’Albino\" where the Latin has \"sancti Alpíni\" (Alpinus)."
        ),
    },
    "mr:0915-ioannes-baptista-et-hyacinthus-ab-angelis": {
        EDITION_EN: (
            "Translation error: \"Xagada\" where the Latin has \"Xagacía\"."
        ),
    },
    "mr:0915-straton-et-socii": {
        EDITION_EN: (
            "Translation error: \"Stratonis\" where the Latin has \"Stratónis\" (of Straton)."
        ),
    },
    "mr:0916-ludovicus-aleman": {
        EDITION_EN: (
            "Translation error: \"Salles\" where the Latin has \"Sali\" (Salon)."
        ),
    },
    "mr:0916-rogellus-et-servusdei": {
        EDITION_IT: (
            "Translation error: \"mani e piedi\" (hands and feet) where the Latin has \"mánibus "
            "cruribúsque\" (hands and legs)."
        ),
    },
    "mr:0916-vitalis": {
        EDITION_EN: (
            "Translation error: \"the monasteries he founded\" where the Latin has \"cœnóbium ab "
            "ipso cónditum\" (the monastery he founded)."
        ),
    },
    "mr:0919-arnulphus": {
        EDITION_IT: (
            "Translation error: \"si adoperò molto\" (he worked hard) where the Latin has "
            "\"multa sustínuit\" (he endured much)."
        ),
    },
    "mr:0919-eustochius": {
        EDITION_EN: (
            "Translation error: \"the region of Lyon\" where the Latin has \"in Gállia "
            "Lugdunénsi\" (the province of Lugdunensian Gaul)."
        ),
    },
    "mr:0919-sequanus": {
        EDITION_IT: (
            "Translation error: \"Sisteron\" (a town in Provence) for the monastery the Latin "
            "places \"apud Língones\" (near Langres); this is Segestre, now Saint-Seine-l'Abbaye."
        ),
    },
    "mr:0920-hypatius-et-asianus": {
        EDITION_EN: (
            "Translation error: \"Asias\" where the Latin has \"Asiáni\" (Asianus)."
        ),
    },
    "mr:0921-eusebius-et-socii": {
        EDITION_EN: (
            "Translation error: \"seized and killed\" where the Latin has \"discérpti atque "
            "necáti\" (torn to pieces and killed)."
        ),
    },
    "mr:0921-vincentius-galbis-girones-et-emmanuel-torro-garcia": {
        EDITION_EN: (
            "Translation error: \"Torre\" where the Latin has \"Torró\"."
        ),
    },
    "mr:0922-basilla": {
        EDITION_EN: (
            "Translation error: \"Basilia\" where the Latin has \"Basíllæ\" (Basilla)."
        ),
    },
    "mr:0922-silvanus": {
        EDITION_EN: (
            "Translation error: \"Lurais\" where the Latin has \"Libróso\" (Levroux)."
        ),
    },
    "mr:0923-pius-de-pietrelcina": {
        EDITION_EN: (
            "Translation error: the rank \"Memorial\" is missing where the Latin begins "
            "\"Memória sancti Pii\"."
        ),
    },
    "mr:0925-paulus-et-tatta": {
        EDITION_EN: (
            "Translation error: \"Tatia\" where the Latin has \"Tattæ\" (Tatta)."
        ),
    },
    "mr:0925-sergius-de-radonez": {
        EDITION_IT: (
            "Translation error: \"a Mosca\" (in Moscow) where the Latin has \"in Mosquénsi "
            "Rússiæ regióne\" (in the Moscow region); the monastery is not in the city."
        ),
    },
    "mr:0925-solemnis": {
        EDITION_EN: (
            "Translation error: \"the region of Lyon\" where the Latin has \"in Gállia "
            "Lugdunénsi\" (the province of Lugdunensian Gaul)."
        ),
    },
    "mr:0926-emmanuel-legua-marti": {
        EDITION_EN: (
            "Translation error: \"Capuchin Sisters\" where the Latin has \"Capulatórum\" (the "
            "Capuchin Tertiaries, a men's order)."
        ),
    },
    "mr:0929-michael-gabriel-et-raphael-archangeli": {
        EDITION_EN: (
            "Translation error: \"long ago rebuilt\" where the Latin has \"antíquitus "
            "ædificátæ\" (built long ago)."
        ),
    },
    "mr:1001-florentia-caerols-martinez": {
        EDITION_EN: (
            "Translation error: \"Florentina\" where the Latin has \"Floréntiæ\" (Florentia)."
        ),
    },
    "mr:1001-gaspar-hikojiro-et-andreas-yoshida": {
        EDITION_EN: (
            "Translation error: the title \"martyrs\" (Latin \"mártyrum\") is omitted."
        ),
    },
    "mr:1001-teresia-a-iesu-infante": {
        EDITION_IT: (
            "Translation error: \"all’età di venticinque anni\" (at the age of twenty-five) "
            "where the Latin has \"vicésimo quinto ætátis suæ anno\" (in her twenty-fifth year, "
            "i.e. aged twenty-four)."
        ),
    },
    "mr:1002-franciscus-carceller-et-isidorus-bover-oliver": {
        EDITION_EN: (
            "Translation error: \"Castalla\" where the Latin \"Castáliam\" means Castellón de la "
            "Plana."
        ),
    },
    "mr:1003-cyprianus": {
        EDITION_IT: (
            "Translation error: \"se non prima invocato dalla grazia preveniente\" where the "
            "Latin has \"nisi prímitus Dei grátia præveniénte vocátum\" (unless first called by "
            "God's prevenient grace)."
        ),
        EDITION_EN: (
            "Translation error: \"the province of France\" where the Latin \"Província Gálliæ\" "
            "means Provence."
        ),
    },
    "mr:1004-franciscus": {
        EDITION_EN: (
            "Translation error: \"naked\" is added; the Latin has only \"super nudam terram\" "
            "(on the bare ground)."
        ),
    },
    "mr:1005-marianus-skrzypczak": {
        EDITION_IT: (
            "Misprint: \"Skrzypezak\" where the Latin has \"Skrzypczak\"."
        ),
    },
    "mr:1006-artaldus": {
        EDITION_IT: (
            "Translation error: \"fino all’età di centosei anni\" (to the age of one hundred and "
            "six) where the Latin has \"usque ad centésimum sextum annum\" (to his "
            "hundred-and-sixth year)."
        ),
    },
    "mr:1006-bruno": {
        EDITION_IT: (
            "Translation error: \"valle di Chartroux\" where the Latin has \"valle Cartúsiæ in "
            "Alpibus\" (the valley of the Chartreuse in the Alps)."
        ),
    },
    "mr:1006-ioannes-xenus": {
        EDITION_IT: (
            "Misprint: \"Nazogírea\" where the Latin has \"Azogýreæ\" (Azogyrea)."
        ),
    },
    "mr:1006-magnus": {
        EDITION_EN: (
            "Translation error: \"in the Venetian region\" where the Latin \"Venétiis\" means at "
            "Venice."
        ),
    },
    "mr:1006-maria-rosa-durocher": {
        EDITION_IT: (
            "Misprint: \"Durochet\" where the Latin has \"Durocher\"."
        ),
    },
    "mr:1008-evodius": {
        EDITION_EN: (
            "Translation error: \"in the region of Lyon\" where the Latin has \"in Gállia "
            "Lugdunénsi\" (the province of Lugdunensis)."
        ),
    },
    "mr:1008-ragenfredis": {
        EDITION_EN: (
            "Translation error: \"monasteries\" where the Latin has \"cœnóbium\" (a monastery)."
        ),
    },
    "mr:1012-domnina": {
        EDITION_EN: (
            "Translation error: \"Lycianus\" where the Latin has \"Lýcia prǽside\" (the governor "
            "Lycias)."
        ),
    },
    "mr:1013-geraldus": {
        EDITION_IT: (
            "Translation error: \"con grande profitto per i suoi possedimenti\" (with great "
            "profit for his possessions) where the Latin has \"pro provinciárum suárum salúte\" "
            "(for the welfare of his provinces)."
        ),
    },
    "mr:1013-venantius": {
        EDITION_EN: (
            "Translation error: \"in the region of Lyon\" where the Latin has \"in Gállia "
            "Lugdunénsi\" (the province of Lugdunensis)."
        ),
    },
    "mr:1015-teresia-a-iesu": {
        EDITION_EN: (
            "Translation error: \"degrees of love\" where the Latin has \"per gradus ánimæ\" (of "
            "the soul by degrees)."
        ),
    },
    "mr:1016-gerardus-maiella": {
        EDITION_LA: (
            "Source error: \"Muri in Lucánia\" (Muro Lucano, his birthplace); he died at "
            "Materdomini near Caposele in Campania."
        ),
    },
    "mr:1019-gratus": {
        EDITION_IT: (
            "Translation error: \"Oléron\" (the Atlantic island) where the Latin has "
            "\"Illuróne\" (Oloron, at the foot of the Pyrenees)."
        ),
    },
    "mr:1019-philippus-howard": {
        EDITION_IT: (
            "Translation error: \"dagli stenti e dalle torture\" (by privations and tortures) "
            "where the Latin has \"egestáte ærumnísque\" (by want and hardships); no torture is "
            "mentioned."
        ),
    },
    "mr:1019-sabinianus-et-potentianus": {
        EDITION_EN: (
            "Translation error: \"the region around Lyon\" where the Latin has \"Gállia "
            "Lugdunénsi\" (the Roman province of Lugdunensis, not the area of Lyon)."
        ),
    },
    "mr:1020-adelina": {
        EDITION_EN: (
            "Translation error: \"Sévigny\" where the Latin has \"Saviníaci\" (Savigny)."
        ),
    },
    "mr:1020-sindulphus": {
        EDITION_EN: (
            "Translation error: \"Aulnay\" where the Latin has \"Alsóntiæ\" (Aussonce)."
        ),
    },
    "mr:1022-benedictus": {
        EDITION_IT: (
            "Translation error: \"a Mézières\" where the Latin has \"Maceráci\" (Massérac, near "
            "Nantes)."
        ),
    },
    "mr:1022-mallonus": {
        EDITION_EN: (
            "Translation error: \"the region around Lyon\" where the Latin has \"Gállia "
            "Lugdunénsi\" (the Roman province of Lugdunensis, not the area of Lyon)."
        ),
    },
    "mr:1022-marcus": {
        EDITION_EN: (
            "Translation error: \"is said to have gathered together again\" where the Latin has "
            "\"congregáre cœpit\" (began to gather), with no \"is said\"."
        ),
    },
    "mr:1023-allucius": {
        EDITION_EN: (
            "Translation error: \"Campoli\" where the Latin has \"Campuliáni\" (Campugliano)."
        ),
    },
    "mr:1023-ioannes-bonus": {
        EDITION_EN: (
            "Translation error: \"having lost his mother\" where the Latin has \"matre relícta\" "
            "(having left his mother)."
        ),
    },
    "mr:1024-aretha-et-socii": {
        EDITION_EN: (
            "Translation error: \"also called Dhu Nuwas\" where the Latin has \"seu Dun‘an\"."
        ),
    },
    "mr:1025-maria-teresia-ferragud-roig-et-socii": {
        EDITION_IT: (
            "Translation error: \"vergine dell’Ordine delle Clarisse Cappuccine ... vergini "
            "dell’Ordine delle Agostiniane Scalze\" where the Latin has \"vírginum ex Ordine "
            "Clarissárum Capuccinárum ... vírginis ex Ordine Augustinianárum Discalceatárum\" "
            "(three Capuchin Poor Clares, one Discalced Augustinian)."
        ),
    },
    "mr:1028-ferrutius": {
        EDITION_EN: (
            "Translation error: \"Belgic France\" where the Latin has \"Gállia Bélgica\" (the "
            "Roman province)."
        ),
    },
    "mr:1028-genesius": {
        EDITION_EN: (
            "Translation error: \"Tizac\" where the Latin has \"Tigérni\" (Thiers)."
        ),
    },
    "mr:1029-colmanus": {
        EDITION_EN: (
            "Translation error: \"Doagh\" where the Latin has \"Duácæ Gállicæ\" (Kilmacduagh, in "
            "Galway)."
        ),
    },
    "mr:1029-dodo": {
        EDITION_EN: (
            "Translation error: \"the monastery of Fanay\" where the Latin has \"Monastérii in "
            "Fánia\" (Moustier-en-Fagne)."
        ),
    },
    "mr:1101-nonius-alvarez-pereira": {
        EDITION_EN: (
            "Translation error: \"lay brothers\" where the Latin has \"fratres oblátos\" (oblate "
            "brothers)."
        ),
    },
    "mr:1102-marcianus": {
        EDITION_LA: (
            "Probable error: \"Chalcedonénsem\" (of Chalcedon) where the desert in which Marcian "
            "lived was that of Chalcis in Syria (\"Chalcidénsem\")."
        ),
        EDITION_IT: (
            "Translation error: \"si ritirò in monastero a Calcedonia\" where the Latin has \"in "
            "erémum Chalcedonénsem se cóntulit\" (he withdrew into the desert)."
        ),
    },
    "mr:1102-margarita-de-lotharingia": {
        EDITION_EN: (
            "Translation error: \"Mortain\" where the Latin has \"Moritániæ\" (Mortagne). "
            "Translation error: \"rebuilt\" where the Latin has \"ædificáverat\" (had built)."
        ),
    },
    "mr:1103-ermengaudius": {
        EDITION_EN: (
            "Translation error: \"rebuilĐing\" where the Latin has \"ædificándo\" (building)."
        ),
    },
    "mr:1103-simon-balacchi": {
        EDITION_EN: (
            "Translation error: \"chose a life\" where the Latin has \"vitam degit\" (led his "
            "life)."
        ),
    },
    "mr:1104-francisca-de-ambosia": {
        EDITION_IT: (
            "Translation error: \"un Carmelo femminile\" where the Latin has \"primum in Gállia "
            "carmélum mulíerum\" (the first Carmel of nuns in France)."
        ),
        EDITION_EN: (
            "Translation error: \"first founded at Vannes ... a convent of Carmelite nuns\" "
            "where the Latin has \"primum in Gállia carmélum mulíerum\" (the first Carmel of "
            "women in France)."
        ),
    },
    "mr:1104-modesta": {
        EDITION_EN: (
            "Translation error: \"presided worthily\" where the Latin has \"prima prǽfuit\" (was "
            "the first to preside)."
        ),
    },
    "mr:1105-dominicus-mau": {
        EDITION_IT: (
            "Translation error: \"con l'accusa di aver portato in pubblico la corona del "
            "Rosario\" where the Latin has \"Rosárii corónam públice ferens\" (openly wearing "
            "the rosary as he was led to execution, exhorting the Christians)."
        ),
    },
    "mr:1105-domninus": {
        EDITION_IT: (
            "Translation error: \"Mismiyā\" where the Latin has \"metálla Phænénsia\" (the mines "
            "of Phaeno, at Feinan south of the Dead Sea)."
        ),
    },
    "mr:1105-gregorius-lakota": {
        EDITION_EN: (
            "Translation error: \"Abé\" where the Latin has \"Abez\"."
        ),
    },
    "mr:1106-felix": {
        EDITION_IT: (
            "Translation error: \"La Calle ... nell'odierna Tunisia\" where the Latin has "
            "\"Thinísæ\" (Thinisa, Ras el-Djebel in Tunisia; La Calle is in Algeria)."
        ),
    },
    "mr:1107-athenodorus": {
        EDITION_EN: (
            "Translation error: \"divine eloquence\" where the Latin has \"divínis elóquiis\" "
            "(the divine Scriptures)."
        ),
    },
    "mr:1107-willibrordus": {
        EDITION_EN: (
            "Translation error: \"Saint Sergius, pope\" omits the ordinal of \"Sérgio papa "
            "Primo\" (Sergius I)."
        ),
    },
    "mr:1108-deusdedit-i": {
        EDITION_EN: (
            "Translation error: \"Saint Deusdedit, pope\" omits the ordinal of \"Deúsdedit papæ "
            "Primi\" (Deusdedit I)."
        ),
    },
    "mr:1108-simpronianus-et-socii": {
        EDITION_IT: (
            "Translation error: \"Srijem ... nell'odierna Croazia\" where the Latin has "
            "\"Sírmium\" (the city of Sremska Mitrovica, in present-day Serbia)."
        ),
    },
    "mr:1109-agrippinus": {
        EDITION_IT: (
            "Translation error: \"fu tra i primi che antichi documenti dichiarano difensore "
            "della città\" where the Latin has \"epíscopi inter primos\" (one of the first "
            "bishops of the city), whom ancient monuments call its defender."
        ),
    },
    "mr:1112-macarius": {
        EDITION_EN: (
            "Translation error: \"Lismore\" where the Latin has \"Máleo ínsula\" (the island of "
            "Mull)."
        ),
    },
    "mr:1113-arcadius-et-socii": {
        EDITION_EN: (
            "Translation error: \"Eutychius\" where the Latin has \"Eutychiáni\" (Eutychian)."
        ),
    },
    "mr:1113-himerius": {
        EDITION_EN: (
            "Translation error: \"valley of Susa\" where the Latin has \"Valle Susingénsi\" (the "
            "valley of the Suze)."
        ),
    },
    "mr:1113-livia-pietrantoni": {
        EDITION_EN: (
            "Translation error: \"Augustine\" where the Latin has \"Augustínæ\" (Augustina)."
        ),
    },
    "mr:1115-guria-et-samona": {
        EDITION_EN: (
            "Translation error: \"the Mysian governor\" where the Latin has \"a Mysiáno "
            "præfécto\" (by the prefect Mysianus)."
        ),
    },
    "mr:1115-viginti-martyres-hipponis-regii": {
        EDITION_EN: (
            "Translation error: \"Valerian\" where the Latin has \"Valeriánæ\" (Valeriana)."
        ),
    },
    "mr:1116-eduardus-osbaldeston": {
        EDITION_EN: (
            "Translation error: \"hanged, drawn, and quartered\" where the Latin has only "
            "\"suspéndii supplíciis\" (the punishment of hanging). Translation error: \"for his "
            "priestly office\" where the Latin has \"quod Angliam sacérdos petivísset\" (because "
            "he had come to England as a priest)."
        ),
    },
    "mr:1116-eucherius": {
        EDITION_IT: (
            "Translation error: \"nella vicina isola di Lérins\" (on the nearby island of "
            "Lérins) where the Latin has \"in ínsula próxima Lirinénsem\" (on the island next to "
            "Lérins, i.e. Lero)."
        ),
    },
    "mr:1116-leocadius-et-lusor": {
        EDITION_IT: (
            "Translation error: \"A Dol\" where the Latin \"Doli in território Bituricénsi\" is "
            "Déols, in the territory of Bourges."
        ),
    },
    "mr:1117-hugo-nucariae": {
        EDITION_EN: (
            "Translation error: \"Nocera\" where the Latin has \"Nucáriæ in Sicília\" (Novara di "
            "Sicilia)."
        ),
    },
    "mr:1117-iosaphat-kocylovskyj": {
        EDITION_EN: (
            "Translation error: \"Kapayivka\" where the Latin has \"Čapaivca\" (Chapaivka)."
        ),
    },
    "mr:1119-severinus-et-socii": {
        EDITION_IT: (
            "Translation error: \"Braine-sur-la-Vesle\" (a town near Soissons) where the Latin "
            "has \"Brennáco prope Viénnam\" (Brennacum near Vienne)."
        ),
    },
    "mr:1120-francisca-lloret-marti-et-socii": {
        EDITION_EN: (
            "Translation error: \"Doctrine of the Christian\" where the Latin has \"Doctrínæ "
            "Christiánæ\" (Christian Doctrine)."
        ),
    },
    "mr:1121-agapius": {
        EDITION_EN: (
            "Translation error: \"always deferring to greater contests\" where the Latin has "
            "\"semper ad maióra certámina dilátus\" (always reserved for greater contests)."
        ),
    },
    "mr:1121-gelasius-i": {
        EDITION_IT: (
            "Translation error: \"illustrò con vera profondità di analisi\" omits that he was "
            "the first to do so (Latin \"primus fúnditus illustrávit\")."
        ),
    },
    "mr:1122-petrus-esqueda-ramirez": {
        EDITION_EN: (
            "Translation error: \"Teocaltiche\" where the Latin has \"Teocaltitlán\"."
        ),
    },
    "mr:1123-trudo": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificávit\" (built)."
        ),
    },
    "mr:1125-beatrix-de-ornacieux": {
        EDITION_EN: (
            "Translation error: \"Valencia\" where the Latin has \"in pago Gálliæ Valentinénsi\" "
            "(the district of Valence in Gaul)."
        ),
    },
    "mr:1125-moyses": {
        EDITION_EN: (
            "Translation error: \"the lapsed, the weak, and those at the point of death\" where "
            "the Latin has \"lapsis infírmis et in éxitu constitútis\" (the lapsed who were sick "
            "and at the point of death)."
        ),
    },
    "mr:1125-petrus-yi-ho-yong": {
        EDITION_EN: (
            "Spelling error: \"Yi Ho-yang\" where the Latin has \"Yi Ho-yŏng\"."
        ),
    },
    "mr:1126-caietana-sterni": {
        EDITION_LA: (
            "Spelling error: \"Passáni\" for Bassano (Bassáni)."
        ),
    },
    "mr:1126-iacobus-alberione": {
        EDITION_EN: (
            "Translation error: \"the Priests of the Society\" where the Latin has \"Piæ "
            "Societátis\" (the Pious Society)."
        ),
    },
    "mr:1127-bronislaus-kostowski": {
        EDITION_LA: (
            "Spelling error: \"Kostowski\" for Kostkowski."
        ),
    },
    "mr:1127-gulstanus": {
        EDITION_EN: (
            "Translation error: \"then a hermit in the monastery of Rhuys\" where the Latin "
            "places Gulstan, not Felix, \"in monastério Rhuvigiénsi\"."
        ),
    },
    "mr:1128-papinianus-vitensis-et-mansuetus-urusitanus": {
        EDITION_EN: (
            "Translation error: \"Sufetula\" where the Latin has \"Sufetánus\" (of Sufes)."
        ),
    },
    "mr:1129-iacobus": {
        EDITION_EN: (
            "Translation error: \"verses\" where the Latin has \"versiónibus\" (translations)."
        ),
    },
    "mr:1129-petrus-berthelot-et-thomas-rodriguez": {
        EDITION_EN: (
            "Translation error: \"the sword\" where the Latin has \"secúri\" (the axe)."
        ),
    },
    "mr:1130-cuthbertus-mayne": {
        EDITION_EN: (
            "Translation error: \"St. Stephen-in-the-Fields\" where the Latin has \"Sancti "
            "Stéphani Fani\" (St Stephen's, by Launceston)."
        ),
    },
    "mr:1201-eligius": {
        EDITION_EN: (
            "Translation error: \"rebuilt many monasteries\" where the Latin has \"plúrima "
            "ædificavísset monastéria\" (built many monasteries)."
        ),
    },
    "mr:1201-florentia": {
        EDITION_EN: (
            "Translation error: the phrase \"a sancto Hilário ... convérsa\" (converted by Saint "
            "Hilary) is rendered as a time clause, losing that Hilary converted her."
        ),
    },
    "mr:1202-pimenius": {
        EDITION_EN: (
            "Translation error: \"Pimen\" where the Latin has \"Piménii\" (Pimenius)."
        ),
    },
    "mr:1203-birinus": {
        EDITION_EN: (
            "Translation error: \"who had not yet believed\" is added; the Latin has only "
            "\"Sáxonum occidentálium genti\" (the people of the West Saxons)."
        ),
    },
    "mr:1205-ioannes-almond": {
        EDITION_EN: (
            "Translation error: the sentence is broken after \"until under King James the "
            "First\"; the Latin reads that under King James the First he met the noose at Tyburn."
        ),
    },
    "mr:1208-macarius": {
        EDITION_IT: (
            "Translation error: \"per suo stesso ordine\" (by his own order) where the Latin has "
            "\"ad últimum ... iussus est\" (at last he was ordered, by the judge, to be burned "
            "alive)."
        ),
        EDITION_EN: (
            "Translation error: \"burned alive to the end\" where the Latin \"ad últimum exúri "
            "iussus est\" means he was at last ordered to be burned alive."
        ),
    },
    "mr:1208-patapius": {
        EDITION_EN: (
            "Translation error: \"an Egyptian monastery\" where the Latin has \"in Ægyptiórum "
            "monastério\" (the monastery of the Egyptians, at Constantinople)."
        ),
    },
    "mr:1209-ioannes-didacus-cuauhtlatoatzin": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificarétur\" (was built)."
        ),
    },
    "mr:1209-petrus-fourier": {
        EDITION_IT: (
            "Translation error: \"istituì i Canonici regolari del Nostro Salvatore\" (founded) "
            "where the Latin has \"renovávit\" (renewed, reformed)."
        ),
    },
    "mr:1211-damasus-i": {
        EDITION_EN: (
            "Translation error: \"uncovered the tombs\" where the Latin has \"sepúlcra ... pie "
            "excóluit\" (devoutly honoured the tombs)."
        ),
    },
    "mr:1211-francus-lippi": {
        EDITION_EN: (
            "Translation error: \"Francis\" where the Latin has \"Franci\" (Franco)."
        ),
    },
    "mr:1212-bartholus-buonpedoni": {
        EDITION_EN: (
            "Translation error: \"San Gimignano\" where the Latin has \"óppidum Celloli\" "
            "(Celloli)."
        ),
    },
    "mr:1212-epimachus-et-alexander": {
        EDITION_EN: (
            "Translation error: \"the holy virgins Ammonarion, Mercuria, Dionysia\" where the "
            "Latin calls only Ammonarion \"virgo\"."
        ),
    },
    "mr:1212-maria-de-guadalupe": {
        EDITION_EN: (
            "Translation error: the natives and the poor are joined to \"evangelizing of "
            "families\"; the Latin hails her as \"indigenárum pauperúmque præsídium\" (protector "
            "of the natives and the poor)."
        ),
    },
    "mr:1214-hero-et-socii": {
        EDITION_EN: (
            "Translation error: \"Ater\" where the Latin has \"Atéi\" (Ateus). Translation "
            "error: \"ordered to be dismissed\" where the Latin has \"différri præcépit\" "
            "(ordered to be held back)."
        ),
    },
    "mr:1215-maria-crucifixa-de-rosa": {
        EDITION_EN: (
            "Translation error: \"of Rosa\" where the Latin has the surname \"De Rosa\"."
        ),
    },
    "mr:1216-florentius-kazminsky": {
        EDITION_LA: (
            "Spelling error: \"Kazminsky\" for the surname Koźmiński."
        ),
    },
    "mr:1216-philippus-siphong-onphitak": {
        EDITION_EN: (
            "Translation error: \"was taken\" omits the Latin \"dolóse\" (by deceit)."
        ),
    },
    "mr:1219-maria-eva-de-providentia-et-maria-martha-de-iesu": {
        EDITION_LA: (
            "Spelling error: \"Wołowsk\" for the surname Wołowska."
        ),
    },
    "mr:1220-dominicus": {
        EDITION_EN: (
            "Translation error: \"monastery of Exilensis\" where the Latin \"monastério "
            "Exiliénsi\" means the monastery of Silos."
        ),
    },
    "mr:1221-michaeas-propheta": {
        EDITION_EN: (
            "Translation error: \"come forth from the days of eternity\" is applied to the "
            "chosen people, whereas it refers to the leader born in Bethlehem."
        ),
    },
    "mr:1221-themistocles": {
        EDITION_EN: (
            "Translation error: \"scourged\" where the Latin has \"raptátus\" (dragged)."
        ),
    },
    "mr:1225-anastasia": {
        EDITION_IT: (
            "Translation error: \"a Srijem ... nell’odierna Croazia\" where the Latin has "
            "\"Sírmii\" (Sirmium, today Sremska Mitrovica in Serbia)."
        ),
    },
    "mr:1227-alaphridus-parte": {
        EDITION_EN: (
            "Translation error: \"Liendo\" where the Latin \"Bléndii\" denotes Santander."
        ),
    },
    "mr:1227-iosephus-maria-corbin-ferrer": {
        EDITION_EN: (
            "Translation error: \"Liendo\" where the Latin \"Bléndium\" denotes Santander."
        ),
    },
    "mr:1227-theodorus": {
        EDITION_IT: (
            "Translation error: \"Hisarlik\" where the Latin has \"Apaméæ in Bithýnia\" (Apamea, "
            "today Mudanya)."
        ),
    },
    "mr:1229-benedicta-hyon-kyong-nyon-et-socii": {
        EDITION_EN: (
            "Translation error: \"Benedict\" where the Latin has \"Benedíctæ\" (Benedicta)."
        ),
    },
    "mr:1230-laurentius": {
        EDITION_EN: (
            "Translation error: \"Fragalà\" where the Latin has \"Fraxanónem\" (Frazzanò)."
        ),
    },
    "mr:1230-perpetuus": {
        EDITION_EN: (
            "Translation error: \"rebuilt\" where the Latin has \"ædificávit\" (built)."
        ),
    },
    "mr:1231-marius": {
        EDITION_EN: (
            "Translation error: \"rebuilt many churches\" where the Latin has \"ædificávit\" "
            "(built)."
        ),
    },
}
for _id, _notes in REVIEW_EDITION_NOTES.items():
    _others = EDITION_NOTES.setdefault(_id, {})
    for _ed, _note in _notes.items():
        _others[_ed] = " ".join(n for n in (_others.get(_ed), _note) if n)

# Where the Latin print and the CEI differ on an entry's asterisk, a note on each edition's page
# says what the other prints. Which edition is right (a correction of the Latin, or a legitimate
# departure from it) is left to the experts.
PLACEMENT_EDITION_NOTES = {}
for _id, _n in LATIN_ASTERISKED.items():
    PLACEMENT_EDITION_NOTES[_id] = {
        EDITION_LA: f"Asterisked here (entry {_n}*); the Italian (CEI) edition prints the entry "
                    "without an asterisk.",
        EDITION_IT: f"Printed here without an asterisk; the Latin editio altera prints the entry "
                    f"with one ({_n}*).",
    }
for _id, _n in LATIN_PLAIN.items():
    PLACEMENT_EDITION_NOTES[_id] = {
        EDITION_LA: f"Printed here without an asterisk (entry {_n}.); the Italian (CEI) edition marks "
                    "the entry with one.",
        EDITION_IT: f"Asterisked here; the Latin editio altera prints the entry without an asterisk "
                    f"({_n}.).",
    }
for _id, _notes in PLACEMENT_EDITION_NOTES.items():
    _others = EDITION_NOTES.get(_id, {})
    EDITION_NOTES[_id] = {ed: " ".join(n for n in (_notes.get(ed), _others.get(ed)) if n)
                          for ed in EDITIONS_2004 if _notes.get(ed) or _others.get(ed)}

# The Latin print's entry number where it differs from the CEI's (= the
# workbook's), verified on the print's text layer.
LATIN_RENUMBERING = {
    # January 4: Abrunculus (2*) is printed only in the Latin.
    "mr:0104-gregorius": 3,
    "mr:0104-ferreolus": 4,
    "mr:0104-rigomerus": 5,
    "mr:0104-rigobertus": 6,
    "mr:0104-pharaildis": 7,
    "mr:0104-angela": 8,
    "mr:0104-oringa-menabuoi": 9,
    "mr:0104-thomas-plumtree": 10,
    "mr:0104-elisabeth-anna-seton": 11,
    # June 10: Durando (9*) is printed only in the Latin.
    "mr:0610-eduardus-poppe": 10,
    # August 25: Eusebius and companions (CEI 3) is not in the Latin, which renumbers.
    "mr:0825-genesius": 3,
    "mr:0825-geruntius": 4,
    "mr:0825-severus": 5,
    "mr:0825-mena": 6,
    "mr:0825-aredius": 7,
    "mr:0825-gregorius": 8,
    "mr:0825-thomas-cantelupe": 9,
    "mr:0825-michael-carvalho-et-socii": 10,
    "mr:0825-paulus-ioannes-charles": 11,
    "mr:0825-maria-a-transitu-iesu-sacramenti": 12,
    "mr:0825-aloysius-urbano-lanaspa": 13,
    # December 10: Durando (CEI 9*) is not in the Latin, which renumbers.
    "mr:1210-gundisalvus-vines-masip": 9,
    "mr:1210-antonius-martin-hernandez-et-augustinus-garcia-calvo": 10,
}

# Eulogies printed only in the CEI edition (absent from the Latin print and
# from the English translation of it).
CEI_ONLY = {
    "mr:0712-proclus-et-hilarion",
    "mr:0825-eusebius-et-socii",
    "mr:0709-maria-a-iesu-crucifixo",
    "mr:1210-marcus-antonius-durando",
}

# One eulogy printed on different days by different editions: one ID per day,
# linked both ways as `same_eulogy`.
SAME_EULOGY = {
    "mr:0610-marcus-antonius-durando": "mr:1210-marcus-antonius-durando",
}


def edition_overrides(mr_id, *, entry, asterisk, cei_entry, cei_asterisk):
    """How the 2004-family editions differ from a eulogy's main (Latin print)
    placement: the CEI's own number and asterisk where they differ, and absence
    from the Latin and English for a CEI-only eulogy."""
    out = {}
    cei = {}
    if cei_entry != entry:
        cei["entry"] = cei_entry
    if cei_asterisk != asterisk:
        cei["asterisk"] = cei_asterisk
    if cei:
        out[EDITION_IT] = cei
    if mr_id in CEI_ONLY:
        out[EDITION_LA] = {"absent": True}
        out[EDITION_EN] = {"absent": True}
    return out


def link_same_eulogy(entries, pairs=SAME_EULOGY):
    """Record each pair in `same_eulogy` on both entries (idempotent)."""
    by_id = {e["id"]: e for e in entries}
    for a, b in pairs.items():
        for src, dst in ((a, b), (b, a)):
            if src in by_id:
                links = by_id[src].setdefault("same_eulogy", [])
                if dst not in links:
                    links.append(dst)


def link_deprecated_twins(entries, deprecated):
    """A deprecated eulogy printed by a historical edition on another day than
    its counterpart names that counterpart (current or deprecated) in its
    `same_eulogy` (data/deprecated_ids.json); record the link back on the
    counterpart (idempotent), keeping `same_eulogy` an entry's last key."""
    by_id = {e["id"]: e for e in entries + deprecated}
    for d in deprecated:
        for other in d.get("same_eulogy", []):
            t = by_id.get(other)
            if t is None:
                continue  # reported by validate_editions
            links = t.setdefault("same_eulogy", [])
            if d["id"] not in links:
                links.append(d["id"])
            t["same_eulogy"] = t.pop("same_eulogy")


def _placement(e, edition):
    """(entry, unnumbered) as `edition` prints `e`, or None if it does not."""
    o = e.get("editions", {}).get(edition, {})
    if o.get("absent"):
        return None
    return o.get("entry", e["entry"]), o.get("unnumbered", e.get("unnumbered", False))


def validate_editions(entries):
    """Errors in the per-edition data: unknown editions or keys, overrides that
    repeat the main value, one-sided `same_eulogy` links or same-day ones between
    two current IDs, and two numbered entries with the same number on one day of
    one edition."""
    errors = []
    by_id = {e["id"]: e for e in entries}
    for e in entries:
        for edition, n in e.get("edition_notes", {}).items():
            if edition not in EDITION_LABELS:
                errors.append(f"{e['id']}: edition_notes for unknown edition {edition}")
            elif not isinstance(n, str) or not n.strip():
                errors.append(f"{e['id']}: empty edition_notes for {edition}")
        for edition, o in e.get("editions", {}).items():
            if edition not in EDITIONS_2004:
                errors.append(f"{e['id']}: unknown edition {edition}")
            for k, v in o.items():
                if k not in OVERRIDE_KEYS:
                    errors.append(f"{e['id']}: unknown override key {k} for {edition}")
                elif k == "absent" and v is not True:
                    errors.append(f"{e['id']}: absent must be true for {edition}")
                elif k != "absent" and v == e.get(k, False if k == "unnumbered" else None):
                    errors.append(f"{e['id']}: {k} override repeats the main value for {edition}")
        for other in e.get("same_eulogy", []):
            t = by_id.get(other)
            if t is None:
                errors.append(f"{e['id']}: same_eulogy names unknown {other}")
                continue
            # Same day: allowed only from a deprecated ID, a historical eulogy whose
            # subject the 2004 edition changed (renamed celebration, reduced group,
            # corrected saint), keyed apart and matched (#51).
            if (t["month"], t["day"]) == (e["month"], e["day"]) and not (
                e.get("deprecated") or t.get("deprecated")
            ):
                errors.append(f"{e['id']}: same_eulogy {other} is on the same day")
            if e["id"] not in t.get("same_eulogy", []):
                errors.append(f"{e['id']}: same_eulogy {other} does not link back")
    for edition in EDITIONS_2004:
        seen = {}
        for e in entries:
            if e.get("deprecated"):
                continue
            placed = _placement(e, edition)
            if placed is None:
                continue
            entry, unnumbered = placed
            if entry is None or unnumbered:
                continue
            key = (e["month"], e["day"], entry)
            if key in seen:
                errors.append(f"{e['month']}/{e['day']} entry {entry} in {edition}: "
                              f"{seen[key]} and {e['id']}")
            else:
                seen[key] = e["id"]
    return errors

# The four leap-day elogia are printed twice (Feb 28 and Feb 29) and carry a
# single identity each, anchored at 0229. The Feb 29 placement is primary;
# the Feb 28 placement is recorded in `also_on`.
LEAP_DAY_PRIMARY = (2, 29)


def build_country_map(wb):
    iso = {}
    ws = wb["Paesi"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        code, _en, it = (list(row) + [None] * 3)[:3]
        if code and it:
            iso[it.strip()] = code.strip()
    return iso


def extract(workbook_path):
    import openpyxl  # only needed to read the private workbook

    wb = openpyxl.load_workbook(workbook_path, read_only=True)
    iso = build_country_map(wb)
    rows = []
    for month_index, sheet in enumerate(MONTH_SHEETS, 1):
        ws = wb[sheet]
        for row in ws.iter_rows(min_row=3, values_only=True):
            _mese, giorno, voce, asterisk, _it, _en, _la, paese, mr_id = (
                list(row) + [None] * 9
            )[:9]
            if mr_id is None:
                continue
            paese = str(paese).strip() if paese is not None else ""
            country = iso[paese] if paese else None
            mr_id = str(mr_id).strip()
            mr_id = ID_CORRECTIONS.get(mr_id, mr_id)
            country = COUNTRY_CORRECTIONS.get(mr_id, country)
            row_out = {
                "id": mr_id,
                "month": month_index,
                "day": int(str(giorno)),
                "entry": int(str(voce)),
                "asterisk": asterisk == "*",
                "country": country,
            }
            # The workbook records the CEI's number and asterisk; the main
            # placement follows the Latin print.
            cei_entry, cei_asterisk = row_out["entry"], row_out["asterisk"]
            if mr_id in ASTERISK_OVERRIDES:
                row_out["asterisk"] = ASTERISK_OVERRIDES[mr_id]
            if mr_id in PLACEMENT_OVERRIDES:
                p_month, p_day, p_entry, p_note = PLACEMENT_OVERRIDES[mr_id]
                row_out.update(month=p_month, day=p_day, entry=p_entry)
                row_out["note"] = (row_out.get("note", "") + " " + p_note).strip()
            if mr_id in LATIN_RENUMBERING:
                row_out["entry"] = LATIN_RENUMBERING[mr_id]
            if mr_id in ENTRY_NOTES:
                row_out["note"] = (row_out.get("note", "") + " " + ENTRY_NOTES[mr_id]).strip()
            overrides = edition_overrides(mr_id, entry=row_out["entry"], asterisk=row_out["asterisk"],
                                          cei_entry=cei_entry, cei_asterisk=cei_asterisk)
            if overrides:
                row_out["editions"] = overrides
            leads = UNNUMBERED_LEADS.get((row_out["month"], row_out["day"]), 0)
            if row_out["entry"] is not None and row_out["entry"] <= leads:
                row_out["unnumbered"] = True
            rows.append(row_out)

    # Merge duplicate IDs (the leap-day elogia): keep the Feb 29 placement as
    # primary and record the other placement in `also_on`.
    by_id = {}
    entries = []
    for row in rows:
        if row["id"] in by_id:
            first = by_id[row["id"]]
            primary, secondary = (
                (row, first)
                if (row["month"], row["day"]) == LEAP_DAY_PRIMARY
                else (first, row)
            )
            primary["also_on"] = [{
                "month": secondary["month"],
                "day": secondary["day"],
                "entry": secondary["entry"],
            }]
            if first is not primary:
                entries[entries.index(first)] = primary
            by_id[row["id"]] = primary
        else:
            by_id[row["id"]] = row
            entries.append(row)

    entries.extend(PRINT_ONLY_ENTRIES)
    entries = [dict(e) for e in entries]  # PRINT_ONLY_ENTRIES are module constants: copy
    for e in entries:
        if e["id"] in EDITION_NOTES:
            e["edition_notes"] = dict(EDITION_NOTES[e["id"]])
    link_same_eulogy(entries)
    for e in entries:  # `editions` and `same_eulogy` are the last keys of an entry
        for k in ("editions", "same_eulogy"):
            if k in e:
                e[k] = e.pop(k)
    errors = validate_editions(entries)
    assert not errors, "per-edition placements:\n" + "\n".join(errors)
    entries.sort(key=lambda e: (e["month"], e["day"], e["entry"] is None, e["entry"] or 0))
    return entries


def load_deprecated(repo_root, current_ids):
    """Deprecated canonical IDs coined for eulogies of historical editions
    with no counterpart in the anchor edition (data/deprecated_ids.json,
    generated by the martyrology-api alignment tooling). Their MMDD anchors
    the placement in the edition named by attested_in."""
    path = repo_root / "data" / "deprecated_ids.json"
    if not path.exists():
        return []
    deprecated = json.load(open(path, encoding="utf-8"))
    for e in deprecated:
        assert e.get("deprecated") is True and e["id"] not in current_ids, e["id"]
    return deprecated


def load_typology(repo_root, current_ids):
    """Typology of each current eulogy (data/typology.json, generated by
    extract_typology.py from the Latin texts). Missing file: no typology."""
    path = repo_root / "data" / "typology.json"
    if not path.exists():
        return {}
    typology = json.load(open(path, encoding="utf-8"))["typology"]
    assert set(typology) == set(current_ids), (
        "data/typology.json does not match the current IDs. " + RECOVERY)
    return typology


def add_typology(entries, typology):
    """Insert "typology" right after "country" (key order is output order)."""
    out = []
    for e in entries:
        if e["id"] not in typology:
            out.append(e)
            continue
        row = {}
        for k, v in e.items():
            if k == "typology":
                continue
            row[k] = v
            if k == "country":
                row["typology"] = typology[e["id"]]
        out.append(row)
    return out


def load_places(repo_root, current_ids):
    """Places stated by each current eulogy (data/places.json, generated by
    extract_places.py). Missing file: no places."""
    path = repo_root / "data" / "places.json"
    if not path.exists():
        return {}
    places = json.load(open(path, encoding="utf-8"))["places"]
    assert set(places) <= set(current_ids), (
        "data/places.json has IDs that are not current. " + RECOVERY)
    return places


def check_place_roles(places, typology):
    """The role of each opening place follows typology; catch a places.json
    generated from an older typology.json."""
    stale = [mrid for mrid, items in places.items() for it in items
             if it["source"] == "lead"
             and ROLE_OF_TYPOLOGY.get(typology.get(mrid)) != it["role"]]
    assert not stale, (
        f"data/places.json is out of date with data/typology.json ({len(stale)} opening "
        f"places, e.g. {stale[:3]}): rerun scripts/extract_places.py")


def add_places(entries, places):
    """Insert "places" after "typology" (or "country"); key order is output order."""
    out = []
    for e in entries:
        if e["id"] not in places:
            out.append({k: v for k, v in e.items() if k != "places"})
            continue
        anchor = "typology" if "typology" in e else "country"
        row = {}
        for k, v in e.items():
            if k == "places":
                continue
            row[k] = v
            if k == anchor:
                row["places"] = places[e["id"]]
        out.append(row)
    return out


def write_json(entries, deprecated, repo_root):
    out = {
        "$comment": "Canonical ID registry for the eulogies of the Roman Martyrology. "
                    "IDs are drafts pending committee review; see the README and "
                    "docs/canonicalization-report.md. Entries with deprecated:true "
                    "are attested only in historical editions (their MMDD anchors "
                    "the placement in the edition named by attested_in); the "
                    "deprecated status is itself a mechanical draft.",
        "anchor_edition": "martyrologium_romanum_editio_altera_2004",
        "id_scheme": "mr:MMDD-slug",
        "entry_count": len(entries) + len(deprecated),
        "current_count": len(entries),
        "deprecated_count": len(deprecated),
        "entries": entries + deprecated,
    }
    path = repo_root / "data" / "martyrology_ids.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def write_markdown(entries, repo_root):
    reg_dir = repo_root / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    for month_index, month_name in enumerate(MONTH_NAMES_EN, 1):
        month_entries = [e for e in entries if e["month"] == month_index]
        lines = [
            f"# {month_name}",
            "",
            f"{len(month_entries)} canonical IDs. "
            "`Entry` is the elogium's entry number within the day in the Latin "
            "editio altera 2004 print; an entry number in parentheses marks an unnumbered "
            "header elogium (a drop-cap paragraph for a celebration with liturgical "
            "rank, counted but not printed as a number); `*` marks asterisked entries; "
            "`Country` is the ISO 3166-1 alpha-2 code of the modern country of the "
            "place of the elogium; `Typology` is what the date of the elogium marks "
            "(see docs/canonicalization-report.md, Typology). "
            "`Editions` lists where another 2004-family edition differs from this row "
            "(the Latin print): its own entry number or asterisk, or `absent`; "
            "`same as` names the same eulogy printed on another day.",
            "",
            "| Day | Entry | ID | * | Country | Typology | Editions | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for e in month_entries:
            notes = []
            if e.get("also_on"):
                for a in e["also_on"]:
                    notes.append(f"also printed at {a['month']}/{a['day']} entry {a['entry']}")
            if e.get("note"):
                notes.append(e["note"])
            for edition, n in e.get("edition_notes", {}).items():
                notes.append(f"{EDITION_LABELS[edition]}: {n}")
            if e["entry"] is None:
                entry_cell = "—"
            elif e.get("unnumbered"):
                entry_cell = f"({e['entry']})"
            else:
                entry_cell = str(e["entry"])
            short = {EDITION_LA: "Latin", EDITION_IT: "CEI", EDITION_EN: "English"}
            diffs = []
            for edition, o in e.get("editions", {}).items():
                parts = ["absent" if k == "absent" else f"{k} {v}" for k, v in o.items()]
                diffs.append(f"{short[edition]}: {', '.join(parts)}")
            diffs += [f"same as `{x}`" for x in e.get("same_eulogy", [])]
            lines.append(
                f"| {e['day']} | {entry_cell} "
                f"| `{e['id']}` | {'*' if e['asterisk'] else ''} "
                f"| {e['country'] or ''} | {e.get('typology') or ''} "
                f"| {'; '.join(diffs)} | {' '.join(notes)} |"
            )
        path = reg_dir / f"{month_index:02d}-{month_name.lower()}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    workbook_path = sys.argv[1]
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    entries = extract(workbook_path)
    typology = load_typology(repo_root, {e["id"] for e in entries})
    places = load_places(repo_root, {e["id"] for e in entries})
    if typology:
        check_place_roles(places, typology)
    entries = add_typology(entries, typology)
    entries = add_places(entries, places)
    deprecated = load_deprecated(repo_root, {e["id"] for e in entries})
    link_deprecated_twins(entries, deprecated)
    errors = validate_editions(entries + deprecated)
    assert not errors, "same_eulogy links:\n" + "\n".join(errors)
    path = write_json(entries, deprecated, repo_root)
    write_markdown(entries, repo_root)
    ids = [e["id"] for e in entries] + [e["id"] for e in deprecated]
    assert len(ids) == len(set(ids)), "duplicate IDs after merge"
    print(f"Wrote {len(entries)} current + {len(deprecated)} deprecated entries "
          f"to {path} and registry/*.md")


if __name__ == "__main__":
    main()
