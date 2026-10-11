# 📐 Print-Ready-Maker

Maakt van een gewone flyer of poster een **drukklaar PDF-bestand**: met afloopruimte (bleed), omgezet naar CMYK en, als de drukker dat eist, als PDF/X-1a. Kies je drukker uit de lijst en de juiste technische instellingen worden automatisch gezet.

https://github.com/user-attachments/assets/86275635-c462-45fe-b7ac-aa204de273fd

## Waarom deze tool?

Online drukkerijen keuren bestanden regelmatig af. De drie meest voorkomende redenen:

1. **Geen afloopruimte (bleed).** Een drukker snijdt altijd iets van de rand af. Loopt je achtergrond niet een paar millimeter door, dan krijg je een witte rand.
2. **RGB in plaats van CMYK.** Ontwerpen uit Canva, Word of een telefoon zijn in RGB (schermkleuren). Een drukpers werkt met CMYK-inkt; zonder omzetting kunnen kleuren flets of anders uitvallen.
3. **Verkeerd PDF-type.** Sommige drukkers eisen een specifieke PDF-versie of PDF/X-1a, bijvoorbeeld Bizay voor gevouwen folders.

Print-Ready-Maker lost alle drie in één keer op, zonder dat je hoeft te weten wat Fogra39 of een TrimBox is.

## Wat het doet

- **Afloopruimte toevoegen** (standaard 3 mm, instelbaar tot 20 mm), op vier manieren:
  - *Spiegelen*: de rand van je ontwerp wordt gespiegeld, ziet er meestal het natuurlijkst uit
  - *Randpixels uitrekken*: de buitenste pixels lopen door
  - *Eigen kleur*: kies een kleur, of klik een pixel in je ontwerp aan om die kleur over te nemen
  - *Dominante achtergrondkleur*: de tool kiest zelf de meest voorkomende randkleur
- **Vloeiende overgang** tussen ontwerp en afloop (randvervaging), zonder haarlijnen
- **Formaat aanpassen**: van A5 tot A0, staand of liggend, met een waarschuwing als de verhouding van je bestand niet klopt met het gekozen formaat
- **CMYK-omzetting** afgestemd op de drukstandaard (inktlimiet en zwartopbouw), voor 12 profielen: Fogra 29/39/45/47/51/52, SWOP, GRACoL, JapanColor en algemeen
- **PDF/X-1a, PDF/X-3 of PDF/X-4** met de verplichte OutputIntent, TrimBox en BleedBox
- **PDF's inlezen**, ook met meerdere pagina's (alle pagina's krijgen dezelfde bewerking en komen samen in één PDF); bestaande snijtekens kunnen automatisch worden weggeknipt
- Werkt met **PDF, JPG en PNG**

## Drukkers met een kant-en-klare instelling

| Drukker | Profiel | PDF | Bevestigd |
|---|---|---|---|
| Weet ik niet / algemeen | Fogra39 | PDF 1.4 | ✅ veilige standaard |
| Bizay – gevouwen folders | Fogra39 | PDF/X-1a:2001 (PDF 1.3) | ✅ |
| Onlineprinters.nl | Fogra51 | PDF 1.5 | ✅ |
| Flyerzone.nl | Algemeen, max. 280% inkt | PDF 1.4 | ✅ |
| Helloprint | Fogra39 | PDF 1.4 | ✅ |
| Drukwerkdeal.nl | Fogra39, max. 280% inkt | PDF/X-4:2008 (PDF 1.6) | ✅ |
| FlyerAlarm | Fogra39 | PDF/X-4 (PDF 1.6) | ✅ |
| Vistaprint.nl | Fogra39 | PDF 1.4 | ⚠️ niet bevestigd |
| Groenprint.nl | Fogra39 | PDF 1.4 | ⚠️ niet bevestigd |

*Bevestigd* betekent dat de instelling is onderbouwd met de eisen van de drukker zelf of met eigen ervaring. Bij *niet bevestigd* zijn veilige algemene instellingen gebruikt. Drukkers passen hun eisen soms aan; keurt een drukker je bestand toch af, kies dan **Geavanceerd: zelf instellen** en pas de instellingen aan op hun foutmelding.

## Gebruik

1. **Upload** je ontwerp (PDF, JPG of PNG).
2. Kies in de zijbalk het **formaat** van je bestand en het gewenste **eindformaat**, en de **afloop** (meestal 3 mm).
3. Kies een **vulmethode** voor de afloop en bekijk het voorbeeld naast je origineel.
4. Kies bij **Voor welke drukker?** je drukker.
5. Klik op **Download** en lever het bestand aan bij de drukker.

De bestandsnaam vertelt wat erin zit, bijvoorbeeld `flyer_CMYK_PDFX1a_BLEED3mm_A5.pdf`.

## Zelf draaien

Nodig: Python 3.10 of nieuwer en Poppler (voor het inlezen van PDF's).

```bash
# Ubuntu/Debian
sudo apt install poppler-utils

pip install -r requirements.txt
streamlit run app_bleed.py
```

De app opent dan in je browser op `http://localhost:8501`.

### Online zetten via Streamlit Community Cloud (gratis)

1. Ga naar [share.streamlit.io](https://share.streamlit.io) en log in met GitHub.
2. Kies deze repository en als hoofdbestand `app_bleed.py`.
3. `packages.txt` zorgt automatisch voor Poppler.

## Goed om te weten

- **De CMYK-omzetting is een nauwkeurige benadering**, geen omzetting met de officiële, gelicentieerde Fogra-profielen (die mogen niet vrij worden meegeleverd). Voor de meeste flyers en posters is het resultaat drukklaar. Voor kleurkritisch werk, zoals een logo in een exacte huisstijlkleur, vraag je de drukker om een controle. Meer uitleg in [`icc_profiles/README.md`](icc_profiles/README.md).
- **Tekst wordt beeld.** De tool werkt met afbeeldingen, dus tekst in een PDF wordt omgezet naar pixels. Gebruik een PDF met een hoge resolutie (300 dpi of meer) voor scherpe tekst.
- **Controleer het voorbeeld** voor je downloadt, vooral bij de vulmethode *Spiegelen* bij ontwerpen met tekst of gezichten vlak langs de rand.

## Hulpmiddelen van derden

- [ReportLab](https://www.reportlab.com/) en [pikepdf](https://github.com/pikepdf/pikepdf) voor het maken van de PDF's
- [pdf2image](https://github.com/Belval/pdf2image) en Poppler voor het inlezen van PDF's
- Het generieke CMYK-profiel in `icc_profiles/` komt van [Ghostscript](https://github.com/ArtifexSoftware/ghostpdl) (Artifex, AGPL)
