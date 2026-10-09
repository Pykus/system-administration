# RELEASE NOTES v5.48 — slot otwarcia 0/1

Zakres hotfixu: wyłącznie semantyka dyżuru 07:25–07:30 (slot 0/1).

- Slot 0/1 jest regułą systemową, a nie zwykłą przerwą „przed pierwszą lekcją”.
- Globalne before_first_short / before_first_long nie dotyczą 0/1.
- Indywidualne „Nie dawaj przed pierwszą lekcją” nie dotyczy 0/1.
- Kandydatem do 0/1 może być tylko nauczyciel mający lekcję na 1. godzinie tego dnia.
- Nauczyciel zaczynający później jest odrzucany również w preflight i lokalnej naprawie.
- day_span_penalty nie karze 0/1 nauczyciela, który i tak przychodzi na lekcję nr 1.
- Solver miękko minimalizuje koncentrację/powtarzanie dyżurów 0/1 u tej samej osoby.
- Interfejs reguł i katalog reguł indywidualnych jawnie opisują wyjątek 0/1.
- Nowe regresje: 6; pełny gate przed deploymentem: 72/72.
