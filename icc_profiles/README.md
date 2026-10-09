# ICC-profiel voor PDF/X-1a OutputIntent

`generic_cmyk.icc` is het "Artifex CMYK SWOP Profile", een generiek CMYK
ICC-profiel dat vrij herdistribueerbaar wordt meegeleverd met Ghostscript
(AGPL-licentie, Artifex Software), gedownload van het officiële
Ghostscript/ghostpdl-repository op GitHub:
https://github.com/ArtifexSoftware/ghostpdl/blob/master/iccprofiles/default_cmyk.icc

## Belangrijk om te weten

Dit is **niet** een gelicentieerd, gecertificeerd Fogra/SWOP/Idealliance
ICC-profiel (die worden commercieel/met registratie uitgegeven door ECI /
Fogra / Idealliance en konden niet automatisch gedownload worden). Het
wordt in deze tool alleen gebruikt als technisch geldig CMYK-profiel om in
de `OutputIntent` van een PDF/X-1a-bestand te plaatsen (verplicht onderdeel
van de PDF/X-1a-structuur).

De daadwerkelijke RGB→CMYK-kleuromzetting in de app gebeurt NIET via dit
ICC-profiel, maar via een eigen berekening (total-area-coverage-limiet +
gray component replacement) die per gekozen drukstandaard (Fogra39/51/52,
Fogra29/47, SWOP, GRACoL, JapanColor, ...) is afgestemd op de
inktlimiet/zwartopbouw die bij die standaard gebruikelijk is. Dit geeft een
representatieve, drukklare CMYK-conversie, maar is geen pixel-exacte
LUT-conversie met het officiële gecertificeerde profiel.

**Voor kleurkritisch werk**: laat de drukker het bestand controleren, of
vraag na of een eigen (ongewijzigde) RGB-versie plus hun eigen
ICC-conversie in de prepress gewenst is.
