"""Errores de dominio (SPEC 2.6).

Cada excepción lleva el `codigo` de la tabla de SPEC 2.6. La traducción a HTTP
vive en la API (T8), no aquí. Los códigos `forma_invalida`,
`falta_clave_idempotencia` y `metodo_no_permitido` los detecta solo la API; se
definen aquí para que haya un único catálogo.

Los mensajes nunca deben incluir cédulas, contraseñas ni tokens.
"""

from typing import ClassVar


class ErrorDominio(Exception):
    """Base de los errores de dominio."""

    codigo: ClassVar[str]

    def __init__(self, mensaje: str | None = None) -> None:
        self.mensaje = mensaje if mensaje is not None else self.mensaje_por_defecto
        super().__init__(self.mensaje)

    mensaje_por_defecto: ClassVar[str] = "Error de dominio."


class FormaInvalida(ErrorDominio):
    codigo = "forma_invalida"
    mensaje_por_defecto = (
        "La petición tiene una forma inválida (solo la detecta la API)."
    )


class MontoInvalido(ErrorDominio):
    codigo = "monto_invalido"
    mensaje_por_defecto = "El monto debe ser un entero mayor que cero."


class SobreElTope(ErrorDominio):
    codigo = "sobre_el_tope"
    mensaje_por_defecto = "El monto supera el tope por operación."


class TransferenciaASiMismo(ErrorDominio):
    codigo = "transferencia_a_si_mismo"
    mensaje_por_defecto = "No se puede transferir a la propia cuenta."


class TotalInvalido(ErrorDominio):
    codigo = "total_invalido"
    mensaje_por_defecto = "El total de la bolsa está fuera de los límites."


class FechaLimiteInvalida(ErrorDominio):
    codigo = "fecha_limite_invalida"
    mensaje_por_defecto = "La fecha límite está fuera de la ventana permitida."


class ParticipantesInvalidos(ErrorDominio):
    codigo = "participantes_invalidos"
    mensaje_por_defecto = "La lista de participantes no es válida."


class FaltaClaveIdempotencia(ErrorDominio):
    codigo = "falta_clave_idempotencia"
    mensaje_por_defecto = "Falta la cabecera Idempotency-Key (solo la detecta la API)."


class NoAutenticado(ErrorDominio):
    codigo = "no_autenticado"
    mensaje_por_defecto = (
        "Token ausente, inexistente o expirado, o credenciales inválidas."
    )


class SinPermiso(ErrorDominio):
    codigo = "sin_permiso"
    mensaje_por_defecto = "No tiene permiso sobre la bolsa."


class NoEncontrado(ErrorDominio):
    codigo = "no_encontrado"
    mensaje_por_defecto = "La cuenta o la bolsa no existe."


class RegistroRechazado(ErrorDominio):
    codigo = "registro_rechazado"
    mensaje_por_defecto = "El nombre de usuario o la cédula ya están registrados."


class NombreEnUso(ErrorDominio):
    codigo = "nombre_en_uso"
    mensaje_por_defecto = "El creador ya tiene una bolsa con ese nombre."


class SaldoInsuficiente(ErrorDominio):
    codigo = "saldo_insuficiente"
    mensaje_por_defecto = "Saldo insuficiente."


class FueraDePlazo(ErrorDominio):
    codigo = "fuera_de_plazo"
    mensaje_por_defecto = "La fecha límite ya pasó."


class EstadoInvalido(ErrorDominio):
    codigo = "estado_invalido"
    mensaje_por_defecto = "El estado actual no permite la operación."


class ClaveReutilizada(ErrorDominio):
    codigo = "clave_reutilizada"
    mensaje_por_defecto = "La clave de idempotencia ya se usó con otro cuerpo."


class MetodoNoPermitido(ErrorDominio):
    codigo = "metodo_no_permitido"
    mensaje_por_defecto = "Método no permitido en la ruta (solo lo detecta la API)."


class ReintentosAgotados(ErrorDominio):
    codigo = "reintentos_agotados"
    mensaje_por_defecto = "Se agotaron los reintentos de la operación."
