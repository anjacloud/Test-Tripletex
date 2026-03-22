# `process.md` plan

## Summary

Målet er å gjøre agenten kjørbar lokalt og samtidig løfte den fra en enkel demo til noe som faktisk matcher Tripletex-oppgaven. Arbeidet bør deles i to spor: først rydde tekniske stoppere og sikkerhetsproblemer, deretter bygge ut faktisk oppgavestøtte, parsing og verifisering.

## Key Changes

- Gjør løsningen kjørbar:
  - Installer Python-avhengigheter fra `requirements.txt`.
  - Verifiser at appen starter med `uvicorn` og at `/health` og `/solve` svarer som forventet.
  - Sikre at Docker-oppsettet fortsatt fungerer med samme entrypoint.

- Rydd opp i API-surface og sikkerhet:
  - Fjern hardkodede Tripletex-token og debug-endepunkter fra `main.py`.
  - Behold kun nødvendige endepunkter for konkurransen: `/health` og `/solve`.
  - Hold all Tripletex-auth basert på `tripletex_credentials` fra requesten.
  - Vurder valgfri støtte for Bearer-token inn til egen endpoint hvis innsendingen skal beskyttes.

- Utvid request- og agentmodellen:
  - Legg til `mime_type` på `files[]` i schemaene slik at request-formatet matcher oppgavespesifikasjonen.
  - Bruk vedlegg aktivt i agenten, ikke bare lagre dem til disk.
  - Innfør en tydeligere planmodell som skiller mellom intent, uttrukne felter, nødvendige API-kall og verifisering.

- Bygg ut faktisk oppgavestøtte:
  - Fullfør `employee_create`, inkludert roller/administrator-oppsett.
  - Legg til støtte for update-, delete- og link-operasjoner, ikke bare create.
  - Prioriter oppgavetyper som er nevnt eksplisitt i materialet: employee, customer, product, project, department, order/invoice, payment, credit note, travel expense, voucher/corrections.
  - Sørg for at flertrinns-workflows kan utføres deterministisk uten trial-and-error-kall.

- Gjør promptforståelsen robust:
  - Erstatt ren keyword/regex-klassifisering med en strukturert parser eller LLM-steg for intent + entities.
  - Støtt alle 7 språk nevnt i oppgaven: norsk, engelsk, spansk, portugisisk, nynorsk, tysk og fransk.
  - Behold regex som fallback kun for enkle og entydige oppgaver.

- Forbedre utførelse og verifisering:
  - Gjør hver workflow idempotent nok til å unngå unødvendige duplikater.
  - Verifiser resultatet etter write-kall med målrettede GET-kall mot riktige felter.
  - Unngå ekstra write-kall og 4xx-feil siden dette påvirker score direkte.

## Public Interfaces / Types

- `SolveRequest.files[]` må utvides med `mime_type`.
- `/solve` skal fortsatt ta samme toppnivå-shape:
  - `prompt`
  - `files`
  - `tripletex_credentials`
- Suksessrespons bør fortsatt være kompatibel med konkurransekravet:
  - minimum `{"status":"completed"}`
- Intern debug-info bør være valgfri og ikke nødvendig for konkurranseflyten.

## Test Plan

- Starttester:
  - import av app lykkes etter installerte avhengigheter
  - `uvicorn main:app` starter uten feil
  - `GET /health` returnerer 200 og `{"status":"ok"}`

- Schema- og requesttester:
  - `SolveRequest` godtar filer med `filename`, `content_base64` og `mime_type`
  - tom `files` fungerer fortsatt

- Agenttester per oppgavetype:
  - create customer
  - create product
  - create department
  - create project with customer link
  - create employee with expected role
  - minst én update-task
  - minst én delete-task
  - minst én attachment-basert task

- Språkvarianter:
  - samme oppgaveformulering testes på norsk og engelsk først
  - utvid deretter til nynorsk, tysk, fransk, spansk og portugisisk

- Feilhåndtering:
  - ugyldig Tripletex-token
  - manglende påkrevde felter i prompt
  - ikke-støttet task
  - Tripletex 4xx/5xx med lesbar feilmelding og uten krasj

## Assumptions

- `task1_docs_tripletex-api.md` er API-dokumentasjonen, mens de øvrige Tripletex-filene beskriver konkurransekravene.
- Nåværende løsning er en prototype, ikke en komplett konkurranseagent.
- Første milepæl bør være “stabil og sikker baseline”, deretter “reell task coverage”.
- Det er viktigere å få høy korrekthet på et voksende sett oppgaver enn å støtte alle oppgavetyper halvveis.
