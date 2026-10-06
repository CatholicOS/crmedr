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
    "mr:1216-honoratus-de-bia-a-podlaska-kazminsky": "mr:1216-honoratus-kazminsky",
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
    "mr:0120-bernardus": "mr:0120-cyprianus-iwene-tansi",
    "mr:0127-vitalis": "mr:0127-manfredus-settala",
    "mr:0131-victor": "mr:0131-eusebius",
    "mr:0215-sepulcrus": "mr:0215-angelus-scarpetti",
    "mr:0216-petrus": "mr:0216-philippa-mareri",
    "mr:0220-trudo-fanus": "mr:0220-eucherius",
    "mr:0304-salvator-visconti": "mr:0304-placida-viel",
    "mr:0312-geminianus": "mr:0312-fina",
    "mr:0318-salvator-visconti": "mr:0318-martha-le-bouteiller",
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
    "mr:0226-pietatis-a-cruce-ortiz-real": "mr:0226-pietas-a-cruce",
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
    "mr:0710-maria-gertrudis-a-sancta-sophia-de-ripert": "mr:0710-maria-gertrudis-a-sancta-sophia-et-agnes-a-iesu",
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
    "mr:1129-dionysius-a-nativitate-berthelot": "mr:1129-dionysius-a-nativitate-et-redemptus-a-cruce",
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
    "mr:0725-fridericus-rubio-alvarez": "mr:0725-fridericus-rubio-alvarez-et-socii",
    "mr:0725-petrus-a-corde-redondo": "mr:0725-petrus-a-corde-et-socii",
    "mr:0727-georgius": "mr:0727-georgius-et-socii",
    "mr:0729-ludovicus-bertran": "mr:0729-ludovicus-bertran-et-socii",
    "mr:0730-iosephus-maria-muro-sanmiguel": "mr:0730-iosephus-maria-muro-sanmiguel-et-socii",
    "mr:0801-maria-stella-a-sanctissimo-sacramento-mardosewicz": "mr:0801-maria-stella-a-sanctissimo-sacramento-et-socii",
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
    "mr:0916-laureanus-ferrer-cardet": "mr:0916-laureanus-ferrer-cardet-et-socii",
    "mr:0921-laurentius-imbert": "mr:0921-laurentius-imbert-et-socii",
    "mr:0923-sophia-ximenez-ximenez": "mr:0923-sophia-ximenez-ximenez-et-socii",
    "mr:0925-ioannes-petrus-bengoa-aranguren": "mr:0925-ioannes-petrus-bengoa-aranguren-et-socii",
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
    "mr:0921-matthaeus": "mr:0921-matthaeus-apostolus",
    "mr:1028-simon-et-iudas": "mr:1028-simon-et-iudas-apostoli",
    "mr:1118-dedicatio-basilicarum-petri-et-pauli": "mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum",
    "mr:1130-andreas": "mr:1130-andreas-apostolus",
    "mr:1227-ioannes": "mr:1227-ioannes-apostolus",

    # #59: the evangelists Mark and Luke keep -evangelista.
    "mr:0425-marcus": "mr:0425-marcus-evangelista",
    "mr:1018-lucas": "mr:1018-lucas-evangelista",

    # #59: papal ordinals are roman numerals (rule 3).
    "mr:0116-marcellus-primus": "mr:0116-marcellus-i",
    # a same-day namesake takes his see, not a number (rule 9)
    "mr:0408-dionysius-2": "mr:0408-dionysius-corinthi",

    # #63: one conventional name form per saint (religious name OR name + surname).
    "mr:0105-carolus-a-sancto-andrea-houben": "mr:0105-carolus-a-sancto-andrea",
    "mr:0106-raphaela-maria-a-sacro-corde-porras-ayllon": "mr:0106-raphaela-maria-a-sacro-corde",
    "mr:0109-maria-teresia-a-iesu-le-clerc": "mr:0109-maria-teresia-a-iesu",
    "mr:0110-anna-ab-angelis-monteagudo": "mr:0110-anna-ab-angelis",
    "mr:0111-thomas-de-cora-placidi": "mr:0111-thomas-de-cora",
    "mr:0113-veronica-de-binasco-negroni": "mr:0113-veronica-de-binasco",
    "mr:0114-odoricus-de-portu-naonis-mattiuzzi": "mr:0114-odoricus-de-portu-naonis",
    "mr:0118-andreas-de-piscaria-grego": "mr:0118-andreas-de-piscaria",
    "mr:0120-maria-christina-ab-immaculata-brando": "mr:0120-maria-christina-ab-immaculata",
    "mr:0201-ioanna-francisca-a-visitatione-michelotti": "mr:0201-ioanna-francisca-a-visitatione",
    "mr:0202-simon-de-cassia-fidati": "mr:0202-simon-de-cassia",
    "mr:0203-maria-a-sancto-ignatio-thevenet": "mr:0203-maria-a-sancto-ignatio",
    "mr:0207-aegidius-maria-a-sancto-ioseph-pontillo": "mr:0207-aegidius-maria-a-sancto-ioseph",
    "mr:0207-ioannes-de-triora-lantrua": "mr:0207-ioannes-de-triora",
    "mr:0207-maria-a-providentia-smet": "mr:0207-maria-a-providentia",
    "mr:0214-ioannes-baptista-a-conceptione-garcia": "mr:0214-ioannes-baptista-a-conceptione",
    "mr:0219-conradus-de-placentia-confalonieri": "mr:0219-conradus-confalonieri",
    "mr:0224-constantius-de-fabriano-servoli": "mr:0224-constantius-de-fabriano",
    "mr:0226-paula-a-sancto-iosepho-de-calasanz-montal-fornes": "mr:0226-paula-a-sancto-iosepho-de-calasanz",
    "mr:0227-francisca-anna-a-virgine-perdolenti-cirer-carbonell": "mr:0227-francisca-anna-a-virgine-perdolenti",
    "mr:0227-gabriel-a-virgine-perdolenti-possenti": "mr:0227-gabriel-a-virgine-perdolenti",
    "mr:0227-maria-a-iesu-deluil-martiny": "mr:0227-maria-a-iesu",
    "mr:0227-maria-a-caritate-spiritus-sancti-brader": "mr:0227-maria-a-caritate-spiritus-sancti",
    "mr:0302-angela-a-cruce-guerrero-gonzalez": "mr:0302-angela-a-cruce",
    "mr:0303-innocentius-de-berzo-scalvinoni": "mr:0303-innocentius-de-berzo",
    "mr:0305-ieremias-de-valachia-kostistik": "mr:0305-ieremias-de-valachia",
    "mr:0305-ioannes-iosephus-a-cruce-calosirto": "mr:0305-ioannes-iosephus-a-cruce",
    "mr:0310-elias-a-succursu-nieves-del-castillo": "mr:0310-elias-a-succursu",
    "mr:0311-ioannes-baptista-de-fabriano-righi": "mr:0311-ioannes-baptista-de-fabriano",
    "mr:0318-salvator-de-horta-grionesos": "mr:0318-salvator-de-horta",
    "mr:0319-ioannes-de-parma-buralli": "mr:0319-ioannes-de-parma",
    "mr:0319-marcus-de-marchio-de-montegallo": "mr:0319-marcus-de-montegallo",
    "mr:0320-franciscus-a-iesu-maria-ioseph-palau-y-quer": "mr:0320-franciscus-a-iesu-maria-ioseph",
    "mr:0320-maria-iosepha-a-corde-iesu-sancho-de-guerra": "mr:0320-maria-iosepha-a-corde-iesu",
    "mr:0324-didacus-iosephus-de-gadibus-lopez-caamano": "mr:0324-didacus-iosephus-de-gadibus",
    "mr:0330-petrus-de-vallisoleto-regalado": "mr:0330-petrus-regalado",
    "mr:0330-ludovicus-de-casaurea-palmentieri": "mr:0330-ludovicus-de-casaurea",
    "mr:0402-maria-a-sancto-ioseph-alvarado": "mr:0402-maria-a-sancto-ioseph",
    "mr:0403-gandulfus-de-binasco-sacchi": "mr:0403-gandulfus-de-binasco",
    "mr:0408-dominicus-a-sanctissimo-sacramento-iturrate": "mr:0408-dominicus-a-sanctissimo-sacramento",
    "mr:0410-marcus-de-bononia-fantuzzi": "mr:0410-marcus-de-bononia",
    "mr:0411-angelus-de-clavasio-carletti": "mr:0411-angelus-de-clavasio",
    "mr:0412-teresia-a-iesu-fernandez-solar": "mr:0412-teresia-a-iesu",
    "mr:0417-maria-anna-a-iesu-navarro-de-guevara": "mr:0417-maria-anna-a-iesu",
    "mr:0418-maria-ab-incarnatione-avrillot": "mr:0418-maria-ab-incarnatione",
    "mr:0420-simon-de-tuderto-rinalducci": "mr:0420-simon-de-tuderto",
    "mr:0421-conradus-de-parzham-birndorfer": "mr:0421-conradus-de-parzham",
    "mr:0423-teresia-maria-a-cruce-manetti": "mr:0423-teresia-maria-a-cruce",
    "mr:0424-maria-a-sancta-euphrasia-pelletier": "mr:0424-maria-a-sancta-euphrasia",
    "mr:0427-iacobus-de-iadere-varinguer": "mr:0427-iacobus-de-iadere",
    "mr:0430-maria-ab-incarnatione-guyart-martin": "mr:0430-maria-ab-incarnatione",
    "mr:0508-maria-catharina-a-sancto-augustino-symon-de-longprey": "mr:0508-maria-catharina-a-sancto-augustino",
    "mr:0509-maria-teresia-a-iesu-gerhardinger": "mr:0509-maria-teresia-a-iesu",
    "mr:0519-ioannes-a-sancto-dominico-martinez": "mr:0519-ioannes-a-sancto-dominico",
    "mr:0531-marianus-de-roccacasale-di-nicolantonio": "mr:0531-marianus-de-roccacasale",
    "mr:0606-laurentius-de-villamagna-de-masculis": "mr:0606-laurentius-de-villamagna",
    "mr:0608-maria-a-divino-corde-iesu-droste": "mr:0608-maria-a-divino-corde-iesu",
    "mr:0608-nicolaus-de-gesturi-medda": "mr:0608-nicolaus-de-gesturi",
    "mr:0611-ioannes-a-sancto-facundo-gonzalez-de-castrillo": "mr:0611-ioannes-a-sancto-facundo",
    "mr:0611-rosa-francisca-maria-a-doloribus-molas-vallve": "mr:0611-rosa-francisca-maria-a-doloribus",
    "mr:0612-laurentius-maria-a-sancto-francisco-xaverio-salvi": "mr:0612-laurentius-maria-a-sancto-francisco-xaverio",
    "mr:0612-mercedis-maria-a-iesu-molina": "mr:0612-mercedis-maria-a-iesu",
    "mr:0612-maria-candida-ab-eucharistia-barba": "mr:0612-maria-candida-ab-eucharistia",
    "mr:0706-nazaria-a-sancta-teresia-march-mesa": "mr:0706-nazaria-a-sancta-teresia",
    "mr:0707-iphigenia-a-sancto-matthaeo-de-gaillard-de-la-valdene": "mr:0707-iphigenia-a-sancto-matthaeo",
    "mr:0709-paulina-a-corde-iesu-agonizante-visintainer": "mr:0709-paulina-a-corde-iesu-agonizante",
    "mr:0709-maria-a-iesu-crucifixo-petkovic": "mr:0709-maria-a-iesu-crucifixo",
    "mr:0711-rosalia-clotildis-a-sancta-pelagia-bes-et-socii": "mr:0711-rosalia-clotildis-a-sancta-pelagia-et-socii",
    "mr:0712-rosa-a-sancto-xaverio-tallien-et-socii": "mr:0712-rosa-a-sancto-xaverio-et-socii",
    "mr:0713-magdalena-a-matre-dei-verchiere-et-socii": "mr:0713-magdalena-a-matre-dei-et-socii",
    "mr:0716-amata-a-iesu-de-gordon-et-socii": "mr:0716-amata-a-iesu-et-socii",
    "mr:0717-teresia-a-sancto-augustino-lidoine-et-socii": "mr:0717-teresia-a-sancto-augustino-et-socii",
    "mr:0720-rita-a-virgine-perdolenti-a-corde-iesu-pujalte-y-sanchez-et-francisca-a-corde-iesu-aldea-y-araujo": "mr:0720-rita-a-virgine-perdolenti-a-corde-iesu-et-francisca-a-corde-iesu",
    "mr:0722-augustinus-de-bugella-fangi": "mr:0722-augustinus-de-bugella",
    "mr:0724-ioannes-de-tossiniano-tavelli": "mr:0724-ioannes-de-tossiniano",
    "mr:0724-modestinus-a-iesu-et-maria-mazzarello": "mr:0724-modestinus-a-iesu-et-maria",
    "mr:0724-maria-a-columna-a-sancto-francisco-borgia-martinez-garcia-et-socii": "mr:0724-maria-a-columna-a-sancto-francisco-borgia-et-socii",
    "mr:0725-petrus-de-molliano-corradini": "mr:0725-petrus-de-molliano",
    "mr:0726-maria-margarita-a-sancto-augustino-bonnet-et-socii": "mr:0726-maria-margarita-a-sancto-augustino-et-socii",
    "mr:0727-maria-clemens-a-iesu-crucifixo-staszewska": "mr:0727-maria-clemens-a-iesu-crucifixo",
    "mr:0728-alphonsa-ab-immaculata-conceptione-muttathupadathu": "mr:0728-alphonsa-ab-immaculata-conceptione",
    "mr:0730-leopoldus-de-castronovo-mandic": "mr:0730-leopoldus-mandic",
    "mr:0730-maria-vincentia-a-sancta-dorothea-chavez-orozco": "mr:0730-maria-vincentia-a-sancta-dorothea",
    "mr:0730-maria-a-iesu-sacramentato-venegas-de-la-torre": "mr:0730-maria-a-iesu-sacramentato",
    "mr:0806-maria-francisca-a-iesu-rubatto": "mr:0806-maria-francisca-a-iesu",
    "mr:0807-agathangelus-de-vindocino-nourry-et-cassianus-de-nannetibus-vaz-lopez-netto": "mr:0807-agathangelus-de-vindocino-et-cassianus-de-nannetibus",
    "mr:0808-maria-a-cruce-mackillop": "mr:0808-maria-a-cruce",
    "mr:0808-maria-a-iesu-infante-baldillou-y-bullit-et-socii": "mr:0808-maria-a-iesu-infante-et-socii",
    "mr:0809-teresia-benedicta-a-cruce-stein": "mr:0809-teresia-benedicta-a-cruce",
    "mr:0809-candida-maria-a-iesu-cipitria": "mr:0809-candida-maria-a-iesu",
    "mr:0810-archangelus-de-calataphino-piacentini": "mr:0810-archangelus-de-calataphino",
    "mr:0813-marcus-de-aviano-cristofori": "mr:0813-marcus-de-aviano",
    "mr:0814-sanctus-de-urbino-brancorsini": "mr:0814-sanctus-de-urbino",
    "mr:0815-maria-a-sacrario-a-sancto-aloysio-gonzaga-moragas-cantarero": "mr:0815-maria-a-sacrario-a-sancto-aloysio-gonzaga",
    "mr:0816-petra-a-sancto-ioseph-perez-florido": "mr:0816-petra-a-sancto-ioseph",
    "mr:0819-elvira-a-nativitate-dominae-nostrae-torrentalle-paraire-et-socii": "mr:0819-elvira-a-nativitate-dominae-nostrae-et-socii",
    "mr:0823-ioannes-maria-a-cruce-garcia-mendez": "mr:0823-ioannes-maria-a-cruce",
    "mr:0824-maria-michaela-a-sanctissimo-sacramento-desmaisieres": "mr:0824-maria-michaela-a-sanctissimo-sacramento",
    "mr:0824-maria-ab-incarnatione-rosal": "mr:0824-maria-ab-incarnatione",
    "mr:0826-maria-a-iesu-crucifixo-baouardy": "mr:0826-maria-a-iesu-crucifixo",
    "mr:0826-teresia-a-iesu-jornet-ibars": "mr:0826-teresia-jornet-ibars",
    "mr:0827-dominicus-a-matre-dei-barberi": "mr:0827-dominicus-barberi",
    "mr:0829-maria-a-cruce-jugan": "mr:0829-ioanna-jugan",
    "mr:0903-birgitta-a-iesu-morello": "mr:0903-birgitta-a-iesu",
    "mr:0907-ascensio-a-sancto-iosepho-calasanz-lloret-marco": "mr:0907-ascensio-a-sancto-iosepho-calasanz",
    "mr:0908-iosepha-a-sancto-ioanne-a-deo-ruano-garcia-et-maria-a-doloribus-a-sancta-eulalia-puig-bonany": "mr:0908-iosepha-a-sancto-ioanne-a-deo-et-maria-a-doloribus-a-sancta-eulalia",
    "mr:0911-bonaventura-de-barcinone-gran": "mr:0911-bonaventura-de-barcinone",
    "mr:0911-petrus-de-alcantara-villanueva-larrayoz": "mr:0911-petrus-de-alcantara",
    "mr:0913-maria-a-iesu-lopez-de-rivas": "mr:0913-maria-a-iesu",
    "mr:0919-maria-a-iesu-de-la-yglesia-y-de-varo-et-socii": "mr:0919-maria-a-iesu-et-socii",
    "mr:0921-marcus-de-mutina-scalabrini": "mr:0921-marcus-de-mutina",
    "mr:0922-ignatius-de-sandone-belvisotti": "mr:0922-ignatius-de-sandone",
    "mr:0923-pius-de-pietrelcina-forgione": "mr:0923-pius-de-pietrelcina",
    "mr:0926-maria-a-refugio-rosat-balasch-et-maria-a-calvario-romero-clariana": "mr:0926-maria-a-refugio-et-maria-a-calvario",
    "mr:0928-laurentius-de-manila-ruiz-et-socii": "mr:0928-laurentius-ruiz-et-socii",
    "mr:0928-bernardinus-de-feltria-tomitano": "mr:0928-bernardinus-de-feltria",
    "mr:1006-isidorus-a-sancto-ioseph-de-loor": "mr:1006-isidorus-a-sancto-ioseph",
    "mr:1009-innocentius-ab-immaculata-canoura-arnau-et-socii": "mr:1009-innocentius-ab-immaculata-et-socii",
    "mr:1011-iacobus-de-ulma-griesinger": "mr:1011-iacobus-de-ulma",
    "mr:1012-seraphinus-de-monte-granario-de-nicola": "mr:1012-seraphinus-de-monte-granario",
    "mr:1017-maria-natalia-a-sancto-ludovico-vanot-et-socii": "mr:1017-maria-natalia-a-sancto-ludovico-et-socii",
    "mr:1019-agnes-a-iesu-galand": "mr:1019-agnes-a-iesu",
    "mr:1021-laura-a-sancta-catharina-senensi-montoya-y-upegui": "mr:1021-laura-montoya-y-upegui",
    "mr:1023-maria-clotildis-angela-a-sancto-francisco-borgia-paillot-et-socii": "mr:1023-maria-clotildis-angela-a-sancto-francisco-borgia-et-socii",
    "mr:1031-thomas-de-florentia-bellaci": "mr:1031-thomas-de-florentia",
    "mr:1102-pius-a-sancto-aloysio-campidelli": "mr:1102-pius-a-sancto-aloysio",
    "mr:1109-elisabeth-a-sanctissima-trinitate-catez": "mr:1109-elisabeth-a-sanctissima-trinitate",
    "mr:1113-maria-a-patrocinio-a-sancto-ioanne-giner-gomis": "mr:1113-maria-a-patrocinio-a-sancto-ioanne",
    "mr:1115-maria-a-passione-de-chappotin-de-neuville": "mr:1115-maria-a-passione",
    "mr:1115-raphael-a-sancto-ioseph-kalinowski": "mr:1115-raphael-kalinowski",
    "mr:1118-grimoaldus-a-purificatione-santamaria": "mr:1118-grimoaldus-a-purificatione",
    "mr:1118-maria-a-refugio-hinojosa-y-naveros-et-socii": "mr:1118-maria-a-refugio-et-socii",
    "mr:1120-angela-a-sancto-ioseph-lloret-marti-et-socii": "mr:1120-angela-a-sancto-ioseph-et-socii",
    "mr:1121-maria-a-iesu-bono-pastore-de-siedliska": "mr:1121-maria-a-iesu-bono-pastore",
    "mr:1124-nicetha-a-sancta-prudentia-plaja-xifra-et-socii": "mr:1124-nicetha-a-sancta-prudentia-et-socii",
    "mr:1127-bernardinus-de-fossa-amici": "mr:1127-bernardinus-de-fossa",
    "mr:1130-ioannes-de-vercellis-garbella": "mr:1130-ioannes-de-vercellis",
    "mr:1209-bernardus-maria-a-iesu-silvestrelli": "mr:1209-bernardus-maria-a-iesu",
    "mr:1211-mirabilia-a-iesu-pidal-y-chico-de-guzman": "mr:1211-mirabilia-a-iesu",
    "mr:1216-maria-ab-angelis-fontanella": "mr:1216-maria-ab-angelis",
    "mr:1217-mathildis-a-sacro-corde-tellez-robles": "mr:1217-mathildis-a-sacro-corde",
    "mr:1223-antonius-a-sancta-anna-galvao-de-franca": "mr:1223-antonius-galvao-de-franca",
    "mr:1225-maria-ab-apostolis-von-wullenweber": "mr:1225-maria-ab-apostolis",
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
    "mr:0718-tarsicia-mackiv": 13,
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
    "mr:0724-maria-a-columna-a-sancto-francisco-borgia-et-socii": "ES",  # Guadalajara, Spain
    "mr:0830-ioachim-ferrer-adell": "ES",  # Castellón de la Plana
    "mr:1125-hyacinthus-serrano-lopez": "ES",  # Puebla de Híjar near Teruel
    "mr:0825-maria-a-transitu-iesu-sacramenti": "AR",  # Córdoba, Argentina
    "mr:0320-nicetas": "AL",  # Pojani (Apollonia)
    "mr:0731-ignatius-de-loyola": "IT",  # no place-lead; died in Rome
    "mr:0226-paula-a-sancto-iosepho-de-calasanz": "ES",  # Olesa de Montserrat
    "mr:0918-ambrosius-chulia-ferrandis-et-valentinus-jaunzaras-gomez": "ES",  # Montserrat, Catalonia
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

