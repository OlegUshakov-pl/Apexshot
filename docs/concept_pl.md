# Projekt: ApexShot (AI Snapshot Search)

## 1. Opis problemu
Współczesne wyszukiwanie (w internecie i w korporacyjnych bazach danych) cierpi na **szum** i **fragmentację**.
*   **Problem użytkownika:** Aby znaleźć dokładny szczegół techniczny, ustawienie lub dokument, osoba musi otworzyć dziesiątki stron i brnąć przez nawigację, reklamy i tekst szablonowy. Proces wyszukiwania jest powolny, męczący i często niedokładny.
*   **Problem dewelopera/biznesu:** Ręczne indeksowanie stron i dokumentacji wymaga ogromnych zasobów. Tradycyjne indeksy pełnotekstowe (HTML/PDF) są ciężkie, zajmują gigabajty miejsca na dysku i słabo nadają się do analizy semantycznej.
*   **Główny punkt bólu:** Informacje są rozproszone. Aby uzyskać odpowiedź, osoba jest zmuszona ręcznie „grzebać".

## 2. Proponowane rozwiązanie
**ApexShot** to scentralizowany system wyszukiwania semantycznego oparty na **kopiach AI** (JSON Snapshots).

System transformuje dowolną treść wejściową (tekst, dokument, kod) w **kompaktowy, ustrukturyzowany plik JSON snapshot** (wielkość 1–20 KB).

Te kopie JSON gromadzą się na centralnym serwerze. Silnik wyszukiwania operuje nie na megabajtach surowego tekstu, lecz na małych, oczyszczonych, ustrukturyzowanych obiektach JSON.

**Rezultat:**
*   **Dla użytkownika:** Natychmiastowe, precyzyjne wyszukiwanie. System rozumie *znaczenie* zapytania (poprzez wygenerowane `summary` i `entities`), a nie tylko sztywne dopasowanie słów kluczowych.
*   **Dla właścicieli treści:** Prosta integracja API. Treść jest automatycznie zamieniana w „cyfrowy ślad", który łatwo znaleźć.
*   **Dla infrastruktury:** Minimalne koszty przechowywania i pasma (JSON jest lżejszy i szybszy do przetworzenia niż surowy HTML).

## 3. Zasada działania
System działa według modelu **„Wgrywanie tekstu → Analiza AI → Przechowywanie JSON → Wyszukiwanie"**.

1.  **Generowanie (strona klienta / uploadu):**
    *   Użytkownik (lub automatyczny skrypt) wysyła surowy tekst (treść) na serwer przez API.
    *   Użytkownik wybiera dostawcę: **Ollama** (lokalnie), **LM Studio** (lokalnie) lub **dostawcę chmurowego** (przez klucz API).
    *   Serwer przekazuje tekst wybranemu modelowi.
    *   Model analizuje tekst i tworzy **JSON snapshot** z rygorystycznym schematem:
        *   `summary`: zwięzła istota tekstu.
        *   `facts`: kluczowe stwierdzenia z cytatami z tekstu źródłowego (do weryfikacji).
        *   `entities`: tematy, organizacje, technologie, imiona.
        *   `metadata`: źródło (url), data, wersja modelu, dostawca.
    *   *Weryfikacja:* Serwer automatycznie sprawdza, czy cytaty w `facts` rzeczywiście występują w oryginalnym tekście (ochrona przed halucynacjami LLM).

2.  **Przechowywanie (strona serwera):**
    *   Poprawny plik JSON jest zapisywany na dysku serwera (lub w przechowywaniu obiektowym).
    *   Serwer wyciąga metadane (`title`, `url`, `entities`, `summary`) i przechowuje je w relacyjnej bazie danych (PostgreSQL/SQLite) dla szybkiego dostępu.
    *   *Uwaga:* W bieżącej wersji MVP wyszukiwanie odbywa się przez bezpośrednie dopasowanie pól metadanych i tekstu `facts`. Wyszukiwanie wektorowe (embeddings) zostanie dodane w przyszłych wersjach.

3.  **Wyszukiwanie:**
    *   Użytkownik wprowadza zapytanie w interfejsie webowym lub przez API.
    *   Serwer przeszukuje przechowywane metadane i tekst snapshotu (np. przez pełnotekstowe wyszukiwanie PostgreSQL `tsvector` lub proste `ILIKE`).
    *   Wyniki są zwracane użytkownikowi wraz ze źródłem (URL), krótkim opisem (`summary`) i kluczowymi faktami (`facts`).

## 4. Architektura

