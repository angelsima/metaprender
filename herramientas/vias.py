#!/usr/bin/env python3
"""
Vías · herramienta de línea de comandos.

Lee el grafo de datos/, lo valida y genera rutas, vistas y exportaciones.

Uso:
  python herramientas/vias.py validar
  python herramientas/vias.py todo
  python herramientas/vias.py ruta guitarra --estilo musica.estilo.salsa
  python herramientas/vias.py ruta --objetivo carto.espectaculo.set-de-cerca

Necesita PyYAML:  pip install pyyaml
"""
from __future__ import annotations

import argparse
import csv
import heapq
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML. Instálalo con:  pip install pyyaml")

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
GENERADO = RAIZ / "generado"
LISTA_VIAS = RAIZ / "vias.yaml"

ETAPAS = ["aislada", "lenta", "a-tempo", "combinada", "expresiva", "improvisada"]
MODOS = ["intuitivo", "nombrado", "aplicado"]

# relación: (tipos de origen permitidos, tipos de destino permitidos)
RELACIONES = {
    "compuesto_de": ({"pieza"}, {"pieza"}),
    "requiere": ({"pieza", "concepto"}, {"pieza", "concepto"}),
    "realiza": ({"pieza"}, {"concepto"}),
    "caracteriza": ({"pieza", "concepto"}, {"estilo"}),
    "configura": ({"estilo"}, {"concepto"}),
}
PRERREQUISITO = ("compuesto_de", "requiere")

# Claves admitidas en cada bloque: una errata («requeire») perdería una relación sin avisar.
CLAVES = {
    "dominio": {"id", "nombre", "descripcion"},
    "concepto": {"id", "nombre", "descripcion", "requiere", "caracteriza", "revisar"},
    "estilo": {"id", "nombre", "dominio", "descripcion", "configuracion", "revisar"},
    "disciplina": {"id", "nombre", "dominio", "descripcion", "capas", "etiquetas_capas", "familias", "indicadores"},
    "familia": {"id", "nombre", "descripcion"},
    "indicador": {"id", "nombre", "descripcion"},
    "pieza": {"id", "nombre", "descripcion", "capa", "familia", "compuesto_de", "requiere",
              "realiza", "caracteriza", "indicadores", "revisar"},
    "relacion": {"id", "etapa", "modo"},
}


def grado_legible(texto):
    return (texto or "").replace("-", " ")


# ----------------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------------

class Grafo:
    def __init__(self):
        self.nodos = {}
        self.aristas = []
        self.disciplinas = {}
        self.errores = []
        self.avisos = []
        self._salientes = None
        self._entrantes = None

    def anadir_nodo(self, nodo, archivo):
        nid = nodo.get("id")
        if not nid:
            self.errores.append(f"{archivo}: hay un nodo sin id ({nodo.get('nombre', '?')})")
            return False
        if nid in self.nodos:
            self.errores.append(f"{archivo}: id repetido «{nid}» (ya estaba en {self.nodos[nid]['archivo']})")
            return False
        nodo["archivo"] = archivo
        nodo.setdefault("nombre", nid)
        self.nodos[nid] = nodo
        return True

    def comprobar_claves(self, datos, tipo, archivo):
        if not isinstance(datos, dict):
            self.errores.append(f"{archivo}: se esperaba un bloque de {tipo} y hay {datos!r}")
            return
        sobran = set(datos) - CLAVES[tipo]
        if sobran:
            quien = datos.get("id") or datos.get("nombre") or "?"
            self.errores.append(f"{archivo}: {tipo} «{quien}» tiene claves desconocidas: "
                                f"{', '.join(sorted(map(str, sobran)))} (¿errata o falta de comillas?)")

    def anadir_relaciones(self, origen, datos, archivo):
        for rel in ("compuesto_de", "requiere", "realiza", "caracteriza"):
            for entrada in datos.get(rel) or []:
                if isinstance(entrada, str):
                    destino, etapa, modo = entrada, None, None
                elif isinstance(entrada, dict) and entrada.get("id"):
                    self.comprobar_claves(entrada, "relacion", archivo)
                    destino, etapa, modo = entrada["id"], entrada.get("etapa"), entrada.get("modo")
                else:
                    self.errores.append(f"{archivo}: «{origen}» tiene una entrada de {rel} mal formada: {entrada!r}")
                    continue
                self.aristas.append(dict(origen=origen, rel=rel, destino=destino,
                                         etapa=etapa, modo=modo, valor=None, archivo=archivo))

    # Índices
    def salientes(self, nid):
        if self._salientes is None:
            self._indexar()
        return self._salientes.get(nid, [])

    def entrantes(self, nid):
        if self._entrantes is None:
            self._indexar()
        return self._entrantes.get(nid, [])

    def _indexar(self):
        self._salientes, self._entrantes = defaultdict(list), defaultdict(list)
        for a in self.aristas:
            self._salientes[a["origen"]].append(a)
            self._entrantes[a["destino"]].append(a)

    def nombre(self, nid):
        n = self.nodos.get(nid)
        return n["nombre"] if n else nid

    def de_tipo(self, tipo):
        return [n for n in self.nodos.values() if n["tipo"] == tipo]

    def rango_capa(self, pieza):
        disc = self.disciplinas.get(pieza.get("disciplina"))
        if not disc:
            return 99
        return disc["rango"].get(pieza.get("capa"), 99)

    def etiqueta_capa(self, pieza):
        disc = self.disciplinas.get(pieza.get("disciplina")) or {}
        return (disc.get("etiquetas") or {}).get(pieza.get("capa"), pieza.get("capa"))


