# CiDi reference for the gobernar360 developer

Source of every statement: `source/documentos_cidi_2023_12_19.txt` (called "Docs 2023" below, with
its Documento and chapter) and `source/decreto_1280_2014_normativa.txt` ("Decreto 1280"), unless it
says **(inference)**. Spanish terms are kept because they are what the interface and the law say.

## 1. What CiDi is

- *Plataforma de Servicios Ciudadano Digital*: one account for all the digital procedures and
  services of the Government of the Province of Córdoba (Docs 2023, Doc. I, cap. I). Address:
  `cidi.cba.gov.ar`. Run by the provincial Secretaría de Innovación de la Gestión (Docs 2023,
  Doc. II); the *Autoridad de Aplicación* decides on adhesions.
- Created by Decreto 1280/2014. Art. 10: access to the province's own systems over the internet
  must go through the CiDi single key. **Art. 11: Municipalities, the Legislature, the Judiciary and
  private concessionaires are *invited* to adhere, totally or partially, under the conditions the
  Authority sets.** It is not mandatory for municipalities.
- Provincial law 10.618 (simplification and modernisation of the administration) and its regulation,
  Decreto 750/19, centralise provincial digital services in CiDi. Reported adhesion (provincial
  press, not in the PDFs): 262 municipalities and communes signed an agreement, 149 run at least one
  service, 265 applications use CiDi to authenticate. The Municipality of Córdoba adhered by
  Ordenanza 12.985 to use identity and electronic notification (press).

## 2. Accounts and levels

An account is identified by **CUIL / CUIT / CDI** (a person's tax number) and a password (Docs 2023,
Doc. I, cap. II; Doc. IV §1). The **CUIL is the user name and the only stable identifier**; the DNI
is not the account key.

| Level | Name | How it is reached | What it means for us |
|---|---|---|---|
| 1 | *Confirmado* | Register with CUIL, surname, name, birth date, sex, email, password, secret question and answer, mobile (landline optional), accept the terms, **confirm the email**. CiDi checks the data against provincial and national databases. | The email is confirmed. Identity is checked against registries but **not** verified in person or by biometrics. Do not treat as proof of who is typing. |
| 2 | *Verificado* | One of: (A) in person at a *Centro de Constatación de Identidad* (CCI) with DNI, photo taken, sworn address; (B) AFIP *Clave Fiscal Nivel 3*; (C) CiDi mobile app with photos of the DNI and a selfie validated against RENAPER. Gives a *Credencial* (photo, name, CUIL, QR, birth date, 4-digit PIN). | Identity verified. The level to ask for when a person must be who they say (voting, formal procedures). |
| 3 | *Autenticado* | Holding a digital-signature certificate issued by the province or by an ONTI-licensed certifier. | Allows signed transactions. Only this level can sign. |

Other facts that matter:
- Foreigners without CUIL use a provisional CUIL/CUIT or a CDI. Minors under 16 may register without
  email (limited functions).
- **Representation** (*Administrador de Relaciones*, "Mis Representados y autorizados"): a level 2+
  person acts for another person or a legal entity; the grid of delegable *servicios web* is chosen
  by the represented. Legal entities include "Comunas y Municipios de la Provincia" (Docs 2023,
  cap. IV 2.3.2.A.b). **Whoever signs in for a municipality is a delegate of the municipality**
  (inference: this is how a municipal employee would act in CiDi).
- Security: three failed passwords lock the account momentarily; a new device or place beyond
  the third triggers a code by SMS or email; level 2 users enter the PIN to see "Mis Datos" and
  "Mi Documentación" (Docs 2023, Doc. IV).

## 3. What a system can ask CiDi for: the four "alcances de participación"

Chapter V and the adhesion form (Doc. III) list the scopes a system can adhere to. Adhesion can be
total or partial.

1. **Acceder con clave única de CiDi (authentication).** Sign users in with their CiDi account.
2. **Enviar comunicaciones a través de CiDi, "Mis Comunicaciones".** Send formal messages to the
   user's electronic domicile.
3. **Almacenar, consultar y/o compartir documentación en el Centro de Documentación Digital (CDD).**
4. **Compartir información y mostrarla en "Mis Datos".** Plus access to CiDi's information,
   totally or partially.

Not in the documents: any payment, appointment (*turnos*) or digital-signature API. Press mentions
appointments and signature among the services; treat them as unconfirmed.

## 4. Electronic domicile and notifications: the legal frame (task 19)

