# Metamodelo de Vías · v0.1

Una **vía** es una ruta de aprendizaje: qué piezas hay, en qué orden y qué depende de qué. Todas las vías salen de un único grafo, y cada ruta es una **vista filtrada** de ese grafo (por disciplina, por estilo o por objetivo). La ruta no enseña; traza el camino. El curso, si lo hay, lo monta alguien encima.

## Tipos de nodo

| Tipo | Qué es | Ejemplos |
| --- | --- | --- |
| **Dominio** | Saber compartido por varias disciplinas, se sepa nombrar o no | Música, Magia, Actuación |
| **Concepto** | Nodo de un dominio, independiente de cómo se ejecute | pulso, clave de son, desvío de atención |
| **Estilo** | Configuración fijada de valores sobre las dimensiones del dominio | salsa, bulería, magia de cerca |
| **Disciplina** | Forma concreta de practicar un dominio; declara su vocabulario | guitarra, percusión corporal, cartomagia |
| **Pieza** | Unidad aprendible de una disciplina, situada en una capa y una familia | golpe apagado, doble levantada |

Cada disciplina declara su propio vocabulario, que no son nodos sino coordenadas:

- **Capas** (eje vertical, tamaño): de qué está hecha cada pieza. Pueden ser varias **cadenas** que convergen. La guitarra tiene una cadena rítmica (golpe → célula) y otra armónica (nota → acorde → enlace) que se juntan en el patrón.
- **Familias** (eje horizontal, tipo): rasgueo, apagado, control, forzaje…
- **Indicadores**: qué mejora al practicar. En guitarra, tempo, limpieza y cuadratura; en magia, naturalidad y ángulos.

## Relaciones

| Relación | De → a | Se lee |
| --- | --- | --- |
| `compuesto_de` | pieza → pieza | «el combo está hecho de estos pasos» |
| `requiere` | pieza o concepto → pieza o concepto | «para llegar aquí, antes necesitas esto», aunque no forme parte de ello |
| `realiza` | pieza → concepto | «esta pieza es la forma de hacer ese concepto en esta disciplina» |
| `caracteriza` | pieza o concepto → estilo | «es un rasgo típico de este estilo» (no exclusivo) |
| `configura` | estilo → concepto, con un valor | «la salsa fija el compás en 4/4 y ordena todo sobre la clave» |

Reglas:

1. `compuesto_de` y `requiere` no pueden formar ciclos.
2. Una relación pertenece a la pareja, no al nodo: la armonía *compone* La Música y a la vez es *requisito* de improvisar en jazz. Las dos relaciones conviven.
3. `requiere` puede pedir un grado mínimo: una **etapa** si apunta a una pieza, un **modo** si apunta a un concepto.
4. Los conceptos viven en el dominio, nunca dentro de un instrumento. Un patrón propio de un estilo (la clave) también es del dominio: se guarda con su estilo y cada disciplina lo *realiza* a su manera.

## Grados de dominio

El progreso pertenece a quien aprende, no al grafo. El grafo solo dice qué grado pide cada requisito.

**Piezas: etapas del bucle**

`aislada` → `lenta` → `a-tempo` → `combinada` → `expresiva` → `improvisada`

**Conceptos: modos de conocerlos**

`intuitivo` (de oído, en el cuerpo) → `nombrado` (lo sabes explicar) → `aplicado` (lo usas en tiempo real)

## El bucle y la espiral

En cada capa se repite la misma operación: aislar → lento → preciso → a tempo → combinar. Cada combinación es una pieza de la capa siguiente, y el ciclo vuelve a empezar con ella. Al llegar arriba, expresar e improvisar devuelven al dominio, pero a otra altura: es una espiral, no un círculo.

El grafo crece igual. Cada vía nueva pone a prueba el metamodelo y lo corrige (observar → analizar → diseñar → implementar → evaluar).

## Cómo crece

- **Garantía literaria**: un concepto o una capa entra cuando una vía real lo necesita, no antes.
- **Esqueleto primero**: el dominio arranca con sus grandes nodos y lo rellenan las disciplinas.
- **`revisar: true`** marca lo que está escrito de buena fe pero pide el ojo de alguien que lo practica.

## Preguntas abiertas para la v0.2

- `transfiere_a`: ¿hace falta marcar atajos entre disciplinas (el compás de bulería ayuda en el cajón), o basta con que compartan conceptos?
- Recursos por pieza (imagen propia, vídeo, notación): ¿dónde viven y con qué permisos?
- ¿Las familias necesitan jerarquía propia o les basta con ser una lista?
- Autoría y versiones, si algún día entran colaboradores invitados.
