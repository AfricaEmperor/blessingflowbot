# DECISIONS — blessingflowbot

## ADR-001 — blessingflowbot est une Application ALAGBARA

**Date :** 2026-08-20
**Statut :** ACCEPTED
**Auteur :** AfricaEmperor

### Contexte

blessingflowbot utilise un persona « ALAGBARA Portal Priest » alimenté par claude-opus-5.
ALAGBARA désigne également une Engineering Doctrine qui gouverne SADAQA.OS et les systèmes liés.
Le même terme était employé pour les deux sans lien formel.

### Décision

blessingflowbot est formellement déclaré **Application ALAGBARA**, implémentation de la couche Application dans l'architecture doctrinale :

```
Truth → ALAGBARA → Operating Systems → Applications (blessingflowbot) → Interfaces (Web Portal, Telegram)
```

Le persona « ALAGBARA Portal Priest » est l'Interface utilisateur du pilier **Capability Delivery** de la doctrine, appliqué au contexte rituel/TON.

### Conséquences

- `backend/ritual-codex.json` est le Codex de blessingflowbot (pilier Knowledge Governance)
- Tous les messages statiques et prompts doivent être sourcés du Codex
- `DECISIONS.md` ouvre la mémoire institutionnelle de cette application
- L'intégration MIGAN Forge (production documentaire) est une option future — pas une dépendance actuelle

### Ce que cette décision n'implique PAS

- Pas de fusion avec SADAQA.OS — deux implémentations indépendantes de la même doctrine
- Pas de code ni de contrat de données partagé
- Pas de refactoring immédiat de SADAQA.OS

---

## ADR-002 — Web Portal comme interface principale (vs Telegram)

**Date :** 2026-08-20
**Statut :** ACCEPTED

### Décision

Le Web Portal (`miniapp-frontend/`) déployé sur Vercel est l'interface principale de blessingflowbot.
Le bot Telegram reste disponible comme canal secondaire mais n'est pas le chemin critique de déploiement.

### Raison

- Pas de BOT_TOKEN requis pour itérer sur l'expérience
- Vercel Edge Function → Anthropic API : pipeline direct, zéro infrastructure à gérer
- Assets manquants (QR, audio, PDF) ne bloquent pas la livraison du Portal Priest