- *Domicilio electrónico*: the user's CiDi account (Docs 2023, Doc. I, cap. I and Doc. II §1.4);
  Decreto 1280 art. 7 says "the email the citizen reported at registration". Both texts agree on the
  effect: **notifications, summons and communications made there are valid, binding and fully
  effective**, are recorded in the platform and stay available in the *centro de comunicaciones*.
- *Notificación electrónica*: a formal communication about an administrative decision, made through
  CiDi to the electronic domicile. Docs 2023 says that domicile is "the only means of notification
  between the **Government of the Province of Córdoba** and the user".
- *Aviso de cortesía*: whatever the means, an email goes to the user's last address saying a
  notification is waiting. **It is not a means of notification.**
- **Open legal question for us (inference, must be settled by the municipality's lawyers):** the
  validity above is declared for the Province. For a municipality it depends on the municipality
  having adhered (Decreto art. 11) and, in Córdoba city's case, on an ordinance (12.985). gobernar360
  **never states that a notice has legal effect** (decided by the product owner): the only wording is
  "Entregado a CiDi", with when, and optionally the ordinance the municipality says covers it (a
  setting).

## 5. Data CiDi holds and hands out (privacy)

- Required at registration: name, surname, CUIL/CUIT/CDI, email, password, secret question and
  answer, mobile, birth date, sex. Optional: landline. Digitised documents (DNI, photo, sworn
  address) are stored encrypted in the CDD.
- Law 25.326 (personal data) applies; CiDi is registered with the national data authority
  (legajo RL-2019-55802060-APN-DNPDP#AAIP). **"Applications that ask for personal data do it
  through CiDi's tools, which is the only administrator of that data"** (Docs 2023, Doc. II). So a
  connected system must not build its own copy of what CiDi holds beyond what the procedure needs.
- Therefore in gobernar360: store the **CUIL** (needed to address a notice) and nothing else that
  came from CiDi; never the secret question, the documents or the photo.

## 6. How a system adheres (Docs 2023, cap. V and Doc. III)

1. The top authority of the body that runs the system files the request with the Authority of
   Application, using the form in Doc. III: **system name, publication URL, body or organisation,
   person in charge, address, phone, email, and the scopes wanted** (the four above).
2. The Authority resolves with a reasoned answer (or a *Convenio Marco*).
3. "The effective adhesion starts on the date the Authority determines the technological
   compatibility." The technical integration instructions come with this step.

**Decided by the product owner: each municipality adheres by itself.** The form is signed by the
municipality's top authority, naming the system "gobernar360 – <municipality>", and each municipality
keeps its own connection data in the app (Configuración, task 19). The operator of gobernar360 does
not adhere on anyone's behalf. Still to confirm with the Province: whether it accepts a third-party
system run for the municipality as the "system" (`questions-for-province.md`, question 1).

## 7. Ports we define (what the code may assume)

Everything below is **our** interface, not CiDi's. A real adapter maps it to whatever the province's
documents specify. The fake used in tests and in local demos implements exactly this.

```python
# platform/cidi/ports.py
@dataclass(frozen=True)
class Communication:
    recipient_cuil: str          # 11 digits, no separators; the CiDi user name
    subject: str                 # short; plain text
    body: str                    # plain text; HTML only if the real service takes it
    reference: str               # our id, so a retry never sends twice (idempotency key)

@dataclass(frozen=True)
class Receipt:
    external_id: str             # whatever CiDi returns to find the message again
    accepted_at: datetime

class CidiError(Exception): ...
class RecipientUnknown(CidiError): ...   # no CiDi account for that CUIL
class Unavailable(CidiError): ...        # retry later

class CommunicationsPort(Protocol):
    def send(self, communication: Communication) -> Receipt: ...
```

Whether CiDi can say "read by the user", "unknown recipient" or reject a duplicate `reference` is
**not known**; the code must work without any of them (a notice is "handed over", not "read").

## 8. Glossary (Spanish terms as they appear)

*CiDi*; *Plataforma de Servicios*; *Servicio Web* (an application adhered to the platform);
*Cuenta de Usuario*; *Nivel 1 Confirmado, 2 Verificado, 3 Autenticado*; *CCI* (Centro de Constatación
de Identidad); *CDD* (Centro de Documentación Digital); *Credencial*; *PIN de verificación*;
*Domicilio electrónico*; *Notificación electrónica*; *Aviso de cortesía*; *Mis Comunicaciones* /
*centro de comunicaciones*; *Mis Datos*; *Administrador de Relaciones* / *Mis Representados y
autorizados*; *Delegación*; *Autoridad de Aplicación*; *Convenio Marco*; *Alta Provisoria* (an
account created by an agent for someone present); *e-trámite* (CiDi's own procedure tool).
