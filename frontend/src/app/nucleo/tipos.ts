// Formas de las respuestas de la API (SPEC 9.3 y 9.4). Los montos son enteros en pesos.

export interface Sesion {
  token: string;
  expira_en: string;
}

export interface Saldo {
  cuenta: string;
  saldo: number;
}

export interface Movimiento {
  tipo: string;
  contrapartida: string;
  monto: number;
  creado_en: string;
}

export interface Historial {
  movimientos: Movimiento[];
  desde: number;
  cantidad: number;
}

export interface Transaccion {
  id: number;
  tipo: string;
  origen: string;
  destino: string;
  monto: number;
  creado_en: string;
}

export type EstadoBolsa = 'abierta' | 'cancelada' | 'liquidando' | 'cerrada';
export type EstadoParticipante = 'pendiente' | 'pagado' | 'por_confirmar' | 'retirado';

export interface Bolsa {
  id: string;
  nombre: string;
  creador: string;
  cuenta_objetivo: string;
  total: number;
  fecha_limite: string;
  transferir_al_vencer: boolean;
  estado: EstadoBolsa;
  meta: number;
  aportado: number;
  transferido: number | null;
  participantes: {
    total: number;
    pendientes: number;
    pagados: number;
    por_confirmar: number;
    retirados: number;
  };
  mi_participacion: { parte: number; estado: EstadoParticipante };
}

export interface ResumenBolsa {
  id: string;
  nombre: string;
  estado: EstadoBolsa;
  fecha_limite: string;
  mi_parte: number;
  mi_estado: EstadoParticipante;
}

export interface ListaBolsas {
  bolsas: ResumenBolsa[];
  desde: number;
  cantidad: number;
}

export interface NuevaBolsa {
  nombre: string;
  total: number;
  participantes: string[];
  cuenta_objetivo: string;
  fecha_limite: string;
  transferir_al_vencer: boolean;
}
