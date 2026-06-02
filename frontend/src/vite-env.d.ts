// Augments the vite/client ImportMetaEnv interface (loaded via tsconfig "types")
// with the project's custom environment variable.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}