ASTERISK_OVERRIDES = {}
for _id, _n in LATIN_ASTERISKED.items():
    ASTERISK_OVERRIDES[_id] = (
        True,
        f"Asterisked entry ({_n}*) in the Latin editio altera 2004 print; "
        "the Italian (CEI) edition carries no asterisk.",
    )
for _id, _n in LATIN_PLAIN.items():
    ASTERISK_OVERRIDES[_id] = (
        False,
        f"Plain entry ({_n}., no asterisk) in the Latin editio altera 2004 "
        "print; the Italian (CEI) edition "
        "marks the entry with an asterisk.",
    )

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
        "note": "Entry 2* in the Latin editio altera 2004 print; absent from "
                "the Italian (CEI) edition.",
        "editions": {"martyrologium_romanum_2004_it_IT": {"absent": True}},
    },
    {
        "id": "mr:0104-emmanuel-gonzalez-garcia",
        "month": 1,
        "day": 4,
        "entry": 12,
        "asterisk": True,
        "country": "ES",
        "note": "Numbered 12* in the Latin editio altera 2004 print, 11* in "
                "the Italian (CEI) edition. Manuel González García, blessed in "
                "the 2004 editions, was canonized in 2016.",
        "editions": {"martyrologium_romanum_2004_it_IT": {"entry": 11}},
    },
    {
        "id": "mr:0610-marcus-antonius-durando",
        "month": 6,
        "day": 10,
        "entry": 9,
        "asterisk": True,
        "country": "IT",
        "note": "Entry 9* at June 10 in the Latin editio altera 2004 print; "
                "the Italian (CEI) edition prints "
                "the same eulogy at December 10, entry 9* "
                "(mr:1210-marcus-antonius-durando).",
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
EDITION_1749 = "martyrologium_romanum_1749"
EDITION_1914 = "martyrologium_romanum_1914_en_unofficial"
EDITION_LABELS = {
    EDITION_LA: "2004 Latin", EDITION_IT: "2004 Italian", EDITION_EN: "2004 English",
    EDITION_1749: "1749 Latin", EDITION_1914: "1914 English",
}

# A curator's note that concerns one edition's text only (a mistranslation, a
# misprint, a dropped line): `edition_notes` on the entry, shown with that
# edition alone; `note` (ENTRY_NOTES) is for remarks about the eulogy itself.
# Deprecated IDs carry theirs in data/deprecated_ids.json.
EDITION_NOTES = {
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
    "mr:0221-petrus-damianus": {
        EDITION_IT: (
            "Translation omission: the sentence \"Ipsíus autem tránsitus Favéntiæ in Flamínia "
            "crástina die evénit\" (his death took place at Faenza on the following day) is not "
            "rendered."
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
    "mr:0302-angela-a-cruce": {
        EDITION_IT: (
            "Translation omission: the title \"vergine\" (Latin \"vírginis\") is missing after the "
            "name."
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
    "mr:0516-simon-stock": {
        EDITION_IT: (
            "Translation error: \"beato Simone Stock\" where the Latin has \"sancti Simónis Stock\" "
            "(Saint)."
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
    "mr:0717-teresia-a-sancto-augustino-et-socii": {
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
    "mr:0827-guarinus": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" where the Latin has \"Sabaudiae\" (in Savoy)."
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
    "mr:0920-iosephus-maria-de-yermo-y-parres": {
        EDITION_IT: (
            "Translation error: \"beato\" where the Latin has \"sancti\" (Saint); he was canonized in "
            "2000."
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
    "mr:1108-godefridus": {
        EDITION_IT: (
            "Translation error: \"per un quinquennio\" (for five years) where the Latin has \"a "
            "quinquénnio\" (from the age of five)."
        ),
    },
    "mr:1114-siardus": {
        EDITION_IT: (
            "Translation error: \"Malgarten\" where the Latin has \"Horto Sanctæ Maríæ\" "
            "(Mariëngaarde, in Friesland)."
        ),
    },
    "mr:1126-pontius-falciniacensis": {
        EDITION_IT: (
            "Translation error: \"in Borgogna\" (in Burgundy) where the Latin has \"in Sabáudia\" (in "
            "Savoy)."
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
}

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
    "mr:0104-christiana-menabuoi": 9,
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
                row_out["asterisk"], row_out["note"] = ASTERISK_OVERRIDES[mr_id]
            if mr_id in PLACEMENT_OVERRIDES:
                p_month, p_day, p_entry, p_note = PLACEMENT_OVERRIDES[mr_id]
                row_out.update(month=p_month, day=p_day, entry=p_entry)
                row_out["note"] = (row_out.get("note", "") + " " + p_note).strip()
            if mr_id in LATIN_RENUMBERING:
                row_out["entry"] = LATIN_RENUMBERING[mr_id]
            if mr_id in ENTRY_NOTES:
                row_out["note"] = (row_out.get("note", "") + " " + ENTRY_NOTES[mr_id]).strip()
            if mr_id in EDITION_NOTES:
                row_out["edition_notes"] = dict(EDITION_NOTES[mr_id])
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