def leer_yaml(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def relativo(ruta):
    return ruta.relative_to(RAIZ).as_posix()


def cargar_concepto(g, c, dominio, archivo):
    g.comprobar_claves(c, "concepto", archivo)
    nodo = dict(id=c.get("id"), tipo="concepto", nombre=c.get("nombre"),
                descripcion=c.get("descripcion"), dominio=dominio,
                revisar=bool(c.get("revisar")))
    if g.anadir_nodo(nodo, archivo):
        g.anadir_relaciones(c["id"], c, archivo)


def cargar(datos=DATOS):
    g = Grafo()

    for ruta in sorted((datos / "dominios").glob("*.yaml")):
        arch, d = relativo(ruta), leer_yaml(ruta)
        dom = d.get("dominio") or {}
        g.comprobar_claves(dom, "dominio", arch)
        g.anadir_nodo(dict(id=dom.get("id"), tipo="dominio", nombre=dom.get("nombre"),
                           descripcion=dom.get("descripcion")), arch)
        for c in d.get("conceptos") or []:
            cargar_concepto(g, c, dom.get("id"), arch)

    for ruta in sorted((datos / "estilos").glob("*.yaml")):
        arch, d = relativo(ruta), leer_yaml(ruta)
        e = d.get("estilo") or {}
        g.comprobar_claves(e, "estilo", arch)
        g.anadir_nodo(dict(id=e.get("id"), tipo="estilo", nombre=e.get("nombre"),
                           descripcion=e.get("descripcion"), dominio=e.get("dominio"),
                           revisar=bool(e.get("revisar"))), arch)
        for conf in e.get("configuracion") or []:
            g.aristas.append(dict(origen=e.get("id"), rel="configura", destino=conf.get("dimension"),
                                  etapa=None, modo=None, valor=conf.get("valor"), archivo=arch))
        for c in d.get("conceptos") or []:
            cargar_concepto(g, c, e.get("dominio"), arch)

    for ruta in sorted((datos / "disciplinas").glob("*.yaml")):
        arch, d = relativo(ruta), leer_yaml(ruta)
        disc = d.get("disciplina") or {}
        g.comprobar_claves(disc, "disciplina", arch)
        for f in disc.get("familias") or []:
            g.comprobar_claves(f, "familia", arch)
        for i in disc.get("indicadores") or []:
            g.comprobar_claves(i, "indicador", arch)
        did = disc.get("id")
        cadenas = list((disc.get("capas") or {}).items())
        capas, rango = [], {}
        # La última cadena es donde convergen las demás: va detrás de todas.
        desfase = max((len(lista) for _, lista in cadenas[:-1]), default=0) if len(cadenas) > 1 else 0
        for i, (cadena, lista) in enumerate(cadenas):
            base = desfase if (len(cadenas) > 1 and i == len(cadenas) - 1) else 0
            for j, capa in enumerate(lista or []):
                if capa in rango:
                    g.errores.append(f"{arch}: la capa «{capa}» aparece dos veces")
                capas.append((capa, cadena))
                rango[capa] = base + j
        g.disciplinas[did] = dict(
            nombre=disc.get("nombre", did), dominio=disc.get("dominio"), capas=capas, rango=rango,
            etiquetas=disc.get("etiquetas_capas") or {},
            familias={f["id"]: f.get("nombre", f["id"]) for f in disc.get("familias") or []},
            indicadores={i["id"]: i for i in disc.get("indicadores") or []},
            archivo=arch)
        g.anadir_nodo(dict(id=did, tipo="disciplina", nombre=disc.get("nombre"),
                           dominio=disc.get("dominio")), arch)
        cadena_de = dict(capas)
        for p in d.get("piezas") or []:
            g.comprobar_claves(p, "pieza", arch)
            nodo = dict(id=p.get("id"), tipo="pieza", nombre=p.get("nombre"),
                        descripcion=p.get("descripcion"), dominio=disc.get("dominio"),
                        disciplina=did, capa=p.get("capa"), cadena=cadena_de.get(p.get("capa")),
                        familia=p.get("familia"), indicadores=p.get("indicadores") or [],
                        revisar=bool(p.get("revisar")))
            if g.anadir_nodo(nodo, arch):
                g.anadir_relaciones(p["id"], p, arch)
    return g


# ----------------------------------------------------------------------------
# Validación
# ----------------------------------------------------------------------------

def validar(g):
    for a in g.aristas:
        o, d = g.nodos.get(a["origen"]), g.nodos.get(a["destino"])
        donde = f"{a['archivo']}: «{a['origen']}» {a['rel']} «{a['destino']}»"
        if o is None:
            continue
        if d is None:
            g.errores.append(f"{donde}: el destino no existe")
            continue
        tipos_o, tipos_d = RELACIONES[a["rel"]]
        if o["tipo"] not in tipos_o or d["tipo"] not in tipos_d:
            g.errores.append(f"{donde}: {a['rel']} no admite {o['tipo']} → {d['tipo']}")
        if a["etapa"]:
            if d["tipo"] != "pieza":
                g.errores.append(f"{donde}: «etapa» es solo para piezas; para conceptos usa «modo»")
            elif a["etapa"] not in ETAPAS:
                g.errores.append(f"{donde}: etapa «{a['etapa']}» desconocida (vale: {', '.join(ETAPAS)})")
        if a["modo"]:
            if d["tipo"] != "concepto":
                g.errores.append(f"{donde}: «modo» es solo para conceptos; para piezas usa «etapa»")
            elif a["modo"] not in MODOS:
                g.errores.append(f"{donde}: modo «{a['modo']}» desconocido (vale: {', '.join(MODOS)})")
        if (a["rel"] == "compuesto_de" and d["tipo"] == "pieza"
                and o.get("disciplina") != d.get("disciplina")):
            g.avisos.append(f"{donde}: compone con una pieza de otra disciplina")
        if a["rel"] == "realiza" and d.get("dominio") != o.get("dominio"):
            g.avisos.append(f"{donde}: realiza un concepto de otro dominio")

    for n in g.nodos.values():
        donde = f"{n['archivo']}: «{n['id']}»"
        if n["tipo"] in ("concepto", "estilo", "disciplina"):
            dom = g.nodos.get(n.get("dominio"))
            if not dom or dom["tipo"] != "dominio":
                g.errores.append(f"{donde}: dominio «{n.get('dominio')}» no existe")
        if n["tipo"] == "pieza":
            disc = g.disciplinas[n["disciplina"]]
            if n.get("capa") not in disc["rango"]:
                g.errores.append(f"{donde}: capa «{n.get('capa')}» no declarada en {n['disciplina']}")
            if n.get("familia") not in disc["familias"]:
                g.errores.append(f"{donde}: familia «{n.get('familia')}» no declarada en {n['disciplina']}")
            for i in n["indicadores"]:
                if i not in disc["indicadores"]:
                    g.errores.append(f"{donde}: indicador «{i}» no declarado en {n['disciplina']}")

    for ciclo in buscar_ciclos(g):
        g.errores.append("ciclo de dependencias: " + " → ".join(ciclo))
    return not g.errores


def buscar_ciclos(g):
    BLANCO, GRIS, NEGRO = 0, 1, 2
    color = {nid: BLANCO for nid in g.nodos}
    ciclos = []
    for inicio in g.nodos:
        if color[inicio] != BLANCO:
            continue
        pila = [(inicio, iter(prerrequisitos(g, inicio)))]
        camino = [inicio]
        color[inicio] = GRIS
        while pila:
            nodo, hijos = pila[-1]
            siguiente = next(hijos, None)
            if siguiente is None:
                color[nodo] = NEGRO
                pila.pop()
                camino.pop()
            elif color[siguiente] == GRIS:
                ciclos.append(camino[camino.index(siguiente):] + [siguiente])
            elif color[siguiente] == BLANCO:
                color[siguiente] = GRIS
                pila.append((siguiente, iter(prerrequisitos(g, siguiente))))
                camino.append(siguiente)
    return ciclos


def prerrequisitos(g, nid):
    return [a["destino"] for a in g.salientes(nid) if a["rel"] in PRERREQUISITO and a["destino"] in g.nodos]


# ----------------------------------------------------------------------------
# Rutas: vistas filtradas del grafo
# ----------------------------------------------------------------------------

def objetivos_de(g, disciplina=None, estilo=None, objetivo=None):
    if objetivo:
        return [objetivo]
    piezas = [p for p in g.de_tipo("pieza") if p["disciplina"] == disciplina]
    if not estilo:
        return [p["id"] for p in piezas]

    def caracteriza(nid):
        return any(a["rel"] == "caracteriza" and a["destino"] == estilo for a in g.salientes(nid))

    elegidas = []
    for p in piezas:
        realizados = [a["destino"] for a in g.salientes(p["id"]) if a["rel"] == "realiza"]
        if caracteriza(p["id"]) or any(caracteriza(c) for c in realizados):
            elegidas.append(p["id"])
    return elegidas


def cierre(g, objetivos):
    vistos, pila = set(), list(objetivos)
    while pila:
        n = pila.pop()
        if n in vistos or n not in g.nodos:
            continue
        vistos.add(n)
        pila.extend(prerrequisitos(g, n))
    return vistos


def orden_topologico(g, conjunto, clave):
    """Ordena para que nada aparezca antes que aquello en lo que se apoya."""
    faltan = {n: {d for d in prerrequisitos(g, n) if d in conjunto} for n in conjunto}
    dependientes = defaultdict(set)
    for n, deps in faltan.items():
        for d in deps:
            dependientes[d].add(n)
    cola = [(clave(n), n) for n, deps in faltan.items() if not deps]
    heapq.heapify(cola)
    orden = []
    while cola:
        _, n = heapq.heappop(cola)
        orden.append(n)
        for m in dependientes[n]:
            faltan[m].discard(n)
            if not faltan[m]:
                heapq.heappush(cola, (clave(m), m))
    return orden


def calcular_ruta(g, disciplina=None, estilo=None, objetivo=None):
    objetivos = objetivos_de(g, disciplina, estilo, objetivo)
    todo = cierre(g, objetivos)
    piezas = {n for n in todo if g.nodos[n]["tipo"] == "pieza"}
    conceptos = {n for n in todo if g.nodos[n]["tipo"] == "concepto"}
    orden_piezas = orden_topologico(
        g, piezas, lambda n: (g.rango_capa(g.nodos[n]), g.nodos[n]["nombre"]))
    orden_conceptos = orden_topologico(
        g, conceptos, lambda n: (g.nodos[n]["dominio"], g.nodos[n]["nombre"]))
    return dict(objetivos=objetivos, piezas=orden_piezas, conceptos=orden_conceptos, todo=todo)


def grado_pedido(g, concepto, dentro):
    """El modo más alto que piden los nodos de la ruta a un concepto."""
    modos = [a["modo"] for a in g.entrantes(concepto)
             if a["rel"] == "requiere" and a["origen"] in dentro and a["modo"]]
    return max(modos, key=MODOS.index) if modos else None


# ----------------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------------

AVISO_GENERADO = "> Generado por `herramientas/vias.py` a partir de `datos/`. Edita los datos, no este archivo."


def enlazar(g, entrada, con_grado=True):
    texto = g.nombre(entrada["destino"])
    grado = entrada.get("etapa") or entrada.get("modo")
    if con_grado and grado:
        texto += f" ({grado_legible(grado)})"
    return texto


def lista_corta(nombres, maximo=3):
    if len(nombres) <= maximo:
        return ", ".join(nombres)
    return ", ".join(nombres[:maximo]) + f" y {len(nombres) - maximo} más"


def etiqueta_mermaid(texto):
    return (texto or "").replace('"', "'").replace("#", "nº")


def diagrama(g, piezas, conceptos):
    ids = {n: f"n{i}" for i, n in enumerate(piezas + conceptos)}
    lineas = ["```mermaid", "graph LR"]
    for n in piezas:
        lineas.append(f'  {ids[n]}["{etiqueta_mermaid(g.nombre(n))}"]')
    por_dominio = defaultdict(list)
    for n in conceptos:
        por_dominio[g.nodos[n]["dominio"]].append(n)
    for dom, lista in por_dominio.items():
        lineas.append(f'  subgraph dom_{dom.replace("-", "_")}["{etiqueta_mermaid(g.nombre(dom))}"]')
        for n in lista:
            lineas.append(f'    {ids[n]}(["{etiqueta_mermaid(g.nombre(n))}"])')
        lineas.append("  end")
    for n in piezas + conceptos:
        for a in g.salientes(n):
            if a["rel"] not in PRERREQUISITO or a["destino"] not in ids:
                continue
            flecha = "-->" if a["rel"] == "compuesto_de" else "-.->"
            grado = a["etapa"] or a["modo"]
            texto = f"|{grado_legible(grado)}|" if grado else ""
            lineas.append(f"  {ids[a['destino']]} {flecha}{texto} {ids[n]}")
    lineas.append("  classDef concepto fill:#eef3f8,stroke:#7a93ad,color:#1d2b3a")
    lineas.append("  classDef revisar stroke:#c27a00,stroke-width:2px,stroke-dasharray:4 3")
    if conceptos:
        lineas.append("  class " + ",".join(ids[n] for n in conceptos) + " concepto")
    marcados = [ids[n] for n in piezas + conceptos if g.nodos[n].get("revisar")]
    if marcados:
        lineas.append("  class " + ",".join(marcados) + " revisar")
    lineas.append("```")
    return "\n".join(lineas)


def markdown_ruta(g, titulo, disciplina=None, estilo=None, objetivo=None):
    r = calcular_ruta(g, disciplina, estilo, objetivo)
    piezas, conceptos, dentro = r["piezas"], r["conceptos"], r["todo"]
    if not disciplina and objetivo in g.nodos:
        disciplina = g.nodos[objetivo].get("disciplina")
    disc = g.disciplinas.get(disciplina)
    md = [f"# Vía · {titulo}", "", AVISO_GENERADO, ""]

    if objetivo:
        md.append(f"**Objetivo:** {g.nombre(objetivo)}.")
    elif estilo:
        md.append(f"**Objetivo:** las piezas de {g.nombre(disciplina).lower()} que caracterizan "
                  f"la {g.nombre(estilo).lower()} ({len(r['objetivos'])}).")
    md.append(f"**Recorrido:** {len(piezas)} piezas y {len(conceptos)} conceptos del dominio. "
              "Las marcadas con ⚑ piden revisión de alguien que lo practique.")
    # En el mapa, solo los conceptos que piden directamente las piezas; el resto va en la tabla.
    directos = [c for c in conceptos
                if any(a["rel"] == "requiere" and a["origen"] in piezas for a in g.entrantes(c))]
    md += ["", "## Mapa", "",
           "Cada flecha va de lo que hace falta antes a lo que se apoya en ello. "
           "Continua: está compuesto de. Discontinua: requiere. Los óvalos son los conceptos del dominio "
           "que piden las piezas; sus propios fundamentos están en la tabla del final.", "",
           diagrama(g, piezas, directos), ""]

    md += ["## Recorrido", "",
           "Ordenado para que nada aparezca antes que aquello en lo que se apoya. "
           "Cada paso pasa por el bucle: aislar, lento, preciso, a tempo, combinar.", ""]
    for i, n in enumerate(piezas, 1):
        p = g.nodos[n]
        marca = " ⚑" if p.get("revisar") else ""
        familia = g.disciplinas[p["disciplina"]]["familias"].get(p["familia"], p["familia"])
        md.append(f"{i}. **{p['nombre']}**{marca} · {g.etiqueta_capa(p)} · {familia.lower()}")
        detalles = []
        if p.get("descripcion"):
            detalles.append(p["descripcion"])
        hecho = [enlazar(g, a) for a in g.salientes(n) if a["rel"] == "compuesto_de"]
        if hecho:
            detalles.append("Hecho de: " + ", ".join(hecho) + ".")
        req = [enlazar(g, a) for a in g.salientes(n) if a["rel"] == "requiere"]
        if req:
            detalles.append("Requiere: " + ", ".join(req) + ".")
        realiza = [g.nombre(a["destino"]) for a in g.salientes(n) if a["rel"] == "realiza"]
        if realiza:
            detalles.append("Realiza: " + ", ".join(realiza) + ".")
        if p["indicadores"]:
            nombres = [g.disciplinas[p["disciplina"]]["indicadores"][i_]["nombre"].lower()
                       for i_ in p["indicadores"]]
            detalles.append("Mide: " + ", ".join(nombres) + ".")
        for d in detalles:
            md.append(f"   {d}  ")
        md.append("")

    md += ["## Lo que necesitas del dominio", "",
           "El grado es el más alto que pide algún paso de la ruta. "
           "Sin grado: basta con tenerlo de base.", "",
           "| Concepto | Dominio | Grado | Lo piden |", "| --- | --- | --- | --- |"]
    for c in conceptos:
        nodo = g.nodos[c]
        grado = grado_legible(grado_pedido(g, c, dentro)) or "—"
        piden = [g.nombre(a["origen"]) for a in g.entrantes(c)
                 if a["rel"] == "requiere" and a["origen"] in dentro]
        marca = " ⚑" if nodo.get("revisar") else ""
        md.append(f"| {nodo['nombre']}{marca} | {g.nombre(nodo['dominio'])} | {grado} | {lista_corta(piden) or '—'} |")
    md.append("")

    if disc:
        md += [f"## Indicadores de {disc['nombre'].lower()}", ""]
        for ind in disc["indicadores"].values():
            desc = f": {ind['descripcion']}" if ind.get("descripcion") else ""
            md.append(f"- **{ind['nombre']}**{desc}")
        md.append("")
    return "\n".join(md)


def markdown_concepto(g, cid):
    c = g.nodos[cid]
    md = [f"# {c['nombre']}", "", AVISO_GENERADO, "",
          f"Concepto del dominio **{g.nombre(c['dominio'])}**." + (f" {c['descripcion']}" if c.get("descripcion") else ""), ""]
    req = [enlazar(g, a) for a in g.salientes(cid) if a["rel"] == "requiere"]
    if req:
        md.append("**Se apoya en:** " + ", ".join(req) + ".  ")
    estilos = [g.nombre(a["destino"]) for a in g.salientes(cid) if a["rel"] == "caracteriza"]
    if estilos:
        md.append("**Caracteriza:** " + ", ".join(estilos) + ".  ")
    dims = [g.nombre(a["origen"]) for a in g.entrantes(cid) if a["rel"] == "configura"]
    if dims:
        md.append("**Lo configuran:** " + ", ".join(dims) + ".  ")
    md += ["", "## Cómo aparece en cada disciplina", "",
           "| Disciplina | Lo realizan | Lo necesitan |", "| --- | --- | --- |"]
    por_disc = defaultdict(lambda: {"realiza": [], "requiere": []})
    for a in g.entrantes(cid):
        o = g.nodos.get(a["origen"])
        if o and o["tipo"] == "pieza" and a["rel"] in ("realiza", "requiere"):
            texto = o["nombre"] + (f" ({grado_legible(a['modo'])})" if a.get("modo") else "")
            por_disc[o["disciplina"]][a["rel"]].append(texto)
    for did in sorted(por_disc):
        filas = por_disc[did]
        md.append(f"| {g.disciplinas[did]['nombre']} | {', '.join(filas['realiza']) or '—'} | "
                  f"{', '.join(filas['requiere']) or '—'} |")
    md.append("")
    return "\n".join(md)


def markdown_estilos(g, dominio):
    estilos = sorted((e for e in g.de_tipo("estilo") if e["dominio"] == dominio), key=lambda e: e["nombre"])
    md = [f"# Estilos · {g.nombre(dominio)}", "", AVISO_GENERADO, "",
          "Un estilo es una combinación fijada de valores sobre las dimensiones del dominio.", ""]
    dims, valores = [], defaultdict(dict)
    for e in estilos:
        for a in g.salientes(e["id"]):
            if a["rel"] == "configura":
                if a["destino"] not in dims:
                    dims.append(a["destino"])
                valores[a["destino"]][e["id"]] = a["valor"]
    md.append("| Dimensión | " + " | ".join(e["nombre"] for e in estilos) + " |")
    md.append("| --- " * (len(estilos) + 1) + "|")
    for d in dims:
        md.append(f"| {g.nombre(d)} | " + " | ".join(valores[d].get(e["id"], "—") for e in estilos) + " |")
    md.append("")
    for e in estilos:
        md += [f"## {e['nombre']}" + (" ⚑" if e.get("revisar") else ""), ""]
        if e.get("descripcion"):
            md += [e["descripcion"], ""]
        propios = [g.nombre(a["origen"]) for a in g.entrantes(e["id"])
                   if a["rel"] == "caracteriza" and g.nodos[a["origen"]]["tipo"] == "concepto"]
        if propios:
            md.append("**Conceptos propios:** " + ", ".join(propios) + ".  ")
        por_disc = defaultdict(list)
        for did in g.disciplinas:
            for pid in objetivos_de(g, did, e["id"]):
                por_disc[did].append(g.nombre(pid))
        for did, lista in por_disc.items():
            if lista:
                md.append(f"**En {g.disciplinas[did]['nombre'].lower()}:** " + ", ".join(lista) + ".  ")
        md.append("")
    return "\n".join(md)


# ----------------------------------------------------------------------------
# Exportación (para pasar a una base de datos más adelante)
# ----------------------------------------------------------------------------

CAMPOS_NODO = ["id", "tipo", "nombre", "descripcion", "dominio", "disciplina",
               "capa", "cadena", "familia", "indicadores", "revisar", "archivo"]
CAMPOS_RELACION = ["origen", "rel", "destino", "etapa", "modo", "valor"]


def exportar(g, carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / "nodos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_NODO, extrasaction="ignore")
        w.writeheader()
        for n in g.nodos.values():
            fila = dict(n)
            fila["indicadores"] = "|".join(n.get("indicadores") or [])
            fila["revisar"] = "sí" if n.get("revisar") else ""
            w.writerow(fila)
    with open(carpeta / "relaciones.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_RELACION, extrasaction="ignore")
        w.writeheader()
        for a in g.aristas:
            w.writerow(a)
    grafo = dict(
        nodos=[{k: v for k, v in n.items() if v not in (None, "", [], False)} for n in g.nodos.values()],
        relaciones=[{k: a[k] for k in CAMPOS_RELACION if a[k] is not None} for a in g.aristas],
        disciplinas={did: dict(nombre=d["nombre"], dominio=d["dominio"],
                               capas=[{"capa": c, "cadena": k} for c, k in d["capas"]],
                               familias=d["familias"], indicadores=d["indicadores"])
                     for did, d in g.disciplinas.items()})
    with open(carpeta / "grafo.json", "w", encoding="utf-8") as f:
        json.dump(grafo, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------
# Órdenes
# ----------------------------------------------------------------------------

def informe(g):
    cuenta = defaultdict(int)
    for n in g.nodos.values():
        cuenta[n["tipo"]] += 1
    resumen = ", ".join(f"{cuenta[t]} {t}s" for t in ("dominio", "concepto", "estilo", "disciplina", "pieza"))
    print(f"Grafo: {resumen}; {len(g.aristas)} relaciones.")
    por_revisar = [n["id"] for n in g.nodos.values() if n.get("revisar")]
    if por_revisar:
        print(f"Marcados para revisar: {len(por_revisar)}")
    for a in g.avisos:
        print(f"  aviso: {a}")
    for e in g.errores:
        print(f"  ERROR: {e}")
    print("Todo en orden." if not g.errores else f"{len(g.errores)} errores.")


def orden_validar(_args):
    g = cargar()
    ok = validar(g)
    informe(g)
    return 0 if ok else 1


def orden_ruta(args):
    g = cargar()
    if not validar(g):
        informe(g)
        return 1
    if not args.objetivo and args.disciplina not in g.disciplinas:
        print(f"No conozco la disciplina «{args.disciplina}». Hay: {', '.join(g.disciplinas)}")
        return 1
    titulo = args.titulo or " · ".join(
        x for x in (g.nombre(args.disciplina) if args.disciplina else None,
                    g.nombre(args.estilo) if args.estilo else None,
                    g.nombre(args.objetivo) if args.objetivo else None) if x)
    texto = markdown_ruta(g, titulo, args.disciplina, args.estilo, args.objetivo)
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
        print(f"Escrito {args.salida}")
    else:
        print(texto)
    return 0


def orden_todo(_args):
    g = cargar()
    ok = validar(g)
    informe(g)
    if not ok:
        print("Corrige los errores antes de generar.")
        return 1
    if GENERADO.exists():
        shutil.rmtree(GENERADO)
    (GENERADO / "rutas").mkdir(parents=True)
    (GENERADO / "conceptos").mkdir()
    (GENERADO / "estilos").mkdir()

    indice = ["# Generado", "", AVISO_GENERADO, "", "## Rutas", ""]
    for via in (leer_yaml(LISTA_VIAS).get("vias") or []):
        texto = markdown_ruta(g, via["titulo"], via.get("disciplina"), via.get("estilo"), via.get("objetivo"))
        (GENERADO / "rutas" / f"{via['id']}.md").write_text(texto, encoding="utf-8")
        indice.append(f"- [{via['titulo']}](rutas/{via['id']}.md)")

    indice += ["", "## Conceptos compartidos entre disciplinas", ""]
    for c in sorted(g.de_tipo("concepto"), key=lambda n: n["nombre"]):
        discs = {g.nodos[a["origen"]].get("disciplina") for a in g.entrantes(c["id"])
                 if a["rel"] in ("realiza", "requiere") and g.nodos.get(a["origen"], {}).get("tipo") == "pieza"}
        if len(discs) >= 2:
            (GENERADO / "conceptos" / f"{c['id']}.md").write_text(markdown_concepto(g, c["id"]), encoding="utf-8")
            indice.append(f"- [{c['nombre']}](conceptos/{c['id']}.md)")

    indice += ["", "## Estilos", ""]
    for dom in sorted({e["dominio"] for e in g.de_tipo("estilo")}):
        (GENERADO / "estilos" / f"{dom}.md").write_text(markdown_estilos(g, dom), encoding="utf-8")
        indice.append(f"- [{g.nombre(dom)}](estilos/{dom}.md)")

    exportar(g, GENERADO / "export")
    indice += ["", "## Exportación", "",
               "- [nodos.csv](export/nodos.csv) y [relaciones.csv](export/relaciones.csv): listos para importar en una base de datos",
               "- [grafo.json](export/grafo.json): el grafo entero para una web", ""]
    (GENERADO / "README.md").write_text("\n".join(indice), encoding="utf-8")
    print(f"Generado en {relativo(GENERADO)}/")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Valida el grafo de Vías y genera rutas.")
    sub = p.add_subparsers(dest="orden", required=True)
    sub.add_parser("validar", help="comprueba que el grafo es coherente").set_defaults(fn=orden_validar)
    sub.add_parser("todo", help="valida y regenera todo lo de generado/").set_defaults(fn=orden_todo)
    r = sub.add_parser("ruta", help="genera una ruta concreta")
    r.add_argument("disciplina", nargs="?")
    r.add_argument("--estilo")
    r.add_argument("--objetivo")
    r.add_argument("--titulo")
    r.add_argument("--salida", help="archivo donde guardarla (si no, se imprime)")
    r.set_defaults(fn=orden_ruta)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
