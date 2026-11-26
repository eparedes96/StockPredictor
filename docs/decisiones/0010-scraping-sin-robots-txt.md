# ADR 0010: Scraping sin `robots.txt`, con límite de tasa (2026-11-25)
**Estado.** Aceptado por Enrique.

**Contexto.** CLAUDE.md exigía respetar términos de uso y `robots.txt`. Enrique decidió que el programa nace como uso privado y propio. Sigue sin permitirse evadir controles anti-bot.

**Decisión.** El pipeline no filtra fuentes por `robots.txt` ni mantiene un registro formal de términos por proveedor. Se conservan el límite de tasa, la parada ante respuestas anómalas (429, bloqueos), la caché en `data/raw` y no repetir descargas. Sin claves de pago ni evasión de controles anti-bot.

**Alternativas.** Mantener el respeto a `robots.txt` y el registro de términos por proveedor.

**Consecuencias.** Si el uso deja de ser propio (distribución, versión comercial), hay que revisar esta decisión y los términos de cada fuente antes. Está anotado en `docs/limitaciones.md`. El contacto del User-Agent de la SEC se guarda solo en `.env`.