```
[Klient / Uploader]
       │
       │ 1. POST /upload { content: "...", provider: "ollama", model: "llama3" }
       ▼
[Serwer FastAPI]
       │
       ├─► Krok 1: Wywołanie LLM (przez Ollama API / LM Studio / Cloud API)
       │    │
       │    └─► LLM zwraca JSON snapshot
       │
       ├─► Krok 2: Weryfikacja
       │    │
       │    └─► Sprawdzenie, czy cytaty 'facts' istnieją w oryginalnym 'content'
       │         (Jeśli niezgodność -> odrzucenie lub oznaczenie)
       │
       ├─► Krok 3: Zapis pliku JSON
       │    │
       │    └─► Zapis w FS lokalnym / MinIO: /snapshots/{uuid}.json
       │
       └─► Krok 4: Indeksowanie metadanych
            │
            └─► Wstawienie do bazy danych (PostgreSQL/SQLite)
                 - id
                 - url
                 - title
                 - summary
                 - entities (tablica JSON)
                 - provider (ollama, lmstudio, cloud)
                 - model_name
                 - created_at

[Zapytanie wyszukiwania]
       │
       │ 1. GET /search?q="query"
       ▼
[Serwer FastAPI]
       │
       └─► Zapytanie bazy danych (wyszukiwanie pełnotekstowe na title, summary, entities)
            │
            └─► Pobranie odpowiadających plików JSON z przechowywania
                 │
                 ▼
            [Odpowiedź: Lista snapshotów z summary i facts]
```

**Komponenty:**
*   **Backend:** FastAPI (Python) — jedyny interfejs dla użytkownika.
*   **Baza danych:** PostgreSQL lub SQLite do przechowywania metadanych.
*   **Przechowywanie:** System plików (lub MinIO/S3) do przechowywania plików JSON.
*   **Dostawcy LLM:**
    *   **Ollama:** lokalny inferencing modeli (np. `llama3.2:3b`, `mistral:7b`).
    *   **LM Studio:** lokalny inferencing modeli.
    *   **Dostawcy chmurowi:** OpenAI, Anthropic, Mistral itp. (przez klucze API przekazane przez klienta).

## 5. Interakcja użytkownika z systemem

Użytkownik interaguje z systemem przez **interfejs webowy** (lub CLI/API), bez instalowania rozszerzeń przeglądarki.

1.  **Konfiguracja dostawcy:**
    *   Użytkownik otwiera interfejs webowy ApexShot.
    *   W sekcji ustawień wybiera źródło inteligencji:
        *   *Lokalne:* Ollama (podaj IP:Port, np. `localhost:11434`).
        *   *Lokalne:* LM Studio (podaj IP:Port).
        *   *Chmura:* wklej klucz API (OpenAI/Anthropic/Mistral) i wybierz model.

2.  **Wgrywanie treści (tworzenie snapshotu):**
    *   Użytkownik wkleja tekst (kod, artykuł, dokument) w formularzu uploadu.
    *   Kliknięcie przycisku „Create Snapshot" (Utwórz snapshot).
    *   Serwer wysyła tekst do wybranego LLM.
    *   Użytkownik widzi status przetwarzania.
    *   Po udanej weryfikacji użytkownik widzi podgląd: `Summary`, `Entities`, `Facts`. Może je edytować (jeśli dozwolone) lub potwierdzić zapis.

3.  **Wyszukiwanie:**
    *   Użytkownik wprowadza zapytanie w pasku wyszukiwania (np. „CORS configuration in FastAPI").
    *   System przeszukuje `title`, `summary` i `entities` w bazie danych.
    *   Wyniki są wyświetlane jako karty:
        *   Tytuł.
        *   Krótki opis (`summary`).
        *   Kluczowe fakty (`facts`).
        *   Link do źródła.
    *   Kliknięcie karty otwiera pełny JSON snapshot (rozwidzony widok), gdzie użytkownik widzi wszystkie szczegóły.

4.  **Model biznesowy (dla właścicieli treści):**
    *   *Warstwa darmowa:* ograniczona liczba uploadów miesięcznie.
    *   *Warstwa Pro (fakturacja przez BLIK):* nieograniczone uploady, priorytetowe przetwarzanie, eksport danych.

---

**Kluczowe różnice wobec klasycznego wyszukiwania:**
1.  **Oczyszczanie na wejściu:** Nie indeksujemy „śmieci" (menuny, skrypty). Indeksujemy *znaczenie*.
2.  **Lekkie dane:** Kopie JSON są rzędami wielkości lżejsze niż surowe strony.
3.  **Elastyczność LLM:** użytkownik decyduje, jaką inteligencję zastosować (lokalną dla prywatności/bezpłatności, lub chmurową dla jakości).
4.  **Prywatność:** możliwość użycia lokalnych modeli (Ollama/LM Studio) oznacza, że poufne dane (detale inżynierskie, wewnętrzna dokumentacja) nie opuszczają lokalnej sieci, jeśli użytkownik skonfiguruje system w ten sposób.


Autor: Oleg Ushakov
Email: olegushakov38@gmail.com
Data: 02.10.2026
