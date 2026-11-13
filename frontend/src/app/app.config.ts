import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';

import { opcionesRouter, routes } from './app.routes';
import { authInterceptor } from './nucleo/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, opcionesRouter),
    provideHttpClient(withInterceptors([authInterceptor])),
  ],
};
