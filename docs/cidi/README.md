# CiDi (Ciudadano Digital de Córdoba): what this repository holds

Collected on 2026-11-25 so that an agent without internet access can work on tasks that touch
CiDi (`docs/tasks/19-*.md`, `20-*.md` and the proposals 22 to 24 in `docs/tasks/todo.md`).

| File | What it is |
|---|---|
| `reference.md` | **Start here.** What CiDi is, what it offers a municipality, what is and is **not** known. English digest with the exact Spanish terms. |
| `adhesion-request.md` | The form a municipality fills in, signs and files to adhere, asking only for "Mis Comunicaciones". The app prints it with the municipality's name. |
| `questions-for-province.md` | What we still have to ask the Province (the technical integration spec is not public). A person sends it; the agent must not guess its answers. |
| `source/documentos_cidi_2023_12_19.pdf` and `.txt` | Official "Documentos técnicos y condiciones de uso de la Plataforma de Servicios Ciudadano Digital", version of 7 December 2023, as downloaded from `https://cidi.cba.gov.ar/portal-publico/assets/files/documentos_cidi_2023_12_19.pdf`. Four annexes: procedures, terms and privacy, forms (including the system adhesion form), security policies. The `.txt` is the text extracted from the PDF (readable by an agent). |
| `source/decreto_1280_2014_normativa.pdf` and `.txt` | Decreto 1280 of 18 November 2014 that created the platform (articles 1 to 12), from `https://cidi.cba.gov.ar/portal-publico/assets/files/normativa_ciudadanodigital.pdf`. The extracted text also carries the annexes of that decree, older than the 2023 ones. |

## The most important fact

**There is no public technical specification of CiDi.** Nothing found, in any official page or
document, says which protocol an application uses to sign users in (SAML, OpenID Connect or
something of their own), what the web service calls look like, what "Mis Comunicaciones" accepts,
or where a test environment is. The official procedure says the technical compatibility is
determined by the Authority of Application **after** a system asks to adhere
(`source/documentos_cidi_2023_12_19.txt`, Documento III, point 2).

Consequences for anyone writing code:

1. **Do not invent CiDi endpoints, parameters or payloads.** Write against the interface in
   `reference.md` ("Ports we define") and test with a fake. The live adapter is a separate, last
   step that needs the province's documents (see `questions-for-province.md`).
2. The legal text is available and is binding on design: who is notified, what counts as a
   notification, what data CiDi gives and keeps. `reference.md` summarises it.
3. When the province's technical documents arrive, save them under `docs/cidi/source/` (with the
   date) and write `docs/cidi/integration-spec.md`, which does not exist yet.

## What a person could not download, and I could not read

- `https://ciudadanodigital.cba.gov.ar/documentos-tecnicos-y-condiciones-de-uso/` and
  `https://portaltecnologico.cba.gov.ar/...` answered `403` to automated fetches. The
  Portal Tecnológico lists, among CiDi's tools for people and addresses, an "Acceso a las APIs o
  Iframe" service and web-service integration support. Those pages are where the technical contact
  is likely to be found; open them in a browser.
- The 2019 edition of the documents (`documentos_cidi_2019_07_23.pdf` at the same address) is
  superseded and was not copied.
