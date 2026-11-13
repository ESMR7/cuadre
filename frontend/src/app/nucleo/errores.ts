// Lo que ve el usuario ante un error sale solo de este mapa, según el campo
// `codigo` (SPEC 9.5). Nunca se muestra el `mensaje` de la API, el status HTTP
// ni el texto de una excepción.

const MENSAJES: Record<string, string> = {
  no_autenticado: 'Tu sesión no es válida o expiró. Inicia sesión de nuevo.',
  sin_permiso: 'No participas en esta bolsa.',
  no_encontrado: 'No encontramos lo que buscas (revisa el nombre de la cuenta).',
  forma_invalida: 'Revisa los datos del formulario.',
  monto_invalido: 'El monto debe ser un número entero mayor que cero.',
  sobre_el_tope: 'El monto supera el tope permitido.',
  total_invalido: 'El total de la bolsa no es válido.',
  participantes_invalidos: 'La lista de participantes no es válida.',
  fecha_limite_invalida: 'La fecha límite no es válida.',
  transferencia_a_si_mismo: 'No puedes transferirte a ti mismo.',
  saldo_insuficiente: 'No tienes saldo suficiente.',
  fuera_de_plazo: 'La bolsa ya venció.',
  estado_invalido: 'La bolsa no permite esta operación en su estado actual.',
  clave_reutilizada: 'Esta operación ya se hizo con otros datos. Empieza una nueva.',
  falta_clave_idempotencia: 'Falta la clave de la operación. Inténtalo de nuevo.',
  nombre_en_uso: 'Ese nombre ya está en uso.',
  registro_rechazado: 'No se pudo completar el registro con esos datos.',
  reintentos_agotados: 'El servicio está ocupado. Puedes reintentar la misma operación.',
  metodo_no_permitido: 'Operación no permitida.',
};

const SIN_CONEXION = 'No hubo respuesta del servidor. Puedes reintentar.';
const GENERICO = 'Ocurrió un error inesperado.';

/** Devuelve el `codigo` de un error de la API, o null si no trae uno. */
export function codigoDe(error: unknown): string | null {
  const cuerpo = (error as { error?: unknown } | null)?.error;
  if (cuerpo && typeof cuerpo === 'object' && 'codigo' in cuerpo) {
    const codigo = (cuerpo as { codigo: unknown }).codigo;
    return typeof codigo === 'string' ? codigo : null;
  }
  return null;
}

/** Mensaje para el usuario, decidido solo por el `codigo`. */
export function mensajeDe(error: unknown): string {
  const codigo = codigoDe(error);
  if (codigo === null) {
    return SIN_CONEXION;
  }
  return MENSAJES[codigo] ?? GENERICO;
}
