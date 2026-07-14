# -*- coding: utf-8 -*-
"""
Núcleo de la simulación de uso del sistema (20 usuarios: 10 entrenadores + 10 clientes).
=========================================================================================
- Cliente HTTP fino sobre la API local real (http://localhost:8000/api).
- Personas con datos realistas y variados.
- Registro de hallazgos categorizado (SEGURIDAD / BUG / DISEÑO) con severidad.
- SOLO contra la base de PRUEBAS. Los usuarios simulados usan el dominio @simulacion.test
  para poder limpiarlos después sin tocar datos reales.

No se ejecuta solo: lo usan los scripts de escenario (_sim_flujos.py, _sim_seguridad.py).
"""
import os
import json
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Any

BASE = os.environ.get("SIM_BASE_URL", "http://localhost:8000/api")
DOMINIO = "jg12-sim.com"             # marca (TLD real, dominio inexistente) para borrar luego
PASSWORD = "Simulacion123"           # contraseña común de los usuarios simulados


# ----------------------------------------------------------------- hallazgos
SEVERIDADES = ("critica", "alta", "media", "baja", "info")
CATEGORIAS = ("SEGURIDAD", "BUG", "DISENO")

_HALLAZGOS: list = []


def hallazgo(categoria: str, severidad: str, titulo: str, detalle: str,
             endpoint: str = "", reproducir: str = ""):
    """Registra un hallazgo de la auditoría."""
    assert categoria in CATEGORIAS, categoria
    assert severidad in SEVERIDADES, severidad
    _HALLAZGOS.append({
        "categoria": categoria, "severidad": severidad, "titulo": titulo,
        "detalle": detalle, "endpoint": endpoint, "reproducir": reproducir,
    })
    marca = {"critica": "[!!!]", "alta": "[!! ]", "media": "[!  ]", "baja": "[ . ]", "info": "[ i ]"}[severidad]
    print(f"  {marca} [{categoria}/{severidad}] {titulo}")


def hallazgos():
    return list(_HALLAZGOS)


def guardar_informe(ruta_json: str):
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(_HALLAZGOS, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------- cliente HTTP
class Api:
    """Sesión HTTP de un usuario (guarda su token). Cada llamada devuelve (status, json|texto)."""

    def __init__(self, etiqueta: str = "anon"):
        self.etiqueta = etiqueta
        self.token: Optional[str] = None
        self.s = requests.Session()

    def _headers(self, extra=None):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if extra:
            h.update(extra)
        return h

    def req(self, metodo: str, ruta: str, *, json_body=None, params=None, auth=True, timeout=30):
        url = ruta if ruta.startswith("http") else f"{BASE}{ruta}"
        headers = self._headers()
        if not auth:
            headers.pop("Authorization", None)
        try:
            r = self.s.request(metodo, url, json=json_body, params=params,
                               headers=headers, timeout=timeout)
        except requests.RequestException as e:
            return 0, f"EXCEPCION: {e}"
        try:
            body = r.json()
        except ValueError:
            body = r.text
        return r.status_code, body

    def get(self, ruta, **kw):    return self.req("GET", ruta, **kw)
    def post(self, ruta, **kw):   return self.req("POST", ruta, **kw)
    def put(self, ruta, **kw):    return self.req("PUT", ruta, **kw)
    def patch(self, ruta, **kw):  return self.req("PATCH", ruta, **kw)
    def delete(self, ruta, **kw): return self.req("DELETE", ruta, **kw)


# ----------------------------------------------------------------- personas
@dataclass
class Persona:
    idx: int
    rol: str                      # "trainer" | "client"
    nombre: str
    email: str
    telefono: str
    # datos de cuestionario (solo clientes)
    sexo: str = "hombre"
    edad: int = 30
    altura: int = 175
    peso: float = 78.0
    objetivo: str = "recomposicion"
    actividad: str = "moderado"
    api: Api = field(default=None, repr=False)
    user_id: Optional[str] = None
    profile_id: Optional[str] = None
    plan: Optional[str] = None
    trainer_id: Optional[str] = None


NOMBRES_TRAINER = [
    "Jesús Gallego", "Laura Prieto", "Marcos Díaz", "Nuria Sáez", "Álvaro Ruiz",
    "Elena Vidal", "Iván Torres", "Carla Moreno", "Rubén Ortega", "Sofía Navarro",
]
NOMBRES_CLIENTE = [
    "Pablo Herrero", "María Campos", "Diego Ferrer", "Ana Belén Gil", "Sergio Lozano",
    "Lucía Castro", "Javier Ramos", "Marta Aguado", "Hugo Peña", "Claudia Serrano",
]

# Perfiles de cliente variados (para ejercitar distintos caminos de macros y planes)
PERFILES_CLIENTE = [
    dict(sexo="hombre", edad=28, altura=180, peso=82, objetivo="definicion", actividad="alto"),
    dict(sexo="mujer",  edad=34, altura=165, peso=62, objetivo="recomposicion", actividad="moderado"),
    dict(sexo="hombre", edad=45, altura=175, peso=95, objetivo="perdida_grasa", actividad="sedentario"),
    dict(sexo="mujer",  edad=23, altura=170, peso=58, objetivo="volumen", actividad="alto"),
    dict(sexo="hombre", edad=52, altura=172, peso=88, objetivo="mantenimiento", actividad="moderado"),
    dict(sexo="mujer",  edad=29, altura=160, peso=70, objetivo="perdida_grasa", actividad="bajo"),
    dict(sexo="hombre", edad=19, altura=185, peso=72, objetivo="volumen", actividad="alto"),
    dict(sexo="mujer",  edad=41, altura=168, peso=75, objetivo="definicion", actividad="moderado"),
    dict(sexo="hombre", edad=36, altura=178, peso=80, objetivo="recomposicion", actividad="moderado"),
    dict(sexo="mujer",  edad=60, altura=158, peso=66, objetivo="mantenimiento", actividad="sedentario"),
]


def construir_personas() -> list:
    personas = []
    for i in range(10):
        n = NOMBRES_TRAINER[i]
        personas.append(Persona(
            idx=i, rol="trainer", nombre=n,
            email=f"sim.trainer{i}@{DOMINIO}",
            telefono=f"6{i:02d}000{i:03d}",
        ))
    for i in range(10):
        n = NOMBRES_CLIENTE[i]
        p = PERFILES_CLIENTE[i]
        personas.append(Persona(
            idx=i, rol="client", nombre=n,
            email=f"sim.cliente{i}@{DOMINIO}",
            telefono=f"7{i:02d}000{i:03d}",
            **p,
        ))
    return personas


def es_ok(status) -> bool:
    return 200 <= status < 300
