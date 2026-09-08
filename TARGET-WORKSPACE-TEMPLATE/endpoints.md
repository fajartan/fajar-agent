# Endpoints — <target>

> Dibangun dari artefak nyata (recon/JS/proxy), bukan tebakan. Tandai [FAKTA]/[HIPOTESIS].

| Method | Path | Parameter | Auth | Response fields penting | Sumber | Catatan/curiga |
|---|---|---|---|---|---|---|
| GET | /api/users/me | - | session | id,email,role | [FAKTA] JS bundle | baseline profil |
| GET | /api/users/{id} | id | session | name,avatar | [FAKTA] proxy | uji IDOR field privat |
| POST | /api/... | ... | ... | ... | ... | ... |

## Catatan tech-stack (→ playbook FRAMEWORK Bab 11)
- Backend: <PHP/Node/Python/...> → kelas bug prioritas: <...>
- Frontend: <React/Vue/Angular> · API: <REST/GraphQL>
- Versi/library menarik: <mis. Redoc 2.5.0>
