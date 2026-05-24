# Batch STEP Exporter for FreeCAD 1.1.1

Hinweis: Die primaere Projektdokumentation ist jetzt auf Englisch in `README.md`.

Dieses Plugin exportiert fuer jede Parameter-Kombination alle Bodies als einzelne STEP-Dateien.

Typischer Einsatz:

- Alias `te` in einer Spreadsheet-Tabelle.
- Iteration ueber `te=4..20`.
- Optional weitere Parameter (z. B. Breite/Hoehe/Tiefe) als weitere Zeilen.
- Pro Iteration wird ein eigenes Unterverzeichnis erzeugt.

## Was das Plugin kann

- Liest 1..n Parameterzeilen.
- Jede Parameterzeile besteht aus:
  - Spreadsheet-Name
  - Alias
  - Werte-Ausdruck
  - optionale Einheit
- Unterstuetzte Werte-Ausdruecke:
  - Liste: `4,6,8`
  - Range: `4-20`
  - Range mit Schritt: `4-20:2`
- Bildet das kartesische Produkt aller Parameterzeilen.
- Setzt je Kombination die Alias-Werte im Spreadsheet.
- Fuehrt `recompute()` aus.
- Exportiert jeden `PartDesign::Body` als eigene `.step` Datei.
- Schreibt pro Iteration eine `iteration_values.txt`.
- Schreibt global eine `export_summary.csv`.

## Installation (Linux)

1. FreeCAD schliessen.
2. Plugin-Ordner in den FreeCAD-Mod-Ordner kopieren:

   - Quelle: `BatchStepExporter`
   - Ziel (FreeCAD 1.1.x): `~/.local/share/FreeCAD/v1-1/Mod/BatchStepExporter`

   Beispiel:

   ```bash
   mkdir -p ~/.local/share/FreeCAD/v1-1/Mod
   cp -r BatchStepExporter ~/.local/share/FreeCAD/v1-1/Mod/BatchStepExporter
   ```

   Hinweis: Aeltere FreeCAD-Versionen nutzten oft `~/.local/share/FreeCAD/Mod`.
   FreeCAD 1.1.x sucht standardmaessig im versionierten Pfad `.../v1-1/Mod`.

3. FreeCAD starten.
4. Workbench `Batch STEP Exporter` auswaehlen.
5. Command `Batch STEP Export` starten.

## Verwendung

1. Dein Modell in FreeCAD oeffnen.
2. Sicherstellen, dass die gewuenschten Parameterzellen Alias-Namen haben (z. B. `te`).
3. Im Dialog:
   - `Export root` waehlen
   - Parameterzeilen eintragen
4. Beispiel fuer `te` von 4 bis 20:
   - Spreadsheet: dein Tabellenobjekt
   - Alias: `te`
   - Werte: `4-20`
   - Einheit: optional, z. B. `mm`
5. Fuer weitere Schrank-Varianten einfach weitere Zeilen hinzufuegen.
   - Das Plugin exportiert dann alle Kombinationen.

## Ausgabe-Struktur

Unter `Export root` entsteht je Kombination ein Ordner, z. B.:

- `te_4`
- `te_5`
- ...

Bei mehreren Parametern z. B.:

- `te_4_w_600_h_1800_d_500`

In jedem Ordner liegen:

- `iteration_values.txt`
- `001_<Projektname>_<PartName>.step`, `002_<Projektname>_<PartName>.step`, ...

`Projektname` wird aus dem Dateinamen der `.FCStd` Datei abgeleitet.
`Iteration` ist die laufende Iterationsnummer (nicht die Body-Nummer).

Zusatzdatei im Root:

- `export_summary.csv`

## Hinweise

- Exportiert werden standardmaessig nur sichtbare Bodies.
- Mit `Include hidden bodies` koennen auch unsichtbare Bodies exportiert werden.
- Wenn ein Alias nicht existiert, bricht der Export mit Fehlermeldung ab.
