/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public address of the gateway, for example http://localhost:18080. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
