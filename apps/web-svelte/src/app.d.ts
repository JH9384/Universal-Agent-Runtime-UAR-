/// <reference types="@sveltejs/kit" />

declare global {
  namespace App {
    interface Error {
      message: string;
      code?: string;
    }
    interface Locals {}
    interface PageData {}
    interface Platform {}
  }
}

export {};
