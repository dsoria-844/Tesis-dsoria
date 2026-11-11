"""Esquemas Pydantic de la API (documentados automáticamente en /docs)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Protocolo = Literal["SSH", "TELNET"]
EstadoAlerta = Literal["NUEVA", "EN_REVISION", "ARCHIVADA"]
Rol = Literal["RESPONSABLE_SEGURIDAD", "AUDITOR", "ADMIN_INFRA"]


class LoginIn(BaseModel):
    correo: str = Field(max_length=255)
    password: str = Field(max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    rol: Rol
    correo: str


class MeOut(BaseModel):
    id: UUID
    correo: str
    rol: Rol


class SesionResumen(BaseModel):
    id: UUID
    session_cowrie_id: str
    ip_origen: str
    puerto_origen: int | None
    protocolo: Protocolo
    fecha_inicio: datetime
    fecha_fin: datetime | None
    duracion_segundos: int | None
    n_intentos: int
    n_comandos: int
    obtuvo_acceso: bool


class SesionPagina(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[SesionResumen]


class IntentoOut(BaseModel):
    timestamp_evento: datetime
    usuario_ensayado: str
    password_ensayado: str | None
    autenticado: bool


class ComandoOut(BaseModel):
    timestamp_evento: datetime
    tipo_evento: str
    comando_tipeado: str
    url_descarga: str | None
    hash_descarga_sha256: str | None


class SesionDetalle(SesionResumen):
    sensor: str
    intentos: list[IntentoOut]
    comandos: list[ComandoOut]


class EventoOut(BaseModel):
    timestamp_evento: datetime
    tipo: str
    ip_origen: str
    sesion_id: UUID
    detalle: str
    autenticado: bool | None


class EventoPagina(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventoOut]


class Desglose(BaseModel):
    frecuencia: float
    volumen: float
    diversidad: float
    persistencia: float
    n_intentos: int
    k_pares_distintos: int
    ventana_segundos: int


class AlertaOut(BaseModel):
    id: int
    ip_origen: str
    fecha_disparo: datetime
    nivel_criticidad: str
    puntaje_asi: float
    estado_alerta: EstadoAlerta
    observaciones_auditor: str | None
    desglose: Desglose


class HistorialOut(BaseModel):
    fecha: datetime
    auditor: str
    estado_anterior: str | None
    estado_nuevo: str | None
    observaciones_anterior: str | None
    observaciones_nueva: str | None


class AlertaDetalle(AlertaOut):
    historial: list[HistorialOut]


class AlertaPagina(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AlertaOut]


class Kpi(BaseModel):
    valor: int
    anterior: int
    variacion_pct: float | None


class PuntoSerie(BaseModel):
    hora: datetime
    ssh: int
    telnet: int


class TopIp(BaseModel):
    ip_origen: str
    puntaje_asi: float
    clasificacion: str
    n_intentos: int
    k_pares_distintos: int
    fecha_calculo: datetime


class Subred(BaseModel):
    subred: str
    sesiones: int


class Latencias(BaseModel):
    ingesta_ms: float | None
    veredicto_ms: float | None


class MetricasOut(BaseModel):
    horas: int
    sesiones: Kpi
    ips_unicas: Kpi
    intentos_login: Kpi
    alertas_abiertas: int
    comandos: int
    serie: list[PuntoSerie]
    top_ips: list[TopIp]
    subredes: list[Subred]
    latencias: Latencias


class ActividadIp(BaseModel):
    ip_origen: str
    protocolos: list[str]
    sesiones: int
    intentos_login: int
    intentos_exitosos: int
    comandos: int
    ultimo_evento: datetime
    puntaje_asi: float | None
    clasificacion: str | None
    fecha_calculo: datetime | None
    alerta_abierta: bool


class TotalesVivo(BaseModel):
    ips: int
    sesiones: int
    intentos_login: int
    comandos: int


class ActividadVivoOut(BaseModel):
    minutos: int | None  # None = todo el histórico
    ahora: datetime
    totales: TotalesVivo
    total_ips: int
    limit: int
    offset: int
    items: list[ActividadIp]


class ConteoCredencial(BaseModel):
    valor: str
    intentos: int
    porcentaje: float


class CredencialesOut(BaseModel):
    horas: int
    total_intentos: int
    usuarios: list[ConteoCredencial]
    passwords: list[ConteoCredencial]
    pares: list[ConteoCredencial]


class SensorOut(BaseModel):
    id: UUID
    nombre: str
    ip_interna: str
    protocolo_emulado: str
    estado: str
    fecha_creacion: datetime
    sesiones_24h: int


class UsuarioOut(BaseModel):
    id: UUID
    correo: str
    rol: Rol
    estado: str
    bloqueado_hasta: datetime | None
    fecha_creacion: datetime


class UsuarioIn(BaseModel):
    correo: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str
    rol: Rol


class UsuarioPatch(BaseModel):
    rol: Rol | None = None
    estado: Literal["ACTIVO", "INACTIVO"] | None = None


# ------------------------------------------------------------ detalle por IP
class ResumenIpOut(BaseModel):
    ip_origen: str
    protocolos: list[str]
    primer_evento: datetime | None
    ultimo_evento: datetime | None
    sesiones: int
    intentos_login: int
    intentos_exitosos: int
    comandos: int
    alerta_abierta: bool


class ComponenteAsi(BaseModel):
    clave: Literal["frecuencia", "volumen", "diversidad", "persistencia"]
    valor: float
    peso: float
    aporte: float


class UltimoAsi(BaseModel):
    fecha_calculo: datetime
    ventana_segundos: int
    n_intentos: int
    k_pares_distintos: int
    componentes: list[ComponenteAsi]
    puntaje_asi: float
    clasificacion: str


class PuntoAsi(BaseModel):
    fecha_calculo: datetime
    puntaje_asi: float
    clasificacion: str
    ventana_segundos: int


class AsiIpOut(BaseModel):
    ip_origen: str
    ultima: UltimoAsi | None
    serie: list[PuntoAsi]


class CredencialesIpOut(BaseModel):
    ip_origen: str
    total_intentos: int
    usuarios: list[ConteoCredencial]
    passwords: list[ConteoCredencial]
    pares: list[ConteoCredencial]


class AlertasIpOut(BaseModel):
    ip_origen: str
    total: int
    items: list[AlertaDetalle]


# ------------------------------------------------------------ perfil propio / serie / reinicio de laboratorio
class PerfilOut(BaseModel):
    id: UUID
    correo: str
    rol: Rol
    estado: str
    fecha_creacion: datetime


class AccesoOut(BaseModel):
    fecha: datetime
    ip_cliente: str | None
    evento: str
    detalle: str | None


class SerieOut(BaseModel):
    vista: str
    paso_segundos: int
    serie: list[PuntoSerie]


class ReinicioIn(BaseModel):
    confirmacion: str = Field(max_length=32)


class ReinicioOut(BaseModel):
    eliminados: dict[str, int]
