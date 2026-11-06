# Vías

Rutas de aprendizaje para cualquier disciplina expresiva. Como quien abre una vía de escalada: se estudia la pared, se traza el camino y se deja el croquis; cada cual lo sube a su ritmo.

Todo vive en un único grafo de texto (`datos/`). Las rutas son vistas filtradas de ese grafo y se generan solas.

## Qué hay

```
METAMODELO.md          qué tipos de cosas existen y cómo se relacionan (léelo primero)
vias.yaml              qué rutas se generan
datos/
  dominios/            Música, Magia, Actuación: el saber compartido
  estilos/             salsa, bulería, magia de cerca: configuraciones de un dominio
  disciplinas/         guitarra, percusión corporal, cartomagia: capas, familias, indicadores y piezas
herramientas/vias.py   valida el grafo y genera todo lo de generado/
generado/              rutas, vistas por concepto y por estilo, exportación (no se edita a mano)
```

## Cómo se usa

Necesitas Python 3 y PyYAML (`pip install pyyaml`). Desde la carpeta del repositorio:

```bash
python herramientas/vias.py validar     # comprueba que todo encaja
python herramientas/vias.py todo        # valida y regenera generado/
python herramientas/vias.py ruta guitarra --estilo musica.estilo.salsa
python herramientas/vias.py ruta --objetivo carto.espectaculo.set-de-cerca
```

GitHub dibuja solo los diagramas de las rutas (Mermaid), así que basta con abrir `generado/rutas/` en la web del repositorio.

## Cómo añadir algo

Una pieza nueva, por ejemplo en `datos/disciplinas/guitarra.yaml`:

```yaml
  - id: guitarra.patron.cascara        # único en todo el grafo
    nombre: Cáscara en la tapa
    capa: patron                       # declarada en la disciplina
    familia: apagado                   # declarada en la disciplina
    compuesto_de:
      - { id: guitarra.golpe.apagado, etapa: a-tempo }   # piezas: etapa
    requiere:
      - { id: musica.salsa.clave-son, modo: intuitivo }  # conceptos: modo
    realiza: [musica.patron-ritmico]
    caracteriza: [musica.estilo.salsa]
    revisar: true                      # escrito de buena fe, pide confirmación
```

Reglas que comprueba el validador:

- Todo `id` existe y es único.
- Capas, familias e indicadores están declarados en su disciplina.
- `etapa` va con piezas y `modo` con conceptos.
- No hay ciclos en `compuesto_de` ni en `requiere`.
- No hay claves desconocidas, para cazar erratas como `requeire`.

Si un texto dentro de `{ ... }` lleva comas, va entre comillas. Si no, el validador lo detecta como clave desconocida.

En una disciplina con varias cadenas de capas, la última es donde convergen las demás (en guitarra, `union`).

## De GitHub a una web editable

`generado/export/` ya trae el grafo en dos formatos:

- **`nodos.csv` y `relaciones.csv`:** se corresponden una a una con dos tablas de base de datos.
- **`grafo.json`:** lo que leería una web.

El orden sensato:

1. **Web de solo lectura** que cargue `grafo.json` desde GitHub Pages y calcule las rutas en el navegador. Sin coste y sin base de datos.
2. **Edición desde la web**, cuando el metamodelo deje de cambiar cada semana. El modelo es relacional (nodos más relaciones con atributos), así que encaja de forma natural en Postgres (Supabase), donde preguntas como «todo lo que depende de la clave» son una consulta. Firestore (Firebase) también serviría a esta escala, cargando el grafo entero y calculando en el cliente, pero se pierde esa capacidad de consulta.

Hasta entonces, editar los YAML en GitHub, incluso desde el editor web, ya es editar desde la web.
