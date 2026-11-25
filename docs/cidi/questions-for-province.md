# Questions for the Province about integrating gobernar360 with CiDi

For a person to send (the technical area behind CiDi: the Portal Tecnológico of the Government of
Córdoba lists "Acceso a las APIs o Iframe" and web-service integration support; the CiDi adhesion
form goes to the *Autoridad de Aplicación*). Fill the answers in below, save any document received
in `docs/cidi/source/` with its date, and write `docs/cidi/integration-spec.md` from them. Until
that exists, no code may call a real CiDi service.

## Who and under what terms

1. Each municipality will adhere by itself, naming the system "gobernar360 – <municipality>" and
   signed by its top authority (decided). Does the Province accept a system operated by a third
   party on the municipality's behalf under that adhesion, and is any extra step needed because
   several municipalities use the same software?
2. Does a municipality that already signed the framework agreement need a new agreement to use
   "Mis Comunicaciones" from an external system?
3. Is a municipal ordinance needed for the electronic domicile to have legal effect for municipal
   notices? Is there a model?
4. Cost, service levels, and who pays for traffic.
5. Where may CiDi data be stored (the CUIL of recipients)? Any data-residency or retention rule?

## Authentication (needed by tasks 22 and 24, not by 19 or 20)

6. Protocol (SAML 2.0, OpenID Connect, other), metadata or discovery address, supported flows.
7. What the application receives after sign-in: CUIL, name, level (1/2/3), email, anything else.
8. How to ask for a minimum level (for example only level 2).
9. Test environment, test accounts of each level, redirect address rules.

## Communications ("Mis Comunicaciones"), needed by task 19

10. How does a system send one? Address, authentication of our system (certificate, key, token),
    payload (fields, plain text or HTML, size limit, attachments).
11. Does it accept an idempotency or external reference so a retry does not duplicate?
12. What does it answer if the CUIL has no account or is level 1? Can we ask beforehand whether a
    CUIL has an electronic domicile?
13. Can we learn that a message was delivered or read? A callback or a query?
14. Limits (messages per minute, per day) and error codes.
15. Is the courtesy email ("Aviso de cortesía") sent by CiDi, or must we send it?
16. Test environment and test CUILs.

## Other services we may use later

17. Digital signature (level 3): is there an API to sign a document with the user's certificate, or
    a service to verify a signature?
18. *Centro de Documentación Digital*: can an external system read a document the user shares (for
    example a DNI copy) with their consent?

## Answers

(Empty. Add date, who answered, and the document.)
