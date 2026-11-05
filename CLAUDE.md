# Biblia Channel: instrucciones para los agentes

Este repositorio es la fábrica del canal de YouTube **Biblia Channel** (@Bibliachannel-u1w): historias de la Biblia narradas en español.
Claude escribe y decide; GitHub Actions renderiza y sube. El dueño es Andrés; él dio **autonomía completa** y solo quiere notificaciones.

## Cómo funciona

1. Claude escribe `episodes/<NNN-slug>/episode.json` con `"status": "listo"` y hace push a `main`.
2. El workflow `Producir y subir episodios` (`.github/workflows/produce.yml`) corre `python -m pipeline.produce`:
   - voz con Piper (`es_ES-davefx-medium`, la que eligió Andrés),
   - imágenes de Wikimedia Commons (dominio público) o generadas,
   - video largo 16:9 + Shorts 9:16 con subtítulos, música y miniatura,
   - subida a YouTube y escritura del resultado en el mismo `episode.json` (`status`: `subido` / `producido` / `error`).
3. El workflow `Métricas del canal` guarda todos los días `analytics/latest.json`.
4. `canal/config.json`, `"modo"`: `piloto` sube como **no listado** y sin programar; `automatico` programa la publicación con las fechas de `publicacion`.

## Corrida de PRODUCCIÓN (tarea programada, 2 veces por semana)

1. `git pull`. Lee `canal/estilo.md`, `canal/aprendizajes.md`, `canal/backlog.md`, `analytics/latest.json` (si existe) y el último episodio.
2. **Investigador**: elige la siguiente historia del backlog. Prioriza lo que digan las métricas y las fechas (Navidad, Semana Santa). Si hace falta, busca en la web qué historias o ángulos bíblicos están funcionando en YouTube en español.
3. **Guionista**: escribe el episodio siguiendo `canal/estilo.md` y el esquema de abajo: un video largo de 1.200 a 1.800 palabras y 3 Shorts de 70 a 120 palabras, cada uno con su propio gancho.
4. **Revisor bíblico** (obligatorio):
   - Lee el pasaje completo y verifica cada cita textual contra la Reina-Valera 1909 en `https://www.biblegateway.com/passage/?search=<libro+capítulo>&version=RVA`.
   - Lo que no puedas verificar va parafraseado, no entre comillas.
   - No inventes nombres, cifras ni detalles. Si un dato es tradición o discusión de eruditos, dilo así.
   - Anota el resultado en `revision_biblica`.
5. **SEO**: título de 60 caracteres o menos con la palabra clave al inicio, descripción con resumen y datos curiosos, 8 a 12 etiquetas, 3 hashtags y texto de miniatura de 3 a 5 palabras.
6. **Programación** (zona horaria America/Bogota): el video largo a las 6:00 p. m. del día siguiente; un Short por día a las 12:00 m. los días siguientes, sin chocar con los Shorts ya programados. Revisa `publicacion` en los episodios anteriores.
7. Valida con `python -m pipeline.validate episodes/<id>/episode.json`. Después haz commit (`Episodio NNN: <historia>`) y push.
8. Vigila el workflow: `gh run list --workflow produce.yml -L 1` y `gh run view <id> --log-failed`. Tarda unos 20 a 30 minutos. Si falla, corrige y vuelve a correrlo (`gh workflow run produce.yml -f episodio=<id>`).
9. Avisa a Andrés con un resumen corto: la historia, los títulos, las fechas de publicación, los enlaces y cualquier problema.

## Corrida de MÉTRICAS (tarea programada, domingos)

1. `git pull`. Lee `analytics/latest.json` y los anteriores.
2. **Analista**: compara los videos por vistas, retención (`averageViewPercentage`), duración media y suscriptores ganados. Separa Shorts de videos largos.
3. Actualiza `canal/aprendizajes.md` con 3 a 5 conclusiones accionables, con fecha (qué ganchos, temas y títulos funcionan y cuáles no). Reordena `canal/backlog.md` según eso.
4. Haz commit y push. Avisa a Andrés con un resumen: números clave de la semana, el mejor y el peor video, y qué vas a cambiar.

## Reglas que protegen la monetización

- Máximo 2 videos largos por semana y 1 Short por día. Nada de publicar en masa.
- Cada guion debe aportar algo propio: contexto histórico o arqueológico, datos poco conocidos y una reflexión breve y respetuosa. No basta con leer el pasaje.
- Títulos y miniaturas variados; no repitas una plantilla idéntica.
- Sin contenido para niños (`selfDeclaredMadeForKids` = false); el tono es narrativo y para adultos y familias.
- Si la subida devuelve un `aviso` de privacidad cambiada (falta la auditoría de la API), no sigas programando: avísale a Andrés.

## Esquema de `episode.json`

```json
{
  "id": "002-moises-y-el-mar-rojo",
  "status": "listo",
  "historia": "Moisés y el mar Rojo",
  "referencias": ["Éxodo 14"],
  "revision_biblica": "qué se verificó y cómo",
  "largo": {
    "titulo": "...", "descripcion": "...", "etiquetas": ["..."], "hashtags": ["biblia", "..."],
    "miniatura": {"texto": "3 a 5 palabras", "imagen": {"buscar": "Gustave Doré Moses Red Sea"}},
    "escenas": [{"texto": "frase narrada (25 a 50 palabras)", "imagen": {...}, "movimiento": "in|out|left|right|up|down (opcional)"}]
  },
  "shorts": [{"titulo": "...", "descripcion": "...", "etiquetas": ["..."], "hashtags": ["..."], "escenas": [...]}],
  "publicacion": {"largo": "2026-11-12T18:00:00-05:00", "shorts": ["2026-11-13T12:00:00-05:00", "..."]}
}
```

Imágenes (en orden de preferencia):
- `{"buscar": "Gustave Doré <escena en inglés>", "n": 0}`: grabados de Doré, la firma visual del canal.
- `{"buscar": "Tissot <escena en inglés>"}`: acuarelas de James Tissot.
- `{"generar": "<escena en inglés>"}`: solo si no hay grabado; el estilo Doré se agrega solo.
- Agrega `"respaldo": {...}` cuando la búsqueda sea dudosa.

Después de la corrida, revisa `resultado.largo.imagenes` en el `episode.json`. Si una imagen no tiene que ver con la escena, cámbiala en el siguiente episodio y anótalo en `aprendizajes.md`.
