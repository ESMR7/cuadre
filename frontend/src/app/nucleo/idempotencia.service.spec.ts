import { IdempotenciaService } from './idempotencia.service';

describe('IdempotenciaService', () => {
  let servicio: IdempotenciaService;

  beforeEach(() => {
    servicio = new IdempotenciaService();
  });

  it('genera una clave UUID v4 al iniciar una intención', () => {
    const clave = servicio.claveDe('transferir');
    expect(clave).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it('un reintento de la misma intención reutiliza la clave', () => {
    expect(servicio.claveDe('transferir')).toBe(servicio.claveDe('transferir'));
  });

  it('intenciones distintas tienen claves distintas', () => {
    expect(servicio.claveDe('aportar:a')).not.toBe(servicio.claveDe('aportar:b'));
  });

  it('conserva la clave ante un error de red', () => {
    const clave = servicio.claveDe('cargar');
    servicio.fallo('cargar', 0);
    expect(servicio.claveDe('cargar')).toBe(clave);
  });

  it('conserva la clave ante 503 reintentos_agotados', () => {
    const clave = servicio.claveDe('cargar');
    servicio.fallo('cargar', 503);
    expect(servicio.claveDe('cargar')).toBe(clave);
  });

  it('conserva la clave ante cualquier 5xx', () => {
    const clave = servicio.claveDe('cargar');
    servicio.fallo('cargar', 500);
    servicio.fallo('cargar', 502);
    expect(servicio.claveDe('cargar')).toBe(clave);
  });

  it('borra la clave tras el éxito: la siguiente intención lleva otra', () => {
    const clave = servicio.claveDe('cargar');
    servicio.exito('cargar');
    expect(servicio.pendiente('cargar')).toBe(false);
    expect(servicio.claveDe('cargar')).not.toBe(clave);
  });

  it('borra la clave ante un 4xx definitivo', () => {
    for (const status of [400, 409, 422]) {
      const clave = servicio.claveDe('transferir');
      servicio.fallo('transferir', status);
      expect(servicio.claveDe('transferir')).not.toBe(clave);
    }
  });

  it('borra la clave cuando el usuario cambia el formulario', () => {
    const clave = servicio.claveDe('transferir');
    servicio.fallo('transferir', 503);
    servicio.cambioFormulario('transferir');
    expect(servicio.claveDe('transferir')).not.toBe(clave);
  });
});
